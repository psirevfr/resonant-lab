"""Measured modal sparsification. Never hides a bank of oscillators in one block.

Sparse group selection and joint fitting use a bounded analysis buffer. Every
proposal is scored at the original sample rate through the actual DSP graph.
The input patch is retained as a candidate and as the fallback.
"""
import numpy as np
from scipy import optimize, signal
from .schema import Patch, Block, Edge
from .blocks import parameters, process, REGISTRY
from .graph import render, validate
from .metrics import Objective
from .identify import modal_patch, link, complexity
from .attack_fit import calibrate_attack
from .instrument import collapse_modes,physical_count
from .texture import band_errors,fit_texture


def tidy(patch):
    """Remove identity gains and one-input sums, preserving executed audio."""
    p=patch.model_copy(deep=True)
    changed=True
    while changed:
        changed=False
        for node in p.nodes:
            incoming=[e for e in p.edges if e.target==node.id]
            identity=(node.type=='gain' and node.parameters.get('gain',1)==1) or node.type=='sum'
            if identity and len(incoming)==1:
                source=incoming[0].source
                p.edges=[Edge(id=f'{source}-{e.target}',source=source,target=e.target) if e.source==node.id else e for e in p.edges if e.target!=node.id]
                p.nodes=[n for n in p.nodes if n.id!=node.id];changed=True;break
    # Identical modes feeding only the same sum can be merged algebraically.
    # No approximation, and no hidden sources: only the amplitude is combined.
    for a in list(p.nodes):
        if a.type!='modal' or a not in p.nodes:continue
        pa=parameters(a.type,a.parameters,p.sample_rate)
        outgoing=[e.target for e in p.edges if e.source==a.id]
        if len(outgoing)!=1 or next(n.type for n in p.nodes if n.id==outgoing[0])!='sum':continue
        for b in list(p.nodes):
            if b.id==a.id or b.type!='modal':continue
            pb=parameters(b.type,b.parameters,p.sample_rate)
            if [e.target for e in p.edges if e.source==b.id]!=outgoing:continue
            if any(pa[k]!=pb[k] for k in pa if k!='amplitude'):continue
            if pa['amplitude']+pb['amplitude']>4:continue
            pa['amplitude']+=pb['amplitude'];a.parameters=pa.copy()
            p.nodes.remove(b);p.edges=[e for e in p.edges if e.source!=b.id]
    if any(n.type=='sum' and sum(e.target==n.id for e in p.edges)==1 for n in p.nodes):
        return tidy(p)
    # Re-layout the compact graph without touching its DSP.
    modes=[n for n in p.nodes if n.type=='modal']
    for i,n in enumerate(modes):n.position={'x':30+240*(i//6),'y':30+115*(i%6)}
    rest=[n for n in p.nodes if n.type!='modal']
    for i,n in enumerate(rest):n.position={'x':300+240*((max(1,len(modes))-1)//6)+220*i,'y':230}
    validate(p)
    return p


def analysis_basis(x,fs,modes):
    # Up to ~12 kHz analysis rate when all candidate modes permit it. All actual
    # decisions still use full-rate Objective/render; no downsampled score escapes.
    highest=max(n.parameters['frequency'] for n in modes)
    down=max(1,min(4,int(fs/(highest*2.5))))
    target=signal.resample_poly(x,1,down) if down>1 else x
    if len(target)*2*len(modes)>8_000_000:
        raise ValueError('Simplification trop volumineuse : réduire la sélection ou le nombre de modes (8 millions de coefficients).')
    t=np.arange(len(target))*down/fs
    columns=[]
    for node in modes:
        p=node.parameters;u=np.maximum(0,t-p['onset'])
        env=np.exp(-u/p['tau'])*(-np.expm1(-u/p['attack']) if p['attack']>0 else 1)*(t>=p['onset'])
        columns.extend((env*np.sin(2*np.pi*p['frequency']*u),env*np.cos(2*np.pi*p['frequency']*u)))
    return np.array(columns).T,target,down


def joint_fit(patch,x,objective,down):
    """Analytic Jacobian for shared-bank least squares, bounded to 45 trials."""
    p=patch.model_copy(deep=True);nodes=[n for n in p.nodes if n.type=='modal'];count=len(nodes)
    values=[n.parameters for n in nodes];onset=values[0]['onset'];attack=values[0]['attack']
    target=signal.resample_poly(x,1,down) if down>1 else x
    t=np.arange(len(target))*down/p.sample_rate;mask=t>=onset+.004;u=t[mask]-onset;target=target[mask]
    if len(target)<count*4:return p
    f=np.array([v['frequency'] for v in values]);amp=np.array([v['amplitude'] for v in values]);phase=np.array([v['phase'] for v in values]);tau=np.array([v['tau'] for v in values])
    env=-np.expm1(-u[:,None]/attack) if attack>0 else np.ones((len(u),1))
    scale=max(np.linalg.norm(target),1e-12)
    def calculate(z,jac=False):
        a,b,df,lt=z.reshape(4,count);decay=np.exp(lt)
        e=np.exp(-u[:,None]/decay)*env;angle=2*np.pi*u[:,None]*(f+df)
        sn=np.sin(angle);cs=np.cos(angle);terms=e*(a*sn+b*cs)
        if jac:return np.column_stack((e*sn,e*cs,e*(a*cs-b*sn)*2*np.pi*u[:,None],terms*u[:,None]/decay))/scale
        return (terms.sum(axis=1)-target)/scale
    low_f=np.maximum(-3,1-f);high_f=np.minimum(3,min(47000,p.sample_rate/2-1e-6)-f)
    init=np.r_[amp*np.cos(phase),amp*np.sin(phase),np.zeros(count),np.log(tau)]
    bounds=(np.r_[np.full(count*2,-4),low_f,np.full(count,np.log(.005))],np.r_[np.full(count*2,4),high_f,np.full(count,np.log(30))])
    fit=optimize.least_squares(calculate,init,jac=lambda z:calculate(z,True),bounds=bounds,max_nfev=45,ftol=1e-6,xtol=1e-6,gtol=1e-6,x_scale='jac')
    a,b,df,lt=fit.x.reshape(4,count)
    if np.any(np.hypot(a,b)>4):return patch
    for i,node in enumerate(nodes):
        node.parameters.update(amplitude=float(np.hypot(a[i],b[i])),phase=float(np.arctan2(b[i],a[i])),frequency=float(f[i]+df[i]),tau=float(np.exp(lt[i])))
    # The fitting criterion is only a proposal; keep it solely on actual full cost.
    if objective(render(p))>=objective(render(patch)):return patch
    return p


def shaping(patch,objective):
    """Test actual tanh + second-order LP + gain; return only an improvement."""
    fs=patch.sample_rate;y=render(patch);initial=objective(y);best=[initial,None]
    def cost(v):
        z=np.tanh(v[0]*y)
        z=process('lowpass',{'fc':float(np.exp(v[1])),'q':v[2]},[z],fs,len(y))*v[3]
        error=objective(z)
        if error<best[0]:best[:]=[error,v.copy()]
        return error
    optimize.minimize(cost,[1,np.log(fs*.45),.707,1],method='Powell',bounds=[(.1,20),(np.log(500),np.log(fs*.49)),(.5,2),(.02,4)],options={'maxfev':120,'maxiter':3})
    if best[1] is None:return None
    drive,log_fc,q,gain=best[1];p=patch.model_copy(deep=True);out=next(n.id for n in p.nodes if n.type=='output');source=next(e.source for e in p.edges if e.target==out)
    p.edges=[e for e in p.edges if e.target!=out]
    p.nodes.extend([Block(id='compact-saturation',type='saturation',parameters={'drive':float(drive)},reason='Saturation de sortie testée par comparaison du coût réel ; sans suréchantillonnage.'),Block(id='compact-lowpass',type='lowpass',parameters={'fc':float(np.exp(log_fc)),'q':float(q)},reason='Passe-bas de sortie ajusté conjointement à la saturation et au gain.'),Block(id='compact-gain',type='gain',parameters={'gain':float(gain)},reason='Gain de sortie explicite du candidat filtré.')])
    p.edges.extend([link(source,'compact-saturation'),link('compact-saturation','compact-lowpass'),link('compact-lowpass','compact-gain'),link('compact-gain',out)])
    p.name+=' · saturation + filtre'
    return tidy(p)


def simplify(patch,x,weights,tolerance=.2,test_shaping=True,protect_texture=False):
    validate(patch)
    if not np.isfinite(tolerance) or not 0<=tolerance<=1:raise ValueError("Tolérance invalide (0 à 1).")
    if len(x)!=round(patch.duration*patch.sample_rate):raise ValueError("Longueur de référence incompatible avec le modèle.")
    if patch.duration>12:raise ValueError('Simplification limitée à 12 secondes.')
    original=patch.model_copy(deep=True);objective=Objective(x,patch.sample_rate,weights)
    folded=collapse_modes(patch)
    modes=[n.model_copy(deep=True) for n in folded.nodes if n.type=='modal']
    if not modes:raise ValueError('Générez un modèle modal avant de le simplifier.')
    for n in modes:n.parameters=parameters(n.type,n.parameters,patch.sample_rate)
    if any(n.parameters['onset']!=modes[0].parameters['onset'] or n.parameters['attack']!=modes[0].parameters['attack'] for n in modes):
        raise ValueError('Cette simplification exige un début et une attaque communs aux modes.')
    baseline=objective(render(original));limit=baseline*(1+tolerance)+1e-12
    reference_bands=band_errors(x,render(original),patch.sample_rate)
    reference_attack=objective.components(render(original))["attack"]
    candidates=[]
    def add(p,reference=False):
        y=render(p);errors=objective.components(y);bands=band_errors(x,y,p.sample_rate);count=sum(len(parameters(n.type,n.parameters,p.sample_rate)) for n in p.nodes)
        reasons=[]
        if errors['total']>limit:reasons.append('Erreur globale')
        if protect_texture:
            if errors['attack']>max(reference_attack*(1+tolerance),.01)+1e-12:reasons.append('Attaque')
            reasons.extend('Bande '+k for k in bands if bands[k]>max(reference_bands[k]*(1+tolerance),.03)+1e-12)
        candidates.append({'patch':p.model_dump(),'errors':errors,'complexity':complexity(p),'score':errors['total'],'parameter_count':count,'modules':physical_count(p),'bands':bands,'rejection_reasons':reasons,'generators':sum(REGISTRY[n.type].inputs==0 for n in p.nodes),'reference':reference,'within_tolerance':not reasons})
    add(original,True)
    clean=tidy(original)
    if len(clean.nodes)<len(original.nodes):add(clean)
    D,target,down=analysis_basis(x,patch.sample_rate,modes);gram=D.T@D;projection=D.T@target;del D
    selected=[];proposals=[]
    maximum=min(16,len(modes))
    budgets={1,2,3,4,6,8,10,12,16,maximum}
    for count in range(1,maximum+1):
        best=None
        for j in range(len(modes)):
            if j in selected:continue
            ids=[k for m in selected+[j] for k in (2*m,2*m+1)]
            g=gram[np.ix_(ids,ids)];b=projection[ids]
            coef=np.linalg.lstsq(g,b,rcond=1e-9)[0]
            if np.any(np.hypot(coef[::2],coef[1::2])>4):continue
            reduction=float(2*coef@b-coef@g@coef)
            if best is None or reduction>best[0]:best=(reduction,j,coef)
        if best is None:break
        _,j,coef=best;selected.append(j)
        if count not in budgets:continue
        partials=[{**modes[m].parameters,'amplitude':float(np.hypot(coef[2*i],coef[2*i+1])),'phase':float(np.arctan2(coef[2*i+1],coef[2*i])),'decay_r2':None} for i,m in enumerate(selected)]
        features={'partials':partials,'onset':modes[0].parameters['onset'],'attack':modes[0].parameters['attack']}
        p=modal_patch(features,patch.sample_rate,patch.duration,count)
        p=joint_fit(p,x,objective,down)
        if features['attack']>0:
            calibrated,_=calibrate_attack(p,objective)
            if objective(render(calibrated))<objective(render(p)):p=calibrated
        p.name=f'Compact · {count} modes';p=tidy(p)
        for n in p.nodes:
            if n.type=='modal':n.reason='Mode sélectionné par sa contribution à la reconstruction, puis fréquences, phases, amplitudes et décroissances réajustées ensemble. Coût final mesuré à la fréquence d’échantillonnage originale. Aucun générateur caché.'
        add(p);proposals.append(p)
    # Only a few useful budgets receive an extra processing search, limiting
    # identification time. A new block must justify its cost in the final choice.
    shortlist=[p for p in proposals if sum(n.type=='modal' for n in p.nodes) in (4,8,12)]
    processing_diagnostics=[]
    if test_shaping:
        from .nonlinear_fit import search
        global_candidates,processing_diagnostics=search(proposals,x,weights,objective)
        for p in global_candidates:add(p)
        for p in shortlist:
            shaped=shaping(p,objective)
            if shaped is not None:add(shaped)
    if protect_texture:
        texture_sources=shortlist+[p for p in global_candidates if sum(n.type=='modal' for n in p.nodes)<=3] if test_shaping else shortlist
        for p in sorted(texture_sources,key=lambda q:objective(render(q)))[:4]:
            textured=fit_texture(p,x,objective)
            if textured is not None:add(textured)
    # Test a residual impact only when the reference actually has that branch.
    if any(n.type=='noise' for n in original.nodes):
        from .impact import fit_impact
        for p in shortlist:
            onset=next(n.parameters['onset'] for n in p.nodes if n.type=='modal')
            impact=fit_impact(p,x,{'onset':onset},objective)
            if impact is not None:add(tidy(impact))
    def size(c):return c['modules'],c['parameter_count'],c['errors']['total']
    eligible=[c for c in candidates if c['within_tolerance']]
    chosen=min(eligible,key=size)
    # Backward pruning fills the gaps between coarse source budgets. A source
    # can be removed only if its actual new render stays inside every constraint.
    pruned=collapse_modes(Patch.model_validate(chosen['patch']))
    for node in sorted([n for n in pruned.nodes if n.type=='modal'],key=lambda n:n.parameters.get('amplitude',0)**2*n.parameters.get('tau',1)):
        outgoing=[e for e in pruned.edges if e.source==node.id]
        if len(outgoing)!=1:continue
        target=next(n for n in pruned.nodes if n.id==outgoing[0].target)
        if target.type!='sum' or sum(e.target==target.id for e in pruned.edges)<2:continue
        q=pruned.model_copy(deep=True);q.nodes=[n for n in q.nodes if n.id!=node.id];q.edges=[e for e in q.edges if e.source!=node.id]
        q=tidy(q);q.name='Compact · élagage vérifié';add(q)
        if candidates[-1]['within_tolerance']:pruned=q
    # Remove a processor only after measuring the actual bypassed graph. Control
    # envelopes and MIDI VCA remain part of the playable instrument contract.
    for node in list(pruned.nodes):
        if node.type not in ('gain','lowpass','lowpass1','highpass','bandpass','notch','peak_eq','saturation','asymmetric_saturation') or node.id.startswith('keyboard-'):continue
        incoming=[e for e in pruned.edges if e.target==node.id]
        if len(incoming)!=1:continue
        q=pruned.model_copy(deep=True);source=incoming[0].source
        q.edges=[Edge(id=f'{source}-{e.target}',source=source,target=e.target) if e.source==node.id else e for e in q.edges if e.target!=node.id]
        q.nodes=[n for n in q.nodes if n.id!=node.id]
        try:q=tidy(q)
        except ValueError:continue  # bypass would duplicate an existing cable
        q.name='Compact · traitements utiles';add(q)
        if candidates[-1]['within_tolerance']:pruned=q
    chosen=min([c for c in candidates if c['within_tolerance']],key=size)
    from .shared_envelopes import share_envelopes
    shared_sources=proposals+[collapse_modes(Patch.model_validate(chosen['patch']))]
    for source in shared_sources:
        for groups in (1,2,3,4,6,8):
            shared=share_envelopes(source,groups)
            if shared is not None:add(shared)
    chosen=min([c for c in candidates if c['within_tolerance']],key=size)
    for c in candidates:
        c['pareto']=not any(other['modules']<=c['modules'] and other['errors']['total']<=c['errors']['total'] and (other['modules']<c['modules'] or other['errors']['total']<c['errors']['total']) for other in candidates)
    candidates.sort(key=size)
    # Ablation on the executed graph: set each source amplitude to zero, without
    # refitting the rest. Negative values flag interference rather than usefulness.
    chosen_patch=Patch.model_validate(chosen['patch']);utilities=[]
    for node in chosen_patch.nodes:
        if node.type in ('sum','output'):continue
        ablated=chosen_patch.model_copy(deep=True)
        if node.type in ('modal','noise','oscillator','impulse'):
            next(n for n in ablated.nodes if n.id==node.id).parameters['amplitude']=0
        elif REGISTRY[node.type].inputs==1:
            source=next(e.source for e in ablated.edges if e.target==node.id)
            ablated.edges=[Edge(id=f'{source}-{e.target}',source=source,target=e.target) if e.source==node.id else e for e in ablated.edges if e.target!=node.id]
            ablated.nodes=[n for n in ablated.nodes if n.id!=node.id]
        else:continue
        delta=objective(render(ablated))-chosen['errors']['total']
        utilities.append({'block_id':node.id,'label':node.label or node.type,'error_increase_without':float(delta)})
    return {'patch':chosen_patch.model_dump(),'original':original.model_dump(),'candidates':candidates,'baseline':baseline,'limit':limit,'tolerance':tolerance,'final':chosen['errors']['total'],'original_blocks':physical_count(original),'final_blocks':physical_count(chosen_patch),'original_generators':sum(REGISTRY[n.type].inputs==0 for n in original.nodes),'final_generators':chosen['generators'],'reverted':chosen['reference'],'utilities':utilities,'shaping_tested':test_shaping,'processing_diagnostics':processing_diagnostics,'reference_bands':reference_bands,'final_bands':chosen['bands'],'protect_texture':protect_texture,'selection':'Minimum de blocs sous la limite d’erreur acceptée ; à égalité, moins de paramètres puis erreur minimale. Version initiale conservée. Utilité : hausse de coût en coupant une source, sans réajuster les autres.'}
