"""Fit explicit subtractive chains and compare their executed signal to the additive reference."""
import numpy as np

from .graph import render
from .identify import complexity, generate, link
from .instrument import physical_count
from .metrics import Objective
from .schema import Block, Patch
from .texture import band_errors


def subtractive_generation(x, fs, request):
    additive = generate(x, fs, request.max_partials, request.complexity_penalty,
                        request.weights, request.refine_modes, request.include_impact, request.detailed)
    reference = additive['candidates'][0]
    features = additive['analysis']
    objective = Objective(x, fs, request.weights)
    f0 = float(np.clip(features.get('f0') or 220, 20, fs * .4))
    tau = float(np.median([p['tau'] for p in features['partials']]))
    sources = ('white_noise', 'pink_noise', 'saw', 'pulse', 'pulse_train')
    if request.source != 'auto':
        sources = (request.source,)
    spectrum = abs(np.fft.rfft(x*np.hanning(len(x))))**2
    frequencies = np.fft.rfftfreq(len(x),1/fs)
    center = float(np.dot(spectrum,frequencies)/max(spectrum.sum(),1e-20))
    cutoff_hint = float(np.clip(2*center,40,fs*.4))
    rows = []
    for source in sources:
        values = {'amplitude': .3, 'seed': 42} if source.endswith('noise') else {'frequency': f0, 'amplitude': .3}
        for cutoff in sorted({min(fs*.4,max(40, f0 * 2)), min(fs * .4, f0 * 12), cutoff_hint}):
            for harmonic_filter in (False, True):
                chain = [
                    ('source', source, values, ''),
                    ('amp', 'gain', {'gain': 1}, 'ALI non-inverseur'),
                    ('lp', 'lowpass1', {'fc': cutoff}, 'Passe-bas RC'),
                ]
                if harmonic_filter:
                    chain.append(('comb', 'comb', {'frequency': f0, 'feedback': .95}, ''))
                chain.extend([
                    ('env', 'envelope', {'attack': features['attack'], 'onset': features['onset'], 'tau': tau}, ''),
                    ('out', 'output', {}, ''),
                ])
                patch = Patch(name='Soustractive', sample_rate=fs, duration=len(x)/fs,
                              nodes=[Block(id=i, type=k, parameters=p, label=label, position={'x': j*240, 'y': 0})
                                     for j, (i, k, p, label) in enumerate(chain)],
                              edges=[link(a[0], b[0]) for a, b in zip(chain, chain[1:])])
                raw = render(patch)
                denominator = max(float(np.linalg.norm(raw)), 1e-12)
                level = float(np.clip(np.linalg.norm(x)/denominator, 0, 4))
                projected = float(np.clip(np.dot(x, raw)/(denominator**2), 0, 4))
                for gain in sorted({level, level*.5, projected}):
                    trial = patch.model_copy(deep=True)
                    trial.nodes[1].parameters['gain'] = gain
                    y = render(trial)
                    errors = objective.components(y)
                    bands = band_errors(x, y, fs)
                    strict = all(errors[k] <= reference['errors'][k]+1e-12 for k in errors)
                    strict &= all(bands[k] <= reference['bands'][k]+1e-12 for k in bands)
                    within = errors['total'] <= reference['errors']['total']*(1+request.tolerance)+1e-12
                    if request.protect_texture:
                        within &= errors['attack'] <= max(reference['errors']['attack']*(1+request.tolerance), .01)+1e-12
                        within &= all(bands[k] <= max(reference['bands'][k]*(1+request.tolerance), .03)+1e-12 for k in bands)
                    rows.append({'patch': trial.model_dump(), 'errors': errors, 'bands': bands,
                                 'complexity': complexity(trial), 'modules': physical_count(trial),
                                 'score': errors['total']+request.complexity_penalty*complexity(trial),
                                 'strict': strict, 'within_tolerance': strict if request.strict else within})
    rows.sort(key=lambda row: (not row['within_tolerance'],
                               row['modules'] if row['within_tolerance'] else 0, row['score']))
    best = rows[0]
    return {**additive, 'patch': best['patch'] if best['within_tolerance'] else reference['patch'],
            'candidates': [reference, *rows[:11]], 'comparison': {'additive': reference, 'subtractive': best},
            'selection': 'Modèle soustractif retenu.' if best['within_tolerance'] else 'Version additive conservée.'}
