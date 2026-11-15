"""Explicit high-band substitutions that preserve the rest of the reference DAG.

A branch is a proposal only. The caller must validate every full-rate quality
criterion before accepting it. No sample bank or hidden oscillator is emitted.
"""
import numpy as np
from .blocks import parameters,process
from .graph import render,validate
from .schema import Block
from .identify import link


def summed_families(patch,kinds=('modal',)):
    nodes,inc,out,order,_=validate(patch);families={}
    for key in order:
        if nodes[key].type in kinds and len(out[key])==1 and nodes[out[key][0]].type=='sum':
            families.setdefault(out[key][0],[]).append(nodes[key])
    return families


def unity_output_route(patch,target):
    """The fast additive trial is exact only on one unity route to output.

    Other input branches can be arbitrary. Downstream filtering, saturation or
    duplicated routes require a different fitting problem and are not guessed.
    """
    nodes,_,out,_,output=validate(patch)
    current=target
    while current!=output:
        node=nodes[current]
        if node.type!='sum' and not (node.type=='gain' and parameters('gain',node.parameters,patch.sample_rate)['gain']==1):return False
        if len(out[current])!=1:return False
        current=out[current][0]
    return True


def remove_modes(patch,ids):
    p=patch.model_copy(deep=True)
    p.nodes=[n for n in p.nodes if n.id not in ids]
    p.edges=[e for e in p.edges if e.source not in ids]
    validate(p)
    return p


def high_band_candidates(reference,x,objective,f0=None):
    """Try at most two cutoffs in the largest directly summed modal family.

    Existing attack/noise/filter branches stay intact. Noise gain is explicit;
    source seed is fixed for all trials. Retain one proposal per cutoff and
    topology; final selection belongs to the unchanged full-rate quality guard.
    """
    families={target:nodes for target,nodes in summed_families(reference).items() if unity_output_route(reference,target)}
    if not families:return []
    target,modes=max(families.items(),key=lambda item:len(item[1]))
    fs=reference.sample_rate;n=len(x);values={b.id:parameters('modal',b.parameters,fs) for b in modes}
    used={b.id for b in reference.nodes};stem='hybrid'
    while any(key.startswith(stem+'-') for key in used):stem+='x'
    branch_y=max(node.position.get('y',0) for node in reference.nodes)+180
    noise=process('noise',{'amplitude':1.,'seed':42},[],fs,n)
    variants=[None]+([.95,.99] if f0 is not None and 20<=f0<min(47000,fs*.49) else [])
    candidates=[]
    for cutoff in (2000.,6000.):
        ids={b.id for b in modes if values[b.id]['frequency']>=cutoff}
        if len(ids)<4 or len(ids)==len(modes):continue
        base=remove_modes(reference,ids);tonal=render(base);residual=x-tonal
        onset=min(values[key]['onset'] for key in ids)
        tau_hint=float(np.clip(np.median([values[key]['tau'] for key in ids]),.005,30))
        best={}
        for feedback in variants:
            raw=noise
            if feedback is not None:raw=process('comb',{'frequency':f0,'feedback':feedback},[raw],fs,n)
            raw=process('highpass',{'fc':cutoff,'q':.70710678},[raw],fs,n)
            for tau in sorted({.025,.12,.5,tau_hint}):
                env={'attack':.001,'tau':tau,'onset':onset}
                burst=process('envelope',env,[raw],fs,n)
                energy=max(float(burst@burst),1e-24)
                # LS phase-sensitive estimate plus energy proposals: a fresh
                # stochastic realization is not assumed to match sample phases.
                projection=float(np.clip((residual@burst)/energy,0,4))
                scale=min(4,float(np.linalg.norm(residual)/np.sqrt(energy)))
                for gain in sorted({projection,scale*.25,scale*.5,scale}):
                    if gain<1e-9:continue
                    error=objective(tonal+gain*burst)
                    family=feedback is not None
                    if family not in best or error<best[family][0]:best[family]=(error,feedback,env,gain)
        for _,feedback,env,gain in best.values():
            p=base.model_copy(deep=True)
            chain=[('noise','noise',{'amplitude':1.,'seed':42}),('gain','gain',{'gain':gain})]
            if feedback is not None:chain.append(('comb','comb',{'frequency':f0,'feedback':feedback}))
            chain.extend([('filter','highpass',{'fc':cutoff,'q':.70710678}),('env','envelope',env)])
            for i,(suffix,kind,params) in enumerate(chain):
                nid=stem+'-'+suffix
                p.nodes.append(Block(id=nid,type=kind,parameters=params,position={'x':240*i,'y':branch_y},reason=f'Essai de remplacement de {len(ids)} modes au-dessus de {cutoff:g} Hz. Les autres branches sont conservées. Bruit synthétique, graine fixe ; acceptation uniquement après mesure complète.'))
                if i:p.edges.append(link(stem+'-'+chain[i-1][0],nid))
            p.edges.append(link(stem+'-env',target))
            p.name=f'Hybride · {sum(node.type=="modal" for node in p.nodes)} modes conservés + aigus bruités'+(' / peigne' if feedback is not None else '')
            validate(p);candidates.append(p)
    return candidates
