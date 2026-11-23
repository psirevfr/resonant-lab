"""Compact generation candidates, accepted only against measured full-rate quality.

No recorded waveform is embedded. A noise comb is a candidate, never an assumed
replacement for the measured inharmonic modes of a piano.
"""
import numpy as np
from .schema import Block,Patch
from .identify import link,modal_patch,complexity
from .graph import render
from .instrument import physical_count
from .texture import band_errors


def comb_candidates(x,fs,features,objective):
    f=features.get('f0')
    if f is None or not 20<=f<min(47000,fs*.49):return []
    features={**features,'partials':[min(features['partials'],key=lambda p:abs(p['frequency']-f))]}
    base=modal_patch(features,fs,len(x)/fs,1)
    from .compact import tidy
    base=tidy(base);carrier=next(n for n in base.nodes if n.type=='modal')
    tau=carrier.parameters['tau'];onset=features['onset'];attack=features['attack']
    tone=render(base);residual=x-tone
    residual_norm=float(np.linalg.norm(residual))
    best={}
    for burst in (False,True):
        for feedback in (.8,.95,.99):
            for cutoff in (min(fs*.4,max(800,f*8)),min(fs*.4,max(2400,f*24))):
                nodes=[Block(id='exciter',type='noise',parameters={'amplitude':1,'seed':42}),
                       Block(id='exciter-gain',type='gain',parameters={'gain':1},reason='Amplification explicite de la source de bruit ; un AOP réel nécessite une alimentation et un réseau de résistances.'),
                       Block(id='comb',type='comb',parameters={'frequency':f,'feedback':feedback}),
                       Block(id='hp',type='highpass',parameters={'fc':max(5,min(fs*.4,f*1.4)),'q':.70710678}),
                       Block(id='lp',type='lowpass1',parameters={'fc':cutoff}),
                       Block(id='noise-env',type='envelope',parameters={'attack':attack,'onset':onset,'tau':.025 if burst else tau}),
                       Block(id='out',type='output')]
                # An impulse-like noise burst excites the comb's decay; sustained
                # noise instead gets its amplitude envelope after the filters.
                order=['exciter','exciter-gain','noise-env','comb','hp','lp','out'] if burst else ['exciter','exciter-gain','comb','hp','lp','noise-env','out']
                p=Patch(name='Fondamentale + bruit '+('pincé' if burst else 'entretenu')+' + peigne',sample_rate=fs,duration=len(x)/fs,nodes=nodes,edges=[link(a,b) for a,b in zip(order,order[1:])])
                raw=render(p)
                # Propose three noise gains from residual energy. The tonal
                # parameters remain measured; all proposals are scored below.
                scale=min(4,residual_norm/max(float(np.linalg.norm(raw)),1e-12))
                for gain in (scale*.25,scale*.5,scale):
                    if gain<1e-8:continue
                    q=p.model_copy(deep=True);next(n for n in q.nodes if n.id=='exciter-gain').parameters['gain']=gain
                    q.nodes.extend([carrier.model_copy(deep=True),Block(id='mix',type='sum')])
                    q.edges=[e for e in q.edges if e.target!='out']+[link(order[-2],'mix'),link(carrier.id,'mix'),link('mix','out')]
                    positions={key:{'x':240*i,'y':180} for i,key in enumerate(order[:-1])}
                    positions.update({carrier.id:{'x':0,'y':0},'mix':{'x':1440,'y':90},'out':{'x':1680,'y':90}})
                    for node in q.nodes:node.position=positions[node.id]
                    y=tone+gain*raw;error=objective(y)
                    if burst not in best or error<best[burst][0]:best[burst]=(error,q)
    return [q for _,q in best.values()]


