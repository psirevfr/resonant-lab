"""Search small executable source → nonlinearity → filter architectures.

No embedded modal bank, no recorded waveform. A reduced-rate search only makes
proposals; their acceptance always uses the full-rate render and full objective.
"""
import numpy as np
from scipy import optimize,signal
from .schema import Block,Patch
from .blocks import parameters,process
from .identify import link
from .graph import render,validate


def architecture(source,style):
    p=source.model_copy(deep=True)
    out=next(n.id for n in p.nodes if n.type=='output')
    upstream=next(e.source for e in p.edges if e.target==out)
    modes=[n for n in p.nodes if n.type=='modal']
    f=min(n.parameters['frequency'] for n in modes)
    p.edges=[e for e in p.edges if e.target!=out]
    shapes={
      'couleur': [('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('lowpass1',{'fc':min(f*8,p.sample_rate*.4)})],
      'resonance': [('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('highpass',{'fc':max(20,f*.2),'q':.707}),('peak_eq',{'fc':min(f*3,p.sample_rate*.35),'q':2,'db':4}),('lowpass',{'fc':min(f*9,p.sample_rate*.4),'q':.707})],
      'pre-filtre': [('lowpass1',{'fc':min(f*5,p.sample_rate*.4)}),('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('peak_eq',{'fc':min(f*2,p.sample_rate*.35),'q':1,'db':-4}),('lowpass',{'fc':min(f*10,p.sample_rate*.4),'q':.707})],
      'parallele': [('asymmetric_saturation',{'drive':12,'bias':.8,'mix':1,'level':.08}),('highpass',{'fc':min(f*2.4,p.sample_rate*.35),'q':.707}),('lowpass',{'fc':min(f*10,p.sample_rate*.4),'q':.707})],
    }
    parent=upstream
    if style=='parallele':
        # Reuse a real existing source for the added harmonic branch.
        parent=max(modes,key=lambda n:n.parameters['amplitude']**2*n.parameters['tau']).id
    for i,(kind,values) in enumerate(shapes[style]):
        nid=f'nl-{i}';p.nodes.append(Block(id=nid,type=kind,parameters=values,label={'asymmetric_saturation':'Création d’harmoniques ×4','peak_eq':'Correction des harmoniques'}.get(kind,''),position={'x':600+220*i,'y':350},reason='Traitement réel ajusté dans une recherche de topologie globale ; paramètres libres explicitement bornés, décision finale sur le rendu à la fréquence originale.'))
        p.edges.append(link(parent,nid));parent=nid
    if style=='parallele':
        p.nodes.append(Block(id='nl-mix',type='sum',label='Direct + harmoniques',position={'x':1500,'y':150}))
        p.edges.extend([link(upstream,'nl-mix'),link(parent,'nl-mix')]);parent='nl-mix'
    p.edges.append(link(parent,out));next(n for n in p.nodes if n.id==out).position={'x':1740,'y':150}
    p.name=f'{len(modes)} sources · {style} non linéaire'
    validate(p);return p


def fit_architecture(p,x,weights,budget=220):
    fs=p.sample_rate
    highest=max(n.parameters['frequency'] for n in p.nodes if n.type=='modal')
    down=max(1,min(4,int(fs/(highest*2.8))))
    rate=fs/down
    target=signal.resample_poly(x,1,down) if down>1 else x
    # Use the same metrics on a reduced buffer for bounded search time.
    from .metrics import Objective
    obj=Objective(target,rate,weights)
    nodes,inc,_,order,out=validate(p)
    values={k:parameters(nodes[k].type,nodes[k].parameters,fs) for k in order}
    variables=[];bounds=[];initial=[]
    def variable(k,key,lo,hi,log=False):
        value=values[k][key]
        if log:lo,hi,value=np.log(lo),np.log(hi),np.log(max(value,lo))
        variables.append((k,key,log));bounds.append((lo,hi));initial.append(float(np.clip(value,lo,hi)))
    for k in order:
        n=nodes[k];v=values[k]
        if n.type=='modal':
            # Sources are jointly readjusted, rather than a fixed bank followed
            # by a cosmetic filter. Phase and decay remain explicit per source.
            variable(k,'amplitude',max(.00001,v['amplitude']*.2),min(4,max(.01,v['amplitude']*3)),True)
            variable(k,'phase',-np.pi,np.pi)
            variable(k,'frequency',max(1,v['frequency']-2),min(47000,fs/2-1e-6,v['frequency']+2))
            variable(k,'tau',max(.005,v['tau']*.5),min(30,v['tau']*2),True)
        elif n.type=='asymmetric_saturation':
            variable(k,'drive',.2,60,True);variable(k,'bias',-2.5,2.5);variable(k,'level',.002,4,True)
        elif n.type in ('lowpass','lowpass1','highpass','peak_eq'):
            variable(k,'fc',max(5,min(v['fc']*.3,rate*.4)),min(rate*.45,max(v['fc']*2.5,50)),True)
            if n.type=='peak_eq':variable(k,'db',-24,24);variable(k,'q',.3,8,True)
            elif n.type in ('highpass','lowpass'):variable(k,'q',.5,2,True)
    best=[float('inf'),np.array(initial)]
    def decode(z):
        for (k,key,log),v in zip(variables,z):values[k][key]=float(np.exp(v) if log else v)
    def cost(z):
        decode(z);buffers={}
        for k in order:buffers[k]=process(nodes[k].type,values[k],[buffers[a] for a in inc[k]],rate,len(target))
        value=obj(buffers[out])
        if value<best[0]:best[:]=[value,z.copy()]
        return value
    initial=np.array(initial);cost(initial)
    # Coarse drives/asymmetries guard against the near-linear local solution.
    di=next(i for i,v in enumerate(variables) if v[1]=='drive');bi=next(i for i,v in enumerate(variables) if v[1]=='bias')
    for drive in (2,12,45):
        for bias in (0,.8,1.8):
            z=initial.copy();z[di]=np.log(drive);z[bi]=bias;cost(z)
    optimize.minimize(cost,best[1],method='Powell',bounds=bounds,options={'maxfev':budget,'maxiter':5,'xtol':.003,'ftol':.0003})
    decode(best[1]);q=p.model_copy(deep=True)
    for node in q.nodes:node.parameters=values[node.id]
    validate(q)
    return q,{'evaluations_budget':budget,'analysis_rate':rate,'sources':sum(n.type=='modal' for n in q.nodes),'architecture':p.name}


def search(proposals,x,weights,objective,budget=220):
    candidates=[];diagnostics=[]
    for source in proposals:
        count=sum(n.type=='modal' for n in source.nodes)
        styles=('couleur','resonance','pre-filtre') if count in (1,2,3,4) else ('parallele',) if count in (6,8) else ()
        for style in styles:
            seed=architecture(source,style)
            fitted,info=fit_architecture(seed,x,weights,budget)
            # Both seed and fit are scored at full rate: analysis resampling
            # cannot cause an unchecked regression in the final decision.
            a=objective(render(seed));b=objective(render(fitted));chosen=fitted if b<a else seed
            candidates.append(chosen);diagnostics.append({**info,'full_rate_error':min(a,b),'seed_error':a,'fitted_error':b,'blocks':len(chosen.nodes)})
    return candidates,diagnostics
