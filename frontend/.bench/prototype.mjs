// src/modelPrototype.ts
function projectSingleMode(times, real, imag, attack, tau, offset) {
  if (times.length !== real.length || times.length !== imag.length || times.length < 12 || tau <= 0 || attack < 0 || ![tau, attack, offset].every(Number.isFinite)) throw Error("Projection invalide.");
  let dotR = 0, dotI = 0, norm = 0, scale2 = 0;
  const br = new Float64Array(times.length), bi = new Float64Array(times.length);
  for (let i = 0; i < times.length; i++) {
    if (![times[i], real[i], imag[i]].every(Number.isFinite)) throw Error("Trajectoire non finie.");
    const envelope = Math.exp(-times[i] / tau) * (attack > 0 ? -Math.expm1(-times[i] / attack) : 1), phase = 2 * Math.PI * times[i] * offset;
    r(i, envelope * Math.cos(phase), envelope * Math.sin(phase));
  }
  function r(i, a, b) {
    br[i] = a;
    bi[i] = b;
    norm += a * a + b * b;
    dotR += a * real[i] + b * imag[i];
    dotI += a * imag[i] - b * real[i];
    scale2 += real[i] ** 2 + imag[i] ** 2;
  }
  if (norm <= 1e-24) throw Error("Base d\xE9g\xE9n\xE9r\xE9e.");
  const coR = dotR / norm, coI = dotI / norm;
  let squared = 0;
  for (let i = 0; i < times.length; i++) {
    const er = br[i] * coR - bi[i] * coI - real[i], ei = br[i] * coI + bi[i] * coR - imag[i];
    squared += er * er + ei * ei;
  }
  return { co: [coR, coI], relative_squared_error: squared / Math.max(scale2, 1e-24) };
}
export {
  projectSingleMode
};
