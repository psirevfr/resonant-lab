// frontend/.bench/reference.ts
var clamp = (x, a, b) => Math.max(a, Math.min(b, x));
var roundEven = (x) => x % 1 === 0.5 ? 2 * Math.round(x / 2) : Math.round(x);
function filter(x, b, a) {
  const y = new Float64Array(x.length);
  for (let i = 0; i < x.length; i++) {
    let v = 0;
    for (let j = 0; j < b.length && j <= i; j++) v += b[j] * x[i - j];
    for (let j = 1; j < a.length && j <= i; j++) v -= a[j] * y[i - j];
    y[i] = v / a[0];
  }
  return y;
}
function bessel(x) {
  let sum = 1, term = 1;
  for (let k = 1; k < 40; k++) {
    term *= x * x / (4 * k * k);
    sum += term;
    if (term < 1e-16) break;
  }
  return sum;
}
function fir() {
  const h = Array.from({ length: 81 }, (_, j) => {
    const i = j - 40;
    return (i === 0 ? 0.25 : Math.sin(Math.PI * i / 4) / (Math.PI * i)) * bessel(5 * Math.sqrt(1 - (i / 40) ** 2)) / bessel(5);
  });
  const sum = h.reduce((a, b) => a + b, 0);
  return h.map((v) => v / sum);
}
var h4 = fir();
function saturate4(x, p) {
  const up = new Float64Array(x.length * 4);
  for (let k = 0; k < up.length; k++) {
    let value = 0;
    for (let j = Math.max(0, Math.ceil((k - 40) / 4)); j <= Math.min(x.length - 1, Math.floor((k + 40) / 4)); j++) value += 4 * h4[k - 4 * j + 40] * x[j];
    up[k] = p.level * ((1 - p.mix) * value + p.mix * (Math.tanh(p.drive * value + p.bias) - Math.tanh(p.bias)));
  }
  const y = new Float64Array(x.length);
  for (let k = 0; k < y.length; k++) for (let j = Math.max(0, 4 * k - 40); j <= Math.min(up.length - 1, 4 * k + 40); j++) y[k] += h4[4 * k - j + 40] * up[j];
  return y;
}
function renderGraph(patch, catalog) {
  const fs = patch.sample_rate, n = Math.round(fs * patch.duration);
  if (![44100, 48e3, 96e3].includes(fs) || !Number.isFinite(n) || n < 32 || n > fs * 60 || patch.nodes.length > 128) throw Error("Mod\xE8le trop volumineux ou \xE9chantillonnage invalide.");
  const nodes = new Map(patch.nodes.map((b) => [b.id, b]));
  if (nodes.size !== patch.nodes.length) throw Error("Identifiants dupliqu\xE9s.");
  const inputs = new Map(patch.nodes.map((b) => [b.id, []])), uses = new Map(patch.nodes.map((b) => [b.id, 0]));
  const pairs = /* @__PURE__ */ new Set();
  for (const e of patch.edges) {
    const pair = e.source + "\0" + e.target;
    if (!nodes.has(e.source) || !nodes.has(e.target) || pairs.has(pair)) throw Error("C\xE2ble invalide.");
    pairs.add(pair);
    inputs.get(e.target).push(e.source);
    uses.set(e.source, uses.get(e.source) + 1);
  }
  const outputs = patch.nodes.filter((b) => b.type === "output");
  if (outputs.length !== 1 || uses.get(outputs[0].id)) throw Error("Une sortie terminale est requise.");
  const values = /* @__PURE__ */ new Map();
  for (const node of patch.nodes) {
    const d = catalog[node.type];
    if (!d) throw Error("Module inconnu : " + node.type);
    if (d.inputs >= 0 && inputs.get(node.id).length !== d.inputs || d.inputs < 0 && !inputs.get(node.id).length) throw Error("Connexions incompl\xE8tes : " + (node.label || node.type));
    if (Object.keys(node.parameters).some((k) => !d.parameters[k])) throw Error("Param\xE8tre inconnu.");
    const p = {};
    for (const [key, spec] of Object.entries(d.parameters)) {
      const value = node.parameters[key] ?? spec.default;
      if (!Number.isFinite(value) || value < spec.minimum || value > spec.maximum || ["frequency", "fc"].includes(key) && value >= fs / 2 || key === "seed" && !Number.isInteger(value)) throw Error("Param\xE8tre hors limites : " + key);
      p[key] = value;
    }
    values.set(node.id, p);
  }
  const order = [], visited = /* @__PURE__ */ new Set(), visiting = /* @__PURE__ */ new Set();
  function visit(id) {
    if (visiting.has(id)) throw Error("Boucle dans le graphe.");
    if (visited.has(id)) return;
    visiting.add(id);
    for (const from of inputs.get(id)) visit(from);
    visiting.delete(id);
    visited.add(id);
    order.push(id);
  }
  for (const id of nodes.keys()) visit(id);
  order.length = 0;
  visited.clear();
  visit(outputs[0].id);
  if (n * order.reduce((a, id) => a + (nodes.get(id).type === "asymmetric_saturation" ? 8 : 1), 0) > 1e8) throw Error("Rendu trop volumineux. R\xE9duisez la dur\xE9e.");
  const buffers = /* @__PURE__ */ new Map();
  for (const id of order) {
    const node = nodes.get(id), p = values.get(id), ins = inputs.get(id).map((k) => buffers.get(k)), kind = node.type;
    let y = new Float64Array(n);
    const envelope = (t) => {
      const u = t - (p.onset ?? 0);
      return u < 0 ? 0 : Math.exp(-u / p.tau) * (p.attack > 0 ? -Math.expm1(-u / p.attack) : 1);
    };
    if (kind === "asymmetric_saturation") y = saturate4(ins[0], p);
    else if (["lowpass", "highpass", "bandpass", "notch", "peak_eq", "lowpass1", "resonator"].includes(kind)) {
      let a, b;
      if (kind === "resonator") {
        const r = Math.exp(-1 / (fs * p.tau));
        a = [1, -2 * r * Math.cos(2 * Math.PI * p.frequency / fs), r * r];
        b = [1 - r];
      } else {
        const k = Math.tan(Math.PI * p.fc / fs), k2 = k * k, q = p.q ?? 1;
        if (kind === "lowpass1") {
          a = [1 + k, k - 1];
          b = [k, k];
        } else if (kind === "peak_eq") {
          const A = 10 ** (p.db / 40);
          a = [1 + k / (A * q) + k2, 2 * (k2 - 1), 1 - k / (A * q) + k2];
          b = [1 + A * k / q + k2, 2 * (k2 - 1), 1 - A * k / q + k2];
        } else {
          a = [1 + k / q + k2, 2 * (k2 - 1), 1 - k / q + k2];
          b = kind === "lowpass" ? [k2, 2 * k2, k2] : kind === "highpass" ? [1, -2, 1] : kind === "bandpass" ? [k / q, 0, -k / q] : [1 + k2, 2 * (k2 - 1), 1 + k2];
        }
      }
      y = filter(ins[0], b, a);
    } else {
      let seed = (p.seed ?? 42) >>> 0;
      seed = seed || 1831565813;
      const uniform = () => {
        seed ^= seed << 13;
        seed ^= seed >>> 17;
        seed ^= seed << 5;
        return ((seed >>> 0) + 0.5) / 4294967296;
      };
      const held = (t) => t < p.attack ? t / Math.max(p.attack, 1 / fs) : 1 - (1 - p.sustain) * clamp((t - p.attack) / p.decay, 0, 1);
      for (let i = 0; i < n; i++) {
        const t = i / fs;
        switch (kind) {
          case "oscillator":
            y[i] = p.amplitude * Math.sin(2 * Math.PI * p.frequency * t + p.phase);
            break;
          case "modal":
            y[i] = p.amplitude * envelope(t) * Math.sin(2 * Math.PI * p.frequency * Math.max(0, t - p.onset) + p.phase);
            break;
          case "noise":
            y[i] = p.amplitude * Math.sqrt(-2 * Math.log(uniform())) * Math.cos(2 * Math.PI * uniform());
            break;
          case "input":
          case "impulse":
            y[i] = i === 0 ? p.amplitude ?? 1 : 0;
            break;
          case "sum":
            for (const x of ins) y[i] += x[i];
            break;
          case "multiply":
            y[i] = ins[0][i] * ins[1][i];
            break;
          case "gain":
            y[i] = p.gain * ins[0][i];
            break;
          case "output":
            y[i] = ins[0][i];
            break;
          case "envelope":
            y[i] = ins[0][i] * envelope(t);
            break;
          case "adsr":
            y[i] = ins[0][i] * (t < p.gate ? held(t) : held(p.gate) * clamp(1 - (t - p.gate) / p.release, 0, 1));
            break;
          case "saturation":
            y[i] = Math.tanh(p.drive * ins[0][i]);
            break;
          case "delay": {
            const at = i - roundEven(fs * p.seconds);
            y[i] = at >= 0 ? ins[0][at] : 0;
            break;
          }
          default:
            throw Error("Module non pris en charge : " + kind);
        }
      }
    }
    for (const v of y) if (!Number.isFinite(v) || Math.abs(v) > 1e8) throw Error("Signal divergent. V\xE9rifiez les gains.");
    buffers.set(id, y);
    for (const source of inputs.get(id)) {
      uses.set(source, uses.get(source) - 1);
      if (uses.get(source) === 0) buffers.delete(source);
    }
  }
  return buffers.get(outputs[0].id);
}
function encodeWav(samples, fs) {
  const buffer = new ArrayBuffer(44 + samples.length * 4), v = new DataView(buffer);
  const text = (at, s) => {
    for (let i = 0; i < s.length; i++) v.setUint8(at + i, s.charCodeAt(i));
  };
  text(0, "RIFF");
  v.setUint32(4, buffer.byteLength - 8, true);
  text(8, "WAVE");
  text(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 3, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, fs, true);
  v.setUint32(28, fs * 4, true);
  v.setUint16(32, 4, true);
  v.setUint16(34, 32, true);
  text(36, "data");
  v.setUint32(40, samples.length * 4, true);
  for (let i = 0; i < samples.length; i++) v.setFloat32(44 + i * 4, samples[i], true);
  return buffer;
}
function fftMagnitude(x) {
  const n = x.length, re = x.slice(), im = new Float64Array(n);
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      const t = re[i];
      re[i] = re[j];
      re[j] = t;
    }
  }
  for (let len = 2; len <= n; len *= 2) {
    const angle = -2 * Math.PI / len;
    for (let i = 0; i < n; i += len) {
      let wr = 1, wi = 0;
      const cr = Math.cos(angle), ci = Math.sin(angle);
      for (let j = 0; j < len / 2; j++) {
        const u = i + j, v = u + len / 2, tr = re[v] * wr - im[v] * wi, ti = re[v] * wi + im[v] * wr;
        re[v] = re[u] - tr;
        im[v] = im[u] - ti;
        re[u] += tr;
        im[u] += ti;
        const next = wr * cr - wi * ci;
        wi = wr * ci + wi * cr;
        wr = next;
      }
    }
  }
  return Array.from({ length: n / 2 + 1 }, (_, i) => Math.hypot(re[i], im[i]));
}
function signalView(x, fs) {
  const time = [], wave = [], et = [], env = [];
  let peak = 0, power = 0;
  const stride = Math.max(1, Math.ceil(x.length / 1600));
  for (let i = 0; i < x.length; i += stride) {
    let lo = Infinity, hi = -Infinity, s = 0, count = 0;
    for (let j = i; j < Math.min(i + stride, x.length); j++) {
      lo = Math.min(lo, x[j]);
      hi = Math.max(hi, x[j]);
      power += x[j] * x[j];
      peak = Math.max(peak, Math.abs(x[j]));
      s += x[j] * x[j];
      count++;
    }
    time.push(i / fs, i / fs);
    wave.push(lo, hi);
    et.push(i / fs);
    env.push(Math.sqrt(s / count));
  }
  const size = 2 ** Math.floor(Math.log2(Math.min(1024, x.length))), hop = Math.max(size / 4, Math.ceil(x.length / 160)), window = Float64Array.from({ length: size }, (_, i) => (1 - Math.cos(2 * Math.PI * i / size)) / 2), norm = window.reduce((a, b) => a + b, 0), spectimes = [], columns = [];
  for (let start = 0; start + size <= x.length; start += hop) {
    const frame = Float64Array.from(window, (w, i) => w * x[start + i]);
    columns.push(fftMagnitude(frame).map((v) => v / norm));
    spectimes.push((start + size / 2) / fs);
  }
  const frequency = Array.from({ length: size / 2 + 1 }, (_, i) => i * fs / size), spectrum = frequency.map((_, i) => 20 * Math.log10(Math.max(1e-7, Math.sqrt(columns.reduce((s, c) => s + c[i] ** 2, 0) / columns.length))));
  return { time, wave, envelope_time: et, envelope: env, frequency, spectrum, spectrogram: { time: spectimes, frequency, db: frequency.map((_, i) => columns.map((c) => 20 * Math.log10(Math.max(c[i], 1e-7)))) }, peak, rms: Math.sqrt(power / x.length), duration: x.length / fs };
}
export {
  encodeWav,
  renderGraph,
  signalView
};
