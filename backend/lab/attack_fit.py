"""Calibrate a shared onset/attack while preserving each modal free decay.

The evaluation cache is transient computation only: exported patches contain
explicit oscillator parameters and never a cached or recorded waveform.
"""
import numpy as np
from .schema import Patch

def calibrate_attack(patch: Patch,objective):
    nodes=[n for n in patch.nodes if n.type=='modal']
    if not nodes or any(n.type not in ('modal','sum','gain','output') for n in patch.nodes):return patch,None
    onset=nodes[0].parameters['onset']; attack=nodes[0].parameters['attack']
    if any(n.parameters['onset']!=onset or n.parameters['attack']!=attack for n in nodes):return patch,None
    if any(n.type=='gain' and n.parameters.get('gain',1)!=1 for n in patch.nodes):return patch,None
    fs=patch.sample_rate;t=np.arange(round(fs*patch.duration))/fs
    free=np.zeros(len(t));u=t-onset
    for node in nodes:
        p=node.parameters
        free+=p['amplitude']*np.exp(-np.maximum(u,-.02)/p['tau'])*np.sin(2*np.pi*p['frequency']*u+p['phase'])
    starts=sorted(set([onset]+[max(0,onset+d) for d in (-.005,-.002,.002,.005,.01)]))
    attacks=sorted(set([attack,.0005,.0015,.003,.006,.012,.024,.04]))
    best=(float('inf'),onset,attack)
    for start in starts:
        if any(n.parameters['amplitude']*np.exp(-(start-onset)/n.parameters['tau'])>4 for n in nodes):continue
        v=np.maximum(0,t-start)
        for a in attacks:
            env=-np.expm1(-v/a)*(t>=start)
            error=objective(free*env)
            if error<best[0]:best=(error,start,a)
    cost,start,a=best
    fitted=patch.model_copy(deep=True)
    for node in fitted.nodes:
        if node.type!='modal':continue
        p=node.parameters;delta=start-p['onset']
        p['amplitude']=float(p['amplitude']*np.exp(-delta/p['tau']))
        p['phase']=float((p['phase']+2*np.pi*p['frequency']*delta+np.pi)%(2*np.pi)-np.pi)
        p['onset']=float(start);p['attack']=float(a)
        node.reason+=f' Attaque commune calibrée : début {start:.6f} s, constante {a:.6f} s ; fréquences et décroissances libres préservées.'
    return fitted,{'onset':start,'attack':a,'error':cost,'candidates':len(starts)*len(attacks),'method':'Recherche sur les paramètres d’attaque communs ; changement de phase/amplitude calculé pour conserver la réponse libre après attaque.'}
