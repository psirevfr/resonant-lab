"""Replace one coherent harmonic group, never the entire reference by assumption.

A saturation creates coupled harmonics, not arbitrary independently detuned modes.
Frequency proximity only chooses a candidate; full-graph metrics decide acceptance.
"""
from .schema import Block,Patch,Weights
from .blocks import parameters,process
from .graph import render,validate
from .identify import link
from .hybrid import summed_families,unity_output_route


def choose_group(reference):
    """At most one group, one measured mode per harmonic, at least four modes.

    Search tolerance is at most a quarter cycle over the measured duration and
    at most 2 Hz. This is NOT an acceptance tolerance for the final sound.
    """
    groups=[];fs=reference.sample_rate;tolerance=min(2.,.25/reference.duration)
    for target,nodes in summed_families(reference).items():
        if not unity_output_route(reference,target):continue
        values={n.id:parameters('modal',n.parameters,fs) for n in nodes}
        for source in nodes:
            first=values[source.id];f=first['frequency']
            if first['amplitude']==0:continue
            group=[source]
            for harmonic in range(2,min(32,int((fs/2-1e-6)/f))+1):
                matching=[n for n in nodes if n.id not in {item.id for item in group} and abs(values[n.id]['frequency']-harmonic*f)<=tolerance and values[n.id]['onset']==first['onset'] and values[n.id]['attack']==first['attack'] and values[n.id]['amplitude']>0]
                if matching:
                    group.append(min(matching,key=lambda n:(abs(values[n.id]['frequency']-harmonic*f),-values[n.id]['amplitude']**2*values[n.id]['tau'],n.id)))
            if len(group)<4:continue
            energy=sum(values[n.id]['amplitude']**2*values[n.id]['tau'] for n in group)
            groups.append((energy,target,source,group))
    return max(groups,key=lambda g:g[0])[1:] if groups else None


def replace_group(reference,target,group,branch):
    """Splice executable blocks, keeping all other nodes/edges and no sample data."""
    p=reference.model_copy(deep=True);ids={n.id for n in group}
    p.nodes=[n for n in p.nodes if n.id not in ids];p.edges=[e for e in p.edges if e.source not in ids]
    stem='harmonic';used={n.id for n in reference.nodes}
    while any(key.startswith(stem+'-') for key in used):stem+='x'
    output=next(n.id for n in branch.nodes if n.type=='output')
    parent=next(e.source for e in branch.edges if e.target==output)
    y=max(n.position.get('y',0) for n in reference.nodes)+180
    for i,node in enumerate(n for n in branch.nodes if n.id!=output):
        node=node.model_copy(deep=True);node.id=stem+'-'+node.id;node.position={'x':i*240,'y':y}
        node.label={'oscillator':'Oscillateur sinusoïdal','asymmetric_saturation':'Saturation asymétrique ×4','lowpass1':'Filtre passe-bas (1er ordre)','envelope':'Enveloppe exponentielle / VCA'}.get(node.type,node.label)
        node.reason=f'Remplacement candidat de {len(group)} modes par une excitation saturée et filtrée ; autres branches conservées. Comparaison finale sur le graphe réellement exécuté.'
        p.nodes.append(node)
    p.edges.extend(link(stem+'-'+e.source,stem+'-'+e.target) for e in branch.edges if e.target!=output)
    p.edges.append(link(stem+'-'+parent,target))
    p.name=f'Hybride · {len(group)} modes remplacés par sinus + saturation ×4 + filtre + enveloppe'
    validate(p);return p


def harmonic_candidates(reference,x,weights:Weights):
    selected=choose_group(reference)
    if selected is None:return []
    target,source,group=selected;fs=reference.sample_rate
    # Unity route is checked above. Subtraction is only a fitting proposal;
    # scoring/acceptance below renders the complete spliced graph afresh.
    kept=render(reference)
    for node in group:kept-=process('modal',parameters('modal',node.parameters,fs),[],fs,len(x))
    residual=x-kept
    source=source.model_copy(deep=True);source.id='carrier';source.parameters=parameters('modal',source.parameters,fs)
    seed=Patch(sample_rate=fs,duration=reference.duration,nodes=[source,Block(id='out',type='output')],edges=[link('carrier','out')])
    from .nonlinear_fit import architecture,fit_architecture,refine_shared
    from .metrics import Objective
    branch=architecture(seed,'excitation-partagee')
    residual_objective=Objective(residual,fs,weights)
    fitted,_=fit_architecture(branch,residual,weights,budget=100)
    best=min((branch,fitted),key=lambda q:residual_objective(render(q)))
    refined,_=refine_shared(best,residual,residual_objective)
    # A lower residual error does not guarantee a lower complete objective.
    # Keep all three distinct proposals for the caller's complete quality guard.
    proposals=[];signatures=set()
    for q in (branch,fitted,refined):
        signature=q.model_dump_json()
        if signature in signatures:continue
        signatures.add(signature)
        proposals.append(replace_group(reference,target,group,q))
    return proposals
