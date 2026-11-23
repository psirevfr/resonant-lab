"""Bounded optimization of the connected graph, evaluated by the full DSP."""
import math

import numpy as np
from scipy import optimize

from .blocks import REGISTRY, parameters
from .graph import render, validate
from .metrics import Objective
from .schema import Block, Edge, OptimizeRequest

METHODS = ('Powell', 'L-BFGS-B', 'differential_evolution')
FILTERS = {'lowpass', 'highpass', 'lowpass1', 'highpass1', 'bandpass', 'notch', 'peak_eq',
           'sallen_key', 'mfb', 'svf_lowpass', 'svf_highpass', 'svf_bandpass', 'vcf'}
SHAPERS = {'saturation', 'asymmetric_saturation', 'clipper', 'wavefolder'}


class Finished(Exception):
    pass


def validate_request(request):
    patch = request.patch.model_copy(deep=True)
    nodes, _, outgoing, active, _ = validate(patch)
    if patch.duration > 12:
        raise ValueError('Optimisation limitée à une sélection de 12 secondes.')
    focus = set(request.focus_ids)
    focus.update(child for key in active if key in focus for child in outgoing[key] if nodes[child].type in FILTERS)
    explicit = set(request.parameter_ids)
    ordered = sorted((nodes[key] for key in active),
                     key=lambda node: (node.id not in focus, node.type not in SHAPERS|FILTERS|{'gain'}))
    selected = []
    for node in ordered:
        values = parameters(node.type, node.parameters, patch.sample_rate)
        node.parameters = values
        for key, value in values.items():
            if key == 'seed' or (explicit and f'{node.id}:{key}' not in explicit):
                continue
            if not explicit and node.id in ('keyboard-velocity', 'keyboard-adsr'):
                continue
            spec = REGISTRY[node.type].parameters[key]
            lo, hi = spec.minimum, spec.maximum
            if key in ('fc', 'frequency'):
                hi = max(value, min(hi, patch.sample_rate*.49))
            if key in ('gate', 'onset', 'seconds'):
                hi = min(hi, max(value, patch.duration))
            elif value > 0 and key in ('fc', 'frequency', 'q', 'tau', 'attack', 'decay', 'release'):
                lo, hi = max(lo, value*.5), min(hi, value*2)
            if hi > lo:
                selected.append((node, key, lo, hi, value))
    ids = {f'{node.id}:{key}' for node, key, *_ in selected}
    if explicit-ids:
        raise ValueError('Paramètre indisponible sur le trajet vers la sortie.')
    if not selected:
        raise ValueError('Aucun paramètre optimisable sur le trajet vers la sortie.')
    return patch, selected


def compensation_patch(patch):
    """At most one explicitly wired EQ after a saturation without a filter."""
    nodes, _, outgoing, active, _ = validate(patch)
    if len(nodes) >= 128 or len(patch.edges) >= 511:
        return None
    for key in active:
        if nodes[key].type not in SHAPERS or len(outgoing[key]) != 1:
            continue
        target = outgoing[key][0]
        if nodes[target].type in FILTERS:
            continue
        identifier = next((f'compensation-eq-{n}' for n in range(1, 129)
                           if f'compensation-eq-{n}' not in nodes), None)
        if identifier is None:
            return None
        p = patch.model_copy(deep=True)
        edge = next(e for e in p.edges if e.source == key and e.target == target)
        edge.target = identifier
        edge_id = identifier+'-out'
        while any(e.id == edge_id for e in p.edges):
            edge_id += '-eq'
        p.edges.append(Edge(id=edge_id, source=identifier, target=target))
        p.nodes.append(Block(id=identifier, type='peak_eq', label='Égaliseur de compensation',
                             parameters={'fc': 1500., 'q': .707, 'db': 0.},
                             position={'x': nodes[key].position.get('x', 0)+210,
                                       'y': nodes[key].position.get('y', 0)+80},
                             reason='Égaliseur proposé après saturation et conservé selon son gain mesuré.'))
        return p, key, identifier
    return None


def compensation_seeds(patch, eq, original, objective):
    """Estimate plausible EQ starting points from the measured spectral residual."""
    rendered = np.abs(np.fft.rfft(render(original)))
    frequencies = np.fft.rfftfreq(len(objective.x),1/patch.sample_rate)
    mask = (frequencies>=40)&(frequencies<=min(47000,patch.sample_rate*.45))
    residual = np.where(mask,np.abs(objective.fft-rendered),0.)
    for _ in range(3):
        index = int(np.argmax(residual))
        if residual[index]<=1e-9:
            break
        frequency = float(frequencies[index])
        db = float(np.clip(20*np.log10(max(objective.fft[index],1e-12)/max(rendered[index],1e-12)),-18,18))
        seed = patch.model_copy(deep=True)
        node = next(n for n in seed.nodes if n.id==eq)
        node.parameters = {'fc':frequency,'q':2.,'db':db}
        yield seed
        residual[np.abs(frequencies-frequency)<max(50.,.1*frequency)] = 0.


