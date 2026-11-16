"""Harmonic substitution proposals, not an unconditional sound replacement.

Predeclared fixture accuracy: max sample error <1e-6. Production selection still
uses every existing full-rate quality guard, with no changes to its tolerances.
"""
import numpy as np
from test_sobriety import nonlinear_fixture
from lab.schema import Block,Patch,Weights
from lab.identify import link
from lab.graph import render,validate
from lab.metrics import Objective
from lab.instrument import physical_count
from lab.harmonic_groups import choose_group,harmonic_candidates


def fixture():
    p,x=nonlinear_fixture()
    # Unrelated tonal and transient branches must remain exactly as specified.
    extra=Block(id='harmonic-extra',type='modal',parameters={'frequency':517,'amplitude':.02,'phase':.3,'tau':.1,'attack':.003,'onset':0})
    impact=Block(id='impact',type='impulse',parameters={'amplitude':.001})
    from lab.blocks import parameters,process
    for n in (extra,impact):
        p.nodes.append(n);p.edges.append(link(n.id,'s'))
        x+=process(n.type,parameters(n.type,n.parameters,p.sample_rate),[],p.sample_rate,len(x))
    return p,x


def test_group_is_replaced_without_losing_other_branches_or_hiding_generators():
    p,x=fixture();before=p.model_dump();obj=Objective(x,p.sample_rate,Weights())
    proposals=harmonic_candidates(p,x,Weights())
    assert 1<=len(proposals)<=3
    best=min(proposals,key=lambda q:obj(render(q)))
    assert physical_count(best)<physical_count(p)
    assert np.max(abs(render(best)-x))<1e-6
    assert obj(render(best))<obj(render(p))
    assert sum(n.type=='oscillator' for n in best.nodes)==1
    assert sum(n.type=='modal' for n in best.nodes)==1
    assert {'asymmetric_saturation','lowpass1','envelope'}<=set(n.type for n in best.nodes)
    for key in ('harmonic-extra','impact'):
        assert next(n for n in best.nodes if n.id==key)==next(n for n in p.nodes if n.id==key)
    for q in proposals:
        validate(q)
        assert np.array_equal(render(q),render(Patch.model_validate_json(q.model_dump_json())))
        assert any(n.id.startswith('harmonicx-') for n in q.nodes)
    assert p.model_dump()==before


def test_detuning_or_different_onsets_do_not_form_a_coherent_group():
    p,_=nonlinear_fixture()
    assert len(choose_group(p)[2])==8
    p.duration=3
    for i,n in enumerate(p.nodes[:8]):
        if i:n.parameters['frequency']+=.4
    assert choose_group(p) is None
    p,_=nonlinear_fixture()
    for i,n in enumerate(p.nodes[:8]):n.parameters['onset']=i*.001
    assert choose_group(p) is None


def test_downstream_filter_and_fanout_are_not_subtracted_as_unity():
    p,x=fixture();p.nodes.append(Block(id='lp',type='lowpass1'))
    p.edges=[e for e in p.edges if e.target!='o']+[link('s','lp'),link('lp','o')]
    assert harmonic_candidates(p,x,Weights())==[]
    p,x=fixture();p.nodes.extend([Block(id='g',type='gain'),Block(id='mix',type='sum')])
    p.edges=[e for e in p.edges if e.target!='o']+[link('s','g'),link('s','mix'),link('g','mix'),link('mix','o')]
    assert choose_group(p) is None


def test_zero_amplitude_modes_are_not_counted_as_useful_harmonics():
    p,_=nonlinear_fixture()
    for n in p.nodes[3:8]:n.parameters['amplitude']=0
    assert choose_group(p) is None


def test_close_frequencies_cannot_assign_the_same_mode_to_several_harmonics():
    p,_=nonlinear_fixture()
    for i,n in enumerate(p.nodes[:8]):n.parameters['frequency']=i+1
    group=choose_group(p)[2]
    assert len(group)==len({n.id for n in group})


def test_simplification_records_substitution_and_respects_existing_guards():
    from lab.compact import simplify
    p,x=fixture()
    r=simplify(p,x,Weights(),tolerance=.2,test_shaping=True,protect_texture=True,test_noise=False)
    substitutions=[c for c in r['candidates'] if 'modes remplacés par sinus' in c['patch']['name']]
    assert substitutions and any(c['within_tolerance'] for c in substitutions)
    assert r['final']<=r['limit'] and r['final_blocks']<r['original_blocks']
    assert all(not c['rejection_reasons'] for c in r['candidates'] if c['within_tolerance'])


def test_generation_keeps_its_stricter_per_band_and_per_term_guards():
    from lab.generation_search import select_compact_generation
    from lab.analysis import analyze
    p,x=fixture();obj=Objective(x,p.sample_rate,Weights())
    rows,reference=select_compact_generation([p],x,analyze(x,p.sample_rate,4),obj,Weights(),.0001)
    assert any('modes remplacés par sinus' in c['patch']['name'] for c in rows)
    for c in rows:
        if not c['within_tolerance']:continue
        assert all(c['errors'][k]<=v+1e-12 for k,v in reference['errors'].items())
        assert all(c['bands'][k]<=v+1e-12 for k,v in reference['bands'].items())
