"""One optional contextual bandit trial, scored by the normal synthesis objective."""
import math

import numpy as np
from scipy.optimize import least_squares

from .blocks import adsr_envelope, exponential
from .schema import Block, Patch

LEARNING_VERSION = 1
PROFILES = ('transient', 'sustained', 'decaying')
STRATEGIES = ('adsr', 'decay')


def sound_profile(features, duration):
    times = np.asarray(features['envelope']['time'])
    amplitude = np.asarray(features['envelope']['amplitude'])
    u = duration - features['onset']
    active = amplitude[times >= features['onset']]
    if not active.size or active.max() <= 0:
        return 'decaying'
    active = active / active.max()
    early = max(1, round(len(active)*.2))
    if u <= .18 or (float(np.mean(active[early:])) if early < len(active) else 0) < .12:
        return 'transient'
    middle = active[len(active)//3:max(len(active)//3+1, 2*len(active)//3)]
    if float(np.median(middle)) >= .5:
        return 'sustained'
    return 'decaying'


def select_strategy(profile, history):
    order = STRATEGIES if profile == 'sustained' else STRATEGIES[::-1]
    if not isinstance(history, dict):
        return order[0]
    table = history.get(profile)
    scores = {}
    for arm in order:
        row = table.get(arm) if isinstance(table, dict) else None
        if not isinstance(row, dict):
            continue
        count, reward = row.get('count'), row.get('reward')
        if type(count) is int and 1 <= count <= 128 and type(reward) in (int,float) and 0 <= reward <= count:
            scores[arm] = (count, reward)
    if len(scores) < len(order):
        unknown = [arm for arm in order if arm not in scores]
        community = history.get('_community')
        group = community.get(profile) if isinstance(community, dict) else None
        prior = {}
        for arm in order:
            row = group.get(arm) if isinstance(group, dict) else None
            if not isinstance(row, dict):
                continue
            count, mean = row.get('contributors'), row.get('mean')
            if type(count) is int and count >= 5 and type(mean) in (int,float) and 0 < mean <= 1:
                prior[arm] = mean
        if prior:
            preferred = max(prior, key=prior.get)
            if history.get('_explore') is True:
                return next((arm for arm in unknown if arm != preferred), unknown[0])
            return preferred
        if history.get('_explore') is True and len(unknown) == len(order):
            return unknown[1]
        return unknown[0]
    total = sum(count for count, _ in scores.values())
    return max(order, key=lambda arm: scores[arm][1]/scores[arm][0]+.25*math.sqrt(math.log(total)/scores[arm][0]))


def fit_envelope(kind, envelope, fs, attack_hint):
    peak = np.max(envelope)
    if peak <= 0:
        return None
    duration = len(envelope)/fs
    indices = np.linspace(0, len(envelope)-1, min(1024, len(envelope)), dtype=int)
    t, y = indices/fs, envelope[indices]/peak
    attack = float(np.clip(attack_hint, 1/fs, min(5., duration*.9)))
    if kind == 'decay':
        def curve(v, points):
            return exponential(points, v[0], v[1])
        bounds = ([1/fs, .005], [min(5., duration), 30.])
        initial = [attack, min(30., max(.005, duration*.4))]
        names = ['attack', 'tau']
    else:
        def curve(v, points):
            return adsr_envelope(points, *v, fs)
        middle = float(np.median(y[len(y)//4:len(y)//2]))
        sustain = float(np.clip(middle, .05, .99))
        tail = np.flatnonzero((t >= .5*duration) & (y < .8*sustain))
        gate = min(duration, max(.001, float(t[tail[0]]) if len(tail) else duration))
        bounds = ([1/fs, .001, 0., 0., .001], [min(5., duration), 10., 1., duration, 10.])
        initial = [attack, min(10., max(.001, duration*.15)), sustain, gate,
                   min(10., max(.001, duration-gate))]
        names = ['attack', 'decay', 'sustain', 'gate', 'release']
    result = least_squares(lambda values: curve(values, t)-y, initial, bounds=bounds, max_nfev=36)
    return dict(zip(names, map(float, result.x))), lambda points: curve(result.x, points)


def envelope_candidate(x, fs, features, objective, strategy, budget):
    """Fit one common envelope and project the measured frequencies onto it."""
    from .identify import link

    onset = round(features['onset']*fs)
    if onset > fs*2 or len(x)-onset < 64:
        return None
    room = budget-2-bool(onset)
    max_modes = min(12, room-1 if room > 2 else min(room, 1))
    if max_modes < 1:
        return None
    partials = sorted(features['partials'], key=lambda p: p['amplitude']**2, reverse=True)[:max_modes]
    if not partials:
        return None
    fit = fit_envelope(strategy, objective.env[onset:], fs, 3*features['attack'])
    if fit is None:
        return None
    params, env = fit
    # Sample over the whole selection, including the attack and release.
    active = x[onset:]
    i = np.linspace(0, len(active)-1, min(8192, len(active)), dtype=int)
    t = i/fs
    angles = 2*np.pi*t[:, None]*np.array([p['frequency'] for p in partials])
    design = np.column_stack((np.sin(angles), np.cos(angles)))*env(t)[:, None]
    coefs = np.linalg.lstsq(design, active[i], rcond=1e-8)[0].reshape(2, -1)
    nodes = []
    for j, (partial, (sine, cosine)) in enumerate(zip(partials, coefs.T)):
        nodes.append(Block(id=f'sinus-{j}', type='oscillator', parameters={
            'frequency': partial['frequency'], 'amplitude': float(np.clip(np.hypot(sine, cosine), 0, 4)),
            'phase': float(np.arctan2(cosine, sine))},
            position={'x': 0, 'y': 110*j}))
    edges = []
    source = nodes[0].id
    if len(nodes)>1:
        edges = [link(node.id, 'mix') for node in nodes]
        nodes.append(Block(id='mix', type='sum', position={'x': 250, 'y': 0}))
        source = 'mix'
    kind = 'adsr' if strategy == 'adsr' else 'envelope'
    label = 'ADSR partagée' if kind == 'adsr' else 'Décroissance partagée'
    nodes.extend([Block(id='shape', type=kind, parameters=params, position={'x': 500, 'y': 0},
                        reason='Enveloppe commune estimée sur le WAV. Fréquences mesurées, amplitudes et phases recalées sur le signal.'),
                  Block(id='out', type='output', position={'x': 1000, 'y': 0})])
    edges.append(link(source, 'shape'))
    if onset:
        nodes.append(Block(id='align', type='delay', parameters={'seconds': onset/fs}, position={'x': 750, 'y': 0}))
        edges.extend([link('shape', 'align'), link('align', 'out')])
    else:
        edges.append(link('shape', 'out'))
    return Patch(name=label, sample_rate=fs, duration=len(x)/fs, nodes=nodes, edges=edges)


def adaptive_reward(baseline, candidate):
    if candidate is None or candidate['modules'] > baseline['modules']:
        return 0.
    for group in ('errors', 'bands'):
        if any(not math.isfinite(candidate[group][k]) or candidate[group][k] > v+1e-12
               for k, v in baseline[group].items()):
            return 0.
    before = baseline['errors']['total']
    improvement = before-candidate['errors']['total']
    saved = baseline['modules']-candidate['modules']
    if improvement <= 1e-12 and not saved:
        return 0.
    return min(1., .75*max(0., improvement)/max(before, 1e-12)+.25*saved/baseline['modules'])