def run_optimization(request: OptimizeRequest, x, progress, cancel):
    patch, selected = validate_request(request)
    objective = Objective(x, patch.sample_rate, request.weights)
    initial = objective(render(patch))
    best, best_patch = initial, patch.model_copy(deep=True)
    parameter_names = [f'{n.id}:{k}' for n,k,*_ in selected]
    history, reports = [initial], []
    budget = min(400, max(request.max_iterations*12+1, min(len(selected)*6, 400)))
    methods = METHODS if request.method == 'compare' else (request.method,)
    total_budget = budget*len(methods)
    compensation = compensation_patch(patch) if request.compensate and not request.parameter_ids else None
    compensation_budget = min(96, max(36, budget//2)) if compensation else 0
    total_budget += compensation_budget

    def run_method(original, specs, method, limit, label, seeded_score=None, seed_evaluations=0):
        nonlocal best, best_patch
        work = original.model_copy(deep=True)
        score = initial if seeded_score is None else seeded_score
        attempts = 0
        best_local, local_patch = score, work.model_copy(deep=True)
        evaluated = set()
        iterations = 0
        converged_groups = 0
        group_size = 8 if len(specs)>12 else len(specs)
        groups = [specs[i:i+group_size] for i in range(0,len(specs),group_size)]
        for i, group in enumerate(groups):
            if cancel.is_set() or attempts+seed_evaluations >= limit:
                break
            allowance = attempts + max(1, (limit-seed_evaluations-attempts)//(len(groups)-i))
            work = local_patch.model_copy(deep=True)
            nodes = {n.id:n for n in work.nodes}
            group = [(nodes[n.id],key,lo,hi) for n,key,lo,hi,_ in group]
            v0 = np.array([(n.parameters[key]-lo)/(hi-lo) for n,key,lo,hi in group])
            def cost(v):
                nonlocal attempts, best_local, local_patch
                if cancel.is_set() or attempts >= allowance:
                    raise Finished()
                for u, (node,key,lo,hi) in zip(v,group):
                    node.parameters[key] = float(np.clip(lo+np.clip(u,0,1)*(hi-lo),lo,hi))
                attempts += 1
                evaluated.update(f'{n.id}:{key}' for u,start,(n,key,*_) in zip(v,v0,group) if abs(u-start)>1e-12)
                try:
                    value = objective(render(work))
                    if not math.isfinite(value):
                        value = 1e12
                except (ValueError, FloatingPointError):
                    value = 1e12
                if value < best_local:
                    best_local, local_patch = value, work.model_copy(deep=True)
                history.append(min(history[-1],best_local) if label!='compensation' else history[-1])
                if attempts==1 or attempts%5==0:
                    progress({'initial':initial,'current':value,'best':history[-1], 'method':method,
                              'evaluations':sum(row['evaluations'] for row in reports)+attempts+seed_evaluations,
                              'budget':total_budget,'history':history.copy(),'parameters':parameter_names})
                return value
            def iteration(*_):
                nonlocal iterations
                iterations+=1
            try:
                # Give each knob a measured perturbation before a solver can
                # spend the group budget on a single line search.
                for axis in range(len(group)):
                    proposal=v0.copy()
                    proposal[axis]+=.12 if proposal[axis]<=.88 else -.12
                    cost(proposal)
                values={node.id:node.parameters for node in local_patch.nodes}
                start=np.array([(values[n.id][key]-lo)/(hi-lo) for n,key,lo,hi in group])
                if method == 'differential_evolution':
                    result = optimize.differential_evolution(cost, [(0,1)]*len(group), maxiter=request.max_iterations,
                                                    popsize=3, polish=False, seed=42, x0=start, callback=iteration)
                else:
                    result = optimize.minimize(cost, start, method=method, bounds=[(0,1)]*len(group),
                                      options={'maxiter':request.max_iterations}, callback=iteration)
                converged_groups+=bool(result.success)
            except Finished:
                pass
        if label!='compensation' and best_local<best:
            best, best_patch = best_local, local_patch
        reports.append({'method':method,'stage':label,'error':best_local,
                        'evaluations':attempts+seed_evaluations,'iterations':iterations,
                        'tested_parameters':len(evaluated),'converged':converged_groups==len(groups)})
        return best_local, local_patch

    for method in methods:
        if cancel.is_set():
            break
        run_method(patch,selected,method,budget,'montage')
    compensation_retained = False
    if compensation and not cancel.is_set() and best>1e-9:
        # Apply the same connection to the best existing fit, preserving its réglages.
        proposal = compensation_patch(best_patch)
        if proposal:
            with_eq, source, eq = proposal
            seed_score = best
            seed_evaluations = 0
            for seed in compensation_seeds(with_eq,eq,best_patch,objective):
                if cancel.is_set():
                    break
                seed_evaluations+=1
                history.append(history[-1])
                try:score=objective(render(seed))
                except (ValueError,FloatingPointError):continue
                if score<seed_score:
                    seed_score,with_eq=score,seed
            expanded, specs = validate_request(request.model_copy(update={
                'patch':with_eq, 'focus_ids':[eq,source],
            }))
            local_specs = [item for item in specs if item[0].id in (eq,source)]
            winner = min(reports,key=lambda row:row['error'])['method']
            extra, result = run_method(expanded,local_specs,winner,compensation_budget,'compensation',seed_score,seed_evaluations)
            if best-extra > max(best*.01,1e-9):
                best, best_patch = extra, result
                compensation_retained = True
                history.append(best)
    desc = 'Arrêt demandé ; meilleur modèle conservé.' if cancel.is_set() else 'Meilleur modèle mesuré dans le budget conservé.'
    return {'patch':best_patch.model_dump(),'initial':initial,'final':best,'history':history,
            'evaluations':sum(row['evaluations'] for row in reports),
            'converged':any(row['converged'] and row['error']==best for row in reports),'message':desc,
            'parameters':parameter_names,
            'bounds':[{'parameter':f'{n.id}:{k}','min':lo,'max':hi} for n,k,lo,hi,_ in selected],
            'methods':reports, 'compensation_retained':compensation_retained}