def select_compact_generation(patches,x,features,objective,weights,penalty,*,history=None,learning=None):
    from .compact import tidy
    from .shared_envelopes import share_envelopes
    from .nonlinear_fit import architecture,fit_architecture,refine_shared
    # Preserve the pre-existing selection/precision contract as the benchmark.
    rows=[]
    def row(p,reference=False):
        y=render(p);errors=objective.components(y)
        return {'patch':p.model_dump(),'errors':errors,'complexity':complexity(p),'score':errors['total']+penalty*complexity(p),'modules':physical_count(p),'bands':band_errors(x,y,p.sample_rate),'reference':reference}
    rows=[row(p) for p in patches]
    baseline=min(rows,key=lambda r:r['score']);baseline['reference']=True
    ref=Patch.model_validate(baseline['patch'])
    proposed=[tidy(p) for p in patches]
    for groups in (1,2,4):
        shared=share_envelopes(tidy(ref),groups)
        if shared is not None:proposed.append(tidy(shared))
    # A bounded additional search, on one/two carriers, never truncating the
    # reference bank or changing its own fitting/iteration requirements.
    for count in sorted({1,min(2,len(features['partials']))}):
        seed=tidy(modal_patch(features,ref.sample_rate,ref.duration,count))
        for style in ('excitation-partagee','excitation-resonante'):
            p=architecture(seed,style)
            fitted,_=fit_architecture(p,x,weights,budget=100)
            best=min((p,fitted),key=lambda q:objective(render(q)))
            best,_=refine_shared(best,x,objective)
            proposed.append(best)
    proposed.extend(comb_candidates(x,ref.sample_rate,features,objective))
    from .hybrid import high_band_candidates
    proposed.extend(high_band_candidates(tidy(ref),x,objective,features.get('f0')))
    from .harmonic_groups import harmonic_candidates
    proposed.extend(harmonic_candidates(tidy(ref),x,weights))
    rows.extend(row(p) for p in proposed)
    def check(r):
        reasons=[]
        for key in baseline['errors']:
            if r['errors'][key]>baseline['errors'][key]+1e-12:reasons.append('Erreur '+key+' supérieure à la référence')
        for band,error in r['bands'].items():
            if error>baseline['bands'][band]+1e-12:reasons.append('Bande '+band+' moins fidèle')
        r['within_tolerance']=not reasons;r['rejection_reasons']=reasons
        return r
    for r in rows:check(r)
    # Bounded backward pruning of the best admissible graph. Other branches,
    # including the measured impact, are never discarded to rebuild a bank.
    from .hybrid import summed_families,remove_modes
    current=Patch.model_validate(min((r for r in rows if r['within_tolerance']),key=lambda r:(r['modules'],r['errors']['total'],r['complexity']))['patch'])
    families=summed_families(current,('modal','oscillator'))
    removable=[n for family in families.values() for n in family]
    for node in sorted(removable,key=lambda n:n.parameters.get('amplitude',0)**2*n.parameters.get('tau',1)):
        target=next(e.target for e in current.edges if e.source==node.id)
        if sum(e.target==target for e in current.edges)<2:continue
        q=tidy(remove_modes(current,{node.id}));q.name='Hybride · modes utiles vérifiés'
        candidate=check(row(q))
        if candidate['within_tolerance']:
            rows.append(candidate);current=q
    eligible=[r for r in rows if r['within_tolerance']]
    chosen=min(eligible,key=lambda r:(r['modules'],r['errors']['total'],r['complexity']))
    if learning is not None:
        from .adaptive import LEARNING_VERSION, adaptive_reward, envelope_candidate, select_strategy, sound_profile
        profile=sound_profile(features,len(x)/ref.sample_rate)
        strategy=select_strategy(profile,history)
        try:
            patch=envelope_candidate(x,ref.sample_rate,features,objective,strategy,chosen['modules'])
            candidate=check(row(patch)) if patch is not None else None
            reward=adaptive_reward(chosen,candidate) if candidate and candidate['within_tolerance'] else 0.
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            # The optional fit can be ill-conditioned on unusual excerpts.
            reward=0.
        if reward>0:
            rows.append(candidate)
            chosen=candidate
        learning.update(version=LEARNING_VERSION,profile=profile,strategy=strategy,reward=reward,accepted=reward>0)
    rows.sort(key=lambda r:(r is not chosen,not r['within_tolerance'],r['score']))
    return rows,baseline
