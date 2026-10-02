"""Bounded numerical optimization with retained best solution and cancellation."""
import numpy as np
from scipy import optimize
from .schema import OptimizeRequest
from .graph import render, validate
from .blocks import REGISTRY,parameters
from .metrics import Objective

class Finished(Exception): pass

def run_optimization(request: OptimizeRequest,x,progress,cancel):
    patch=request.patch.model_copy(deep=True); validate(patch)
    if patch.duration>12: raise ValueError('Optimisation limitée à une sélection de 12 secondes.')
    objective=Objective(x,patch.sample_rate,request.weights)
    selected=[]
    ordered=sorted(patch.nodes,key=lambda n:(0 if n.type=='gain' else 1 if n.id.startswith('impact-') else 2))
    for node in ordered:
        values=parameters(node.type,node.parameters,patch.sample_rate); node.parameters=values
        for key,value in values.items():
            identity=f'{node.id}:{key}'
            default=(key in ('amplitude','tau','gain','fc'))
            chosen = identity in request.parameter_ids if request.parameter_ids else (default and len(selected)<12)
            if chosen:
                spec=REGISTRY[node.type].parameters[key]
                low,high=spec.minimum,spec.maximum
                if key in ('fc','frequency'): high=min(high,patch.sample_rate*.49)
                # Local neighborhood, wide enough for refinement but bounded for scientific control.
                if value>0 and key not in ('phase','gain','sustain','seed'):
                    low=max(low,value*.5); high=min(high,value*2)
                if key=='seed': continue
                selected.append((node,key,low,high,value))
    if not selected: raise ValueError('Aucun paramètre optimisable sélectionné.')
    if len(selected)>24: raise ValueError('Sélectionner au plus 24 paramètres.')
    if request.parameter_ids and set(request.parameter_ids)-{f'{n.id}:{k}' for n,k,*_ in selected}: raise ValueError('Sélection de paramètres invalide.')
    initial=objective(render(patch)); best=initial; best_patch=patch.model_copy(deep=True)
    history=[initial]; evaluations=0; max_evaluations=min(400,request.max_iterations*12+1)
    def cost(v):
        nonlocal best,best_patch,evaluations
        if cancel.is_set() or evaluations>=max_evaluations: raise Finished()
        for u,(node,key,lo,hi,_) in zip(v,selected): node.parameters[key]=float(lo+np.clip(u,0,1)*(hi-lo))
        value=objective(render(patch)); evaluations+=1
        if value<best: best=value; best_patch=patch.model_copy(deep=True)
        history.append(best)
        progress({'initial':initial,'current':value,'best':best,'evaluations':evaluations,'budget':max_evaluations,'history':history.copy(),'parameters':[f'{n.id}:{k}' for n,k,*_ in selected]})
        return value
    v0=np.array([(v-lo)/(hi-lo) for _,_,lo,hi,v in selected])
    message='Budget atteint'; converged=False
    try:
        if request.method=='differential_evolution':
            result=optimize.differential_evolution(cost,[(0,1)]*len(selected),maxiter=request.max_iterations,popsize=4,polish=False,seed=42,x0=v0)
        else:
            result=optimize.minimize(cost,v0,method=request.method,bounds=[(0,1)]*len(selected),options={'maxiter':request.max_iterations})
        message=str(result.message); converged=bool(result.success)
    except Finished:
        message='Arrêt demandé ; meilleur modèle conservé.' if cancel.is_set() else 'Budget d’évaluations atteint ; meilleur modèle conservé.'
    return {'patch':best_patch.model_dump(),'initial':initial,'final':best,'history':history,'evaluations':evaluations,'converged':converged,'message':message,'parameters':[f'{n.id}:{k}' for n,k,*_ in selected],'bounds':[{'parameter':f'{n.id}:{k}','min':lo,'max':hi} for n,k,lo,hi,_ in selected]}
