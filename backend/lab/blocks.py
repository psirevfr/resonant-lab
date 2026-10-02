"""Single source of truth for DSP, parameter units and mathematical documentation."""
from dataclasses import dataclass, asdict
from typing import Callable
import numpy as np
from scipy import signal

@dataclass(frozen=True)
class Parameter:
    default: float
    minimum: float
    maximum: float
    unit: str
    label: str

@dataclass(frozen=True)
class Definition:
    label: str
    category: str
    inputs: int  # -1 = variadic, at least one
    parameters: dict[str, Parameter]
    equation: str
    description: str
    lti: bool = False

def p(default, low, high, unit, label):
    return Parameter(default, low, high, unit, label)

FREQ = p(440, 1, 47000, 'Hz', 'Fréquence')
AMP = p(0.3, 0, 4, '', 'Amplitude')
TAU = p(1, 0.005, 30, 's', 'Décroissance τ')
ATTACK = p(0.005, 0, 5, 's', 'Attaque')
FILTER = {'fc': p(3500, 5, 47000, 'Hz', 'Fréquence caractéristique'), 'q': p(0.70710678, 0.1, 40, '', 'Facteur Q')}
REGISTRY: dict[str, Definition] = {
 'input': Definition('Entrée LTI', 'Générateurs', 0, {}, 'x[n]', 'Entrée externe pour mesurer un système LTI. Impulsion unité en simulation autonome.', True),
 'oscillator': Definition('Sinus', 'Générateurs', 0, {'frequency': FREQ, 'amplitude': AMP, 'phase': p(0,-np.pi,np.pi,'rad','Phase')}, 'x(t) = A sin(2πft + φ)', 'Oscillateur sinusoïdal déterministe. Fréquence strictement inférieure à Nyquist.'),
 'modal': Definition('Mode amorti', 'Physique', 0, {'frequency': FREQ,'amplitude': AMP,'phase': p(0,-np.pi,np.pi,'rad','Phase'),'tau': TAU,'attack': ATTACK,'onset': p(0,0,60,'s','Début')}, 'x(t) = A e^(−u/τ)(1−e^(−u/a)) sin(2πfu+φ), u=t−t₀ ≥ 0', 'Mode oscillatoire amorti avec mise en vibration progressive. Après attaque : q″ + 2q′/τ + ((2πf)² + 1/τ²)q = 0. La phase et l’amplitude décrivent les conditions initiales ; aucune identification unique de masse/raideur.'),
 'noise': Definition('Bruit blanc', 'Générateurs', 0, {'amplitude': AMP,'seed': p(42,0,1000000,'','Graine')}, 'x[n] = A ξ[n], ξ ~ N(0,1)', 'Bruit gaussien reproductible à graine fixée. Amplitude = écart-type.'),
 'impulse': Definition('Impulsion', 'Générateurs', 0, {'amplitude': AMP}, 'x[n] = A δ[n]', 'Impulsion discrète unité, pas une distribution de Dirac continue.'),
 'gain': Definition('Gain', 'Mathématiques', 1, {'gain': p(1,-4,4,'×','Gain')}, 'H(z) = g', 'Gain linéaire constant.', True),
 'sum': Definition('Somme', 'Mathématiques', -1, {}, 'y[n] = Σ xᵢ[n]', 'Somme sans normalisation implicite.', True),
 'multiply': Definition('Produit / VCA', 'Dynamique', 2, {}, 'y[n] = x₁[n] x₂[n]', 'Produit de deux signaux. Pas de fonction de transfert LTI globale.'),
 'lowpass': Definition('Passe-bas', 'Filtres', 1, FILTER, 'H(s) = Ω² / (s² + Ωs/Q + Ω²)', 'Second ordre. Transformation bilinéaire, Ω = 2fs tan(πfc/fs). Le Bode numérique tient compte du pré-gauchissement.', True),
 'highpass': Definition('Passe-haut', 'Filtres', 1, FILTER, 'H(s) = s² / (s² + Ωs/Q + Ω²)', 'Second ordre. Transformation bilinéaire pré-gauchie à fc.', True),
 'bandpass': Definition('Passe-bande', 'Filtres', 1, FILTER, 'H(s) = (Ω/Q)s / (s² + Ωs/Q + Ω²)', 'Gain unité à fc. Transformation bilinéaire pré-gauchie.', True),
 'notch': Definition('Coupe-bande', 'Filtres', 1, FILTER, 'H(s) = (s²+Ω²) / (s² + Ωs/Q + Ω²)', 'Zéro à fc. Transformation bilinéaire pré-gauchie.', True),
 'resonator': Definition('Résonateur', 'Physique', 1, {'frequency': FREQ,'tau': TAU}, 'H(z) = (1−r) / (1−2r cos(θ)z⁻¹+r²z⁻²)', 'Pôles r exp(±jθ), r=exp(−1/(fsτ)), θ=2πf/fs. Résonateur numérique stable ; amplitude non normalisée à la résonance.', True),
 'delay': Definition('Délai', 'Mathématiques', 1, {'seconds': p(0.01,0,2,'s','Retard')}, 'H(z) = z⁻ᴺ, N = round(fs T)', 'Retard entier, arrondi à l’échantillon le plus proche. Les boucles ne sont pas prises en charge.', True),
 'envelope': Definition('Enveloppe exponentielle', 'Dynamique', 1, {'attack': ATTACK,'tau': TAU,'onset': p(0,0,60,'s','Début')}, 'y(t) = x(t)(1−exp(−u/a))exp(−u/τ), u=t−t₀ ≥ 0', 'Multiplication temporelle. Linéaire mais non invariant dans le temps ; pas de Bode LTI.'),
 'adsr': Definition('ADSR', 'Dynamique', 1, {'attack': p(.01,0,5,'s','Attaque'),'decay': p(.2,.001,10,'s','Decay'),'sustain': p(.5,0,1,'×','Sustain'),'gate': p(1,0,60,'s','Durée de note'),'release': p(.4,.001,10,'s','Release')}, 'y(t) = x(t) A_ADSR(t)', 'Segments linéaires ; le relâchement part du niveau réellement atteint à la fin du gate. Le gate ne peut pas être déduit univoquement d’un WAV.'),
 'saturation': Definition('Saturation douce', 'Non linéaire', 1, {'drive': p(1,.01,20,'×','Drive')}, 'y[n] = tanh(d x[n])', 'Non-linéarité statique, sans suréchantillonnage : des harmoniques peuvent se replier. Aucun Bode LTI.'),
 'asymmetric_saturation': Definition('Saturation asymétrique ×4', 'Non linéaire', 1, {'drive':p(4,.1,60,'×','Drive'),'bias':p(.5,-3,3,'','Asymétrie'),'mix':p(1,0,1,'','Mélange'),'level':p(.2,0,4,'×','Niveau')}, 'y = g [(1−m)x + m(tanh(dx+b)−tanh(b))], suréchantillonnage ×4', 'Une seule non-linéarité, sans oscillateur caché. L’asymétrie permet des harmoniques paires. Interpolation et décimation polyphasées ×4 ; filtrage anti-repliement, sans garantie de suppression totale. Niveau explicite.'),
 'peak_eq': Definition('Égaliseur paramétrique', 'Filtres', 1, {'fc':p(1500,5,47000,'Hz','Fréquence centrale'),'q':p(1,.1,20,'','Facteur Q'),'db':p(0,-30,30,'dB','Gain de bande')}, 'H(s) = (s² + A Ω s/Q + Ω²)/(s² + Ω s/(A Q) + Ω²), A=10^(G/40)', 'Un biquad de correction spectrale, gain G dB à fc, unité à DC et Nyquist. Transformation bilinéaire pré-gauchie.', True),
 'lowpass1': Definition('Passe-bas 6 dB/oct', 'Filtres', 1, {'fc':p(3500,5,47000,'Hz','Fréquence caractéristique')}, 'H(s)=Ω/(s+Ω)', 'Premier ordre, transformation bilinéaire pré-gauchie à fc.', True),
 'output': Definition('Sortie', 'Mathématiques', 1, {}, 'y[n] = x[n]', 'Sortie mono du graphe. Aucun écrêtage ni normalisation cachée.', True),
}

