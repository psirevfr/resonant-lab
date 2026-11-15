"""Predeclared full-rate tolerance: 2e-12 for an exactly representable texture.
No relaxed objective/band tolerances are used to accept the substitution.
"""
import numpy as np
from lab.schema import Patch,Block,Weights
from lab.identify import link
from lab.graph import render,validate
from lab.blocks import process
from lab.metrics import Objective
from lab.texture import band_errors
from lab.instrument import physical_count
from lab.hybrid import high_band_candidates,summed_families


def fixture():
    def mode(key,f,amp):return Block(id=key,type='modal',parameters={'frequency':f,'amplitude':amp,'phase':0,'tau':.3,'attack':.003,'onset':0})
    nodes=[mode('fundamental',300,.3)]+[mode(f'upper{i}',2400+i*450,.005) for i in range(6)]
    # A separate existing transient must survive the proposed substitution.
    nodes += [Block(id='impact',type='impulse',parameters={'amplitude':.001}),Block(id='sum',type='sum'),Block(id='out',type='output')]
    p=Patch(duration=.15,nodes=nodes,edges=[link(n.id,'sum') for n in nodes[:-2]]+[link('sum','out')])
    kept=p.model_copy(deep=True);kept.nodes=[n for n in kept.nodes if not n.id.startswith('upper')];kept.edges=[e for e in kept.edges if not e.source.startswith('upper')]
    n=round(p.duration*p.sample_rate);noise=process('noise',{'amplitude':1.,'seed':42},[],p.sample_rate,n)
    noise=process('highpass',{'fc':2000.,'q':.70710678},[noise],p.sample_rate,n)
    noise=process('envelope',{'attack':.001,'tau':.12,'onset':0},[noise],p.sample_rate,n)
    return p,render(kept)+.025*noise


def test_high_band_replacement_preserves_low_modes_and_existing_transient():
    p,x=fixture();before=p.model_dump();objective=Objective(x,p.sample_rate,Weights())
    candidates=high_band_candidates(p,x,objective,300)
    assert len(candidates)==2
    chosen=min(candidates,key=lambda q:objective(render(q)))
    assert physical_count(chosen)<physical_count(p)
    assert sum(n.type=='modal' for n in chosen.nodes)==1
    assert {'noise','gain','highpass','envelope'}<=set(n.type for n in chosen.nodes)
    for key in ('fundamental','impact'):
        assert next(n for n in chosen.nodes if n.id==key)==next(n for n in p.nodes if n.id==key)
    assert np.max(abs(render(chosen)-x))<2e-12
    assert np.array_equal(render(chosen),render(Patch.model_validate_json(chosen.model_dump_json())))
    reference=objective.components(render(p));errors=objective.components(render(chosen))
    assert all(errors[k]<=reference[k]+1e-12 for k in errors)
    a=band_errors(x,render(p),p.sample_rate);b=band_errors(x,render(chosen),p.sample_rate)
    assert all(b[k]<=a[k]+1e-12 for k in b)
    assert p.model_dump()==before


def test_hybrid_names_are_collision_safe_and_no_pitch_requires_no_comb():
    p,x=fixture();p.nodes[0].id='hybrid-low'
    for e in p.edges:
        if e.source=='fundamental':e.source='hybrid-low'
    for q in high_band_candidates(p,x,Objective(x,p.sample_rate,Weights())):
        validate(q)
        assert not any(n.type=='comb' for n in q.nodes)
        assert any(n.id=='hybridx-gain' for n in q.nodes)


def test_nonlinear_routes_are_not_misidentified_as_replaceable_modal_banks():
    p,x=fixture();p.nodes.append(Block(id='sat',type='saturation'))
    p.edges=[e for e in p.edges if e.source!='fundamental']+[link('fundamental','sat'),link('sat','sum')]
    assert all(n.id!='fundamental' for nodes in summed_families(p).values() for n in nodes)
    # All remaining direct modes are high: do not remove their entire family.
    assert high_band_candidates(p,x,Objective(x,p.sample_rate,Weights()),300)==[]


def test_simplification_integrates_hybrid_without_relaxing_user_quality_budget():
    from lab.compact import simplify
    p,x=fixture()
    r=simplify(p,x,Weights(),tolerance=0,test_shaping=False,protect_texture=True,test_noise=True)
    hybrids=[c for c in r['candidates'] if c['patch']['name'].startswith('Hybride')]
    assert hybrids and any(c['within_tolerance'] for c in hybrids)
    assert r['final_blocks']<physical_count(p) and r['final']<=r['limit']
    assert r['original']==p.model_dump()


def test_generation_can_remove_a_useless_source_without_hiding_or_mutating_it():
    from lab.generation_search import select_compact_generation
    from lab.analysis import analyze
    p,_=fixture()
    p.nodes[1].parameters['amplitude']=0
    x=render(p);before=p.model_dump()
    rows,ref=select_compact_generation([p],x,analyze(x,p.sample_rate,4),Objective(x,p.sample_rate,Weights()),Weights(),.0001)
    best=rows[0]
    assert best['modules']<physical_count(p) and best['within_tolerance']
    assert all(e<=1e-12 for e in best['errors'].values())
    assert not any(n['id']=='upper0' for n in best['patch']['nodes'])
    assert p.model_dump()==before==ref['patch']


def test_hybrid_does_not_assume_downstream_processing_or_duplicate_routes_are_unity():
    p,x=fixture();p.nodes.append(Block(id='filter',type='lowpass'))
    p.edges=[e for e in p.edges if e.target!='out']+[link('sum','filter'),link('filter','out')]
    assert high_band_candidates(p,x,Objective(x,p.sample_rate,Weights()),300)==[]
    p,x=fixture();p.nodes += [Block(id='copy',type='gain'),Block(id='mix',type='sum')]
    p.edges=[e for e in p.edges if e.target!='out']+[link('sum','copy'),link('sum','mix'),link('copy','mix'),link('mix','out')]
    assert high_band_candidates(p,x,Objective(x,p.sample_rate,Weights()),300)==[]
