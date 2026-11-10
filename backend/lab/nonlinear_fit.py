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
from .instrument import physical_count


def architecture(source,style):
    p=source.model_copy(deep=True)
    out=next(n.id for n in p.nodes if n.type=='output')
    upstream=next(e.source for e in p.edges if e.target==out)
    modes=[n for n in p.nodes if n.type=='modal']
    f=min(n.parameters['frequency'] for n in modes)
    p.edges=[e for e in p.edges if e.target!=out]
    shared=style in ('excitation-partagee','excitation-resonante')
    if shared:
        # Enrich a periodic carrier BEFORE its amplitude envelope. Saturating an
        # already decaying sine makes its harmonics decay at different rates.
        # This is a different, explicit topology, not a hidden oscillator bank.
        from .instrument import phase_wrap
        weights=np.array([n.parameters['amplitude']**2 for n in modes])+1e-15
        tau=float(np.exp(np.average(np.log([n.parameters['tau'] for n in modes]),weights=weights)))
        attack=modes[0].parameters['attack'];onset=modes[0].parameters['onset']
        if any(n.parameters['attack']!=attack or n.parameters['onset']!=onset for n in modes):
            raise ValueError('Excitation partagée : attaque et début communs requis.')
        for n in modes:
            v=n.parameters;n.type='oscillator'
            n.parameters={k:v[k] for k in ('frequency','amplitude','phase')}
            n.parameters['phase']=phase_wrap(v['phase']-2*np.pi*v['frequency']*onset)
            n.label='Oscillateur sinusoïdal'
            n.reason='Source périodique explicite. La saturation crée ses harmoniques ; une enveloppe commune règle ensuite l’attaque et la décroissance.'
    shapes={
      'couleur': [('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('lowpass1',{'fc':min(f*8,p.sample_rate*.4)})],
      'resonance': [('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('highpass',{'fc':max(20,f*.2),'q':.707}),('peak_eq',{'fc':min(f*3,p.sample_rate*.35),'q':2,'db':4}),('lowpass',{'fc':min(f*9,p.sample_rate*.4),'q':.707})],
      'pre-filtre': [('lowpass1',{'fc':min(f*5,p.sample_rate*.4)}),('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('peak_eq',{'fc':min(f*2,p.sample_rate*.35),'q':1,'db':-4}),('lowpass',{'fc':min(f*10,p.sample_rate*.4),'q':.707})],
      'parallele': [('asymmetric_saturation',{'drive':12,'bias':.8,'mix':1,'level':.08}),('highpass',{'fc':min(f*2.4,p.sample_rate*.35),'q':.707}),('lowpass',{'fc':min(f*10,p.sample_rate*.4),'q':.707})],
      'excitation-partagee': [('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('lowpass1',{'fc':min(f*8,p.sample_rate*.4)})],
      'excitation-resonante': [('asymmetric_saturation',{'drive':4,'bias':.8,'mix':1,'level':.3}),('highpass',{'fc':max(5,min(f*.2,p.sample_rate*.4)),'q':.707}),('peak_eq',{'fc':min(f*3,p.sample_rate*.35),'q':2,'db':4})],
    }
    parent=upstream
    if style=='parallele':
        # Reuse a real existing source for the added harmonic branch.
        parent=max(modes,key=lambda n:n.parameters['amplitude']**2*n.parameters['tau']).id
    for i,(kind,values) in enumerate(shapes[style]):
        nid=f'nl-{i}';p.nodes.append(Block(id=nid,type=kind,parameters=values,label={'asymmetric_saturation':'Création d’harmoniques ×4','peak_eq':'Correction des harmoniques'}.get(kind,''),position={'x':600+220*i,'y':350},reason='Traitement réel ajusté dans une recherche de topologie globale ; paramètres libres explicitement bornés, décision finale sur le rendu à la fréquence originale.'))
        p.edges.append(link(parent,nid));parent=nid
    if shared:
        p.nodes.append(Block(id='nl-envelope',type='envelope',parameters={'attack':attack,'onset':onset,'tau':tau},label='Enveloppe exponentielle / VCA',position={'x':600+220*len(shapes[style]),'y':350},reason='Attaque et décroissance communes après création et filtrage des harmoniques. Bloc réellement exécuté, compté séparément.'))
        p.edges.append(link(parent,'nl-envelope'));parent='nl-envelope'
    if style=='parallele':
        p.nodes.append(Block(id='nl-mix',type='sum',label='Direct + harmoniques',position={'x':1500,'y':150}))
        p.edges.extend([link(upstream,'nl-mix'),link(parent,'nl-mix')]);parent='nl-mix'
    p.edges.append(link(parent,out));next(n for n in p.nodes if n.id==out).position={'x':1740,'y':150}
    names={'excitation-partagee':'sinus → saturation ×4 → passe-bas → enveloppe','excitation-resonante':'sinus → saturation ×4 → passe-haut → égaliseur → enveloppe'}
    p.name=(f'{len(modes)} sources · '+names[style]) if shared else f'{len(modes)} sources · {style} non linéaire'
    validate(p);return p


def fit_architecture(p,x,weights,budget=220):
    fs=p.sample_rate
    highest=max(n.parameters['frequency'] for n in p.nodes if n.type in ('modal','oscillator'))
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
        if n.type in ('modal','oscillator'):
            # Sources are jointly readjusted, rather than a fixed bank followed
            # by a cosmetic filter. Phase and decay remain explicit per source.
            variable(k,'amplitude',max(.00001,v['amplitude']*.2),min(4,max(.01,v['amplitude']*3)),True)
            variable(k,'phase',-np.pi,np.pi)
            variable(k,'frequency',max(1,v['frequency']-2),min(47000,fs/2-1e-6,v['frequency']+2))
            if n.type=='modal':variable(k,'tau',max(.005,v['tau']*.5),min(30,v['tau']*2),True)
        elif n.type=='envelope':
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
    # Give the processing its own budget: a large source bank otherwise exhausts
    # Powell's evaluations before drive, bias and filter controls are visited.
    processing=[i for i,(k,_,_) in enumerate(variables) if nodes[k].type not in ('modal','oscillator')]
    stage_budget=max(20,budget//2)
    anchor=best[1].copy()
    def processing_cost(z):
        proposal=anchor.copy();proposal[processing]=z
        return cost(proposal)
    optimize.minimize(processing_cost,anchor[processing],method='Powell',bounds=[bounds[i] for i in processing],options={'maxfev':stage_budget,'maxiter':4,'xtol':.003,'ftol':.0003})
    optimize.minimize(cost,best[1],method='Powell',bounds=bounds,options={'maxfev':max(15,budget-stage_budget),'maxiter':5,'xtol':.003,'ftol':.0003})
    decode(best[1]);q=p.model_copy(deep=True)
    for node in q.nodes:node.parameters=values[node.id]
    validate(q)
    return q,{'evaluations_budget':budget,'analysis_rate':rate,'sources':sum(n.type in ('modal','oscillator') for n in q.nodes),'architecture':p.name}


def refine_shared(p,x,objective):
    """Bounded full-rate waveform refinement for the small shared excitation.

    This least-squares criterion proposes parameters only. Acceptance still uses
    the unchanged multi-term Objective, including attack and spectrogram.
    """
    q=p.model_copy(deep=True);variables=[];initial=[];lo=[];hi=[]
    for node in q.nodes:
        for key in node.parameters:
            value=node.parameters[key]
            bounds=None;log=False
            if node.type=='oscillator':
                if key=='frequency':bounds=(max(1,value-2),min(47000,q.sample_rate*.49,value+2))
                elif key=='phase':bounds=(-np.pi,np.pi)
            elif node.type=='asymmetric_saturation':
                if key=='drive':bounds=(.1,60);log=True
                elif key=='bias':bounds=(-3,3)
                elif key=='level':bounds=(.00001,4);log=True
            elif node.type in ('lowpass1','highpass','peak_eq'):
                if key=='fc':bounds=(max(5,value*.5),min(47000,q.sample_rate*.49,value*2));log=True
                elif key=='q':bounds=(.3,8)
                elif key=='db':bounds=(-24,24)
            elif node.type=='envelope' and key=='tau':bounds=(max(.005,value*.5),min(30,value*2));log=True
            if bounds is None or bounds[0]>=bounds[1]:continue
            lower,upper=bounds
            variables.append((node,key,log));initial.append(np.log(value) if log else value)
            lo.append(np.log(lower) if log else lower);hi.append(np.log(upper) if log else upper)
    # Bound the dense numerical Jacobian as for the modal fitting path.
    if len(x)*len(variables)>8_000_000:return p,0
    scale=max(np.linalg.norm(x),1e-12);calls=0
    def residual(z):
        nonlocal calls
        calls+=1
        for (node,key,log),v in zip(variables,z):node.parameters[key]=float(np.exp(v) if log else v)
        return (render(q)-x)/scale
    fit=optimize.least_squares(residual,np.clip(initial,lo,hi),bounds=(lo,hi),max_nfev=45,ftol=1e-6,xtol=1e-6,gtol=1e-6,x_scale='jac')
    residual(fit.x)
    return (q if objective(render(q))<objective(render(p)) else p),calls


def search(proposals,x,weights,objective,budget=220):
    candidates=[];diagnostics=[]
    for source in proposals:
        count=sum(n.type=='modal' for n in source.nodes)
        styles=('couleur','resonance','pre-filtre') if count in (1,2,3,4) else ('parallele',) if count in (6,8) else ()
        if count in (1,2):styles+=('excitation-partagee','excitation-resonante')
        for style in styles:
            seed=architecture(source,style)
            fitted,info=fit_architecture(seed,x,weights,budget)
            # Both seed and fit are scored at full rate: analysis resampling
            # cannot cause an unchecked regression in the final decision.
            a=objective(render(seed));b=objective(render(fitted));chosen=fitted if b<a else seed
            refinement_calls=0
            if style in ('excitation-partagee','excitation-resonante') and min(a,b)>1e-10:
                chosen,refinement_calls=refine_shared(chosen,x,objective)
            candidates.append(chosen);diagnostics.append({**info,'full_rate_error':objective(render(chosen)),'seed_error':a,'fitted_error':b,'full_rate_refinement_calls':refinement_calls,'blocks':physical_count(chosen)})
    return candidates,diagnostics