def parameters(kind: str, values: dict[str, float], fs: int) -> dict[str, float]:
    if kind not in REGISTRY:
        raise ValueError(f'Bloc inconnu : {kind}')
    definition = REGISTRY[kind]
    if set(values) - set(definition.parameters):
        raise ValueError(f'Paramètres inconnus pour {kind}.')
    result = {}
    for name, spec in definition.parameters.items():
        value = values.get(name, spec.default)
        if not np.isfinite(value) or not spec.minimum <= value <= spec.maximum:
            raise ValueError(f'{kind}.{name} : valeur hors limites [{spec.minimum}, {spec.maximum}].')
        if name == 'seed' and not float(value).is_integer():
            raise ValueError('La graine du bruit doit être un entier.')
        if name in ('frequency', 'fc') and value >= fs / 2:
            raise ValueError(f'{name} doit être inférieure à Nyquist ({fs/2:g} Hz).')
        result[name] = value
    return result

def coefficients(kind: str, p: dict[str, float], fs: int):
    """Return b,a in ascending powers of z^-1, shared by audio and Bode."""
    if kind in ('lowpass', 'highpass', 'bandpass', 'notch'):
        w = 2 * fs * np.tan(np.pi * p['fc'] / fs)
        a = [1, w / p['q'], w*w]
        b = {'lowpass':[w*w], 'highpass':[1,0,0], 'bandpass':[w/p['q'],0], 'notch':[1,0,w*w]}[kind]
        return signal.bilinear(b, a, fs)
    if kind in ('peak_eq','lowpass1'):
        w=2*fs*np.tan(np.pi*p['fc']/fs)
        if kind=='lowpass1':return signal.bilinear([w],[1,w],fs)
        a=10**(p['db']/40)
        return signal.bilinear([1,a*w/p['q'],w*w],[1,w/(a*p['q']),w*w],fs)
    if kind == 'resonator':
        r = np.exp(-1 / (fs * p['tau']))
        return np.array([1-r]), np.array([1,-2*r*np.cos(2*np.pi*p['frequency']/fs),r*r])
    if kind in ('gain','sum','output','input'):
        return np.array([p.get('gain',1)]), np.array([1.])
    if kind == 'delay':
        b = np.zeros(round(fs*p['seconds'])+1); b[-1] = 1
        return b, np.array([1.])
    raise ValueError('Ce bloc n’est pas un système LTI : aucune fonction de transfert.')

def exponential(t, attack, tau):
    return np.exp(-t/tau) * (-np.expm1(-t/attack) if attack > 0 else 1)

def process(kind: str, p: dict, inputs: list[np.ndarray], fs: int, n: int) -> np.ndarray:
    t = np.arange(n) / fs
    if kind == 'oscillator':
        return p['amplitude'] * np.sin(2*np.pi*p['frequency']*t+p['phase'])
    if kind == 'modal':
        u = np.maximum(0, t-p['onset'])
        return p['amplitude']*exponential(u,p['attack'],p['tau'])*np.sin(2*np.pi*p['frequency']*u+p['phase'])*(t>=p['onset'])
    if kind == 'noise':
        return np.random.default_rng(int(p['seed'])).normal(0,p['amplitude'],n)
    if kind in ('impulse','input'):
        y = np.zeros(n); y[0] = p.get('amplitude',1); return y
    if kind == 'sum':
        return np.sum(inputs,axis=0)
    if kind == 'multiply':
        return inputs[0]*inputs[1]
    if kind == 'envelope':
        u=np.maximum(0,t-p.get('onset',0))
        return inputs[0]*exponential(u,p['attack'],p['tau'])*(t>=p.get('onset',0))
    if kind == 'adsr':
        def held(u):
            return np.where(u < p['attack'], u/max(p['attack'],1/fs), 1-(1-p['sustain'])*np.clip((u-p['attack'])/p['decay'],0,1))
        env = np.where(t < p['gate'], held(t), held(p['gate'])*np.clip(1-(t-p['gate'])/p['release'],0,1))
        return inputs[0]*env
    if kind == 'asymmetric_saturation':
        up=signal.resample_poly(inputs[0],4,1)
        shaped=p['level']*((1-p['mix'])*up+p['mix']*(np.tanh(p['drive']*up+p['bias'])-np.tanh(p['bias'])))
        return signal.resample_poly(shaped,1,4)[:n]
    if kind == 'saturation':
        return np.tanh(p['drive']*inputs[0])
    if kind == 'delay':
        k = round(fs*p['seconds']); y = np.zeros(n)
        if k < n: y[k:] = inputs[0][:n-k]
        return y
    b,a = coefficients(kind,p,fs)
    return signal.lfilter(b,a,inputs[0])

def catalog():
    return {kind: asdict(d) for kind,d in REGISTRY.items()}
