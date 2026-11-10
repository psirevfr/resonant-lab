"""Topology/quality tests: tolerances apply to the unchanged full-rate objective."""
import numpy as np
import pytest
from lab.schema import Patch,Block,Weights
from lab.identify import link
from lab.graph import render,validate
from lab.metrics import Objective
from lab.nonlinear_fit import architecture,refine_shared
from lab.compact import simplify
from lab.instrument import physical_count,expand_modes
from lab.texture import search_texture


def carrier():
    return Patch(duration=.15,nodes=[Block(id='m',type='modal',parameters={'frequency':300,'amplitude':.4,'phase':0,'tau':.3,'attack':.003,'onset':0}),Block(id='o',type='output')],edges=[link('m','o')])


def test_shared_excitation_exposes_every_block_and_preserves_source():
    p=carrier();before=p.model_dump();p.nodes[0].parameters['onset']=.01
    for style in ('excitation-partagee','excitation-resonante'):
        q=architecture(p,style);validate(q)
        assert [n.type for n in q.nodes].count('oscillator')==1
        assert not any(n.type=='modal' for n in q.nodes)
        assert sum(n.type=='envelope' for n in q.nodes)==1
        assert physical_count(q)==len(q.nodes)
        assert np.array_equal(render(q),render(Patch.model_validate_json(q.model_dump_json())))
        assert not np.any(render(q)[:round(.01*q.sample_rate)])
    p.nodes[0].parameters['onset']=0;assert p.model_dump()==before


def nonlinear_fixture():
    seed=carrier();target=architecture(seed,'excitation-partagee')
    next(n for n in target.nodes if n.type=='asymmetric_saturation').parameters['bias']=0
    x=render(target);t=np.arange(len(x))/seed.sample_rate;env=np.exp(-t/.3)*-np.expm1(-t/.003)
    # Reference bank describes the SAME waveform, not a made-up spectrum.
    D=np.array([env*f(2*np.pi*300*h*t) for h in range(1,9) for f in (np.sin,np.cos)]).T
    z=np.linalg.lstsq(D,x,rcond=None)[0]
    modes=[Block(id=f'm{i}',type='modal',parameters={'frequency':300*(i+1),'amplitude':float(np.hypot(*z[2*i:2*i+2])),'phase':float(np.arctan2(z[2*i+1],z[2*i])),'tau':.3,'attack':.003,'onset':0}) for i in range(8)]
    p=Patch(duration=seed.duration,nodes=modes+[Block(id='s',type='sum'),Block(id='o',type='output')],edges=[link(n.id,'s') for n in modes]+[link('s','o')])
    return p,x


def test_nonlinear_bank_replaced_by_one_visible_source_under_same_quality_budget():
    p,x=nonlinear_fixture();before=p.model_dump()
    r=simplify(p,x,Weights(),tolerance=.2,test_shaping=True,protect_texture=True,test_noise=False)
    q=Patch.model_validate(r['patch']);objective=Objective(x,p.sample_rate,Weights())
    # Target predefined before this test: strictly fewer modules/sources, actual
    # objective <= original budget, no >1e-9 scoring discrepancy.
    assert r['final_blocks']<physical_count(p) and r['final_generators']==1
    assert r['final']<=r['limit']
    assert r['final']==pytest.approx(objective(render(q)),abs=1e-9)
    assert p.model_dump()==before==r['original']
    assert len(expand_modes(q).nodes)==r['final_blocks']
    assert {'asymmetric_saturation','envelope','lowpass1'}<=set(n.type for n in q.nodes)
    assert all(not c['rejection_reasons'] for c in r['candidates'] if c['within_tolerance'])


def test_zero_tolerance_never_trades_stable_modes_for_noise():
    p=carrier();p.nodes.insert(1,p.nodes[0].model_copy(update={'id':'b'},deep=True));p.nodes[1].parameters['frequency']=517
    p.nodes.insert(-1,Block(id='sum',type='sum'));p.edges=[link('m','sum'),link('b','sum'),link('sum','o')]
    x=render(p);r=simplify(p,x,Weights(),tolerance=0,test_shaping=False,test_noise=True,protect_texture=True)
    assert r['final_generators']==2
    assert r['final']<=r['limit']
    assert np.max(abs(x-render(Patch.model_validate(r['patch']))))<1e-10


def test_noise_branch_is_minimal_explicit_and_scored_with_actual_filters():
    p=carrier();fs=p.sample_rate;n=round(fs*p.duration)
    from lab.blocks import process
    noise=process('noise',{'amplitude':.04,'seed':42},[],fs,n)
    noise=process('highpass',{'fc':2200,'q':.707},[noise],fs,n)
    noise=process('envelope',{'attack':.001,'tau':.12,'onset':0},[noise],fs,n)
    x=render(p)+noise;obj=Objective(x,fs,Weights());before=p.model_dump()
    proposals,diagnostics=search_texture(p,x,obj)
    assert proposals
    assert len(proposals)==len(diagnostics)<=3
    for q,d in zip(proposals,diagnostics):
        validate(q)
        assert physical_count(q)==d['blocks']
        assert d['full_rate_error']==pytest.approx(obj(render(q)),abs=1e-12)
        branch=[b for b in q.nodes if b.id.startswith('residual-')]
        assert sum(b.type=='noise' for b in branch)==1
        assert sum(b.type=='envelope' for b in branch)==1
        assert not any(b.type=='gain' for b in branch)
        assert np.array_equal(render(q),render(Patch.model_validate_json(q.model_dump_json())))
    assert min(d['full_rate_error'] for d in diagnostics)<obj(render(p))
    assert p.model_dump()==before
    assert search_texture(p,render(p),Objective(render(p),fs,Weights()))==([],[])


def test_full_rate_refinement_never_replaces_a_better_seed():
    p=architecture(carrier(),'excitation-partagee');x=render(p);obj=Objective(x,p.sample_rate,Weights())
    q,calls=refine_shared(p,x,obj)
    assert calls>0
    assert obj(render(q))<=obj(render(p))+1e-12


def test_noise_exploration_and_quality_guards_are_independent(monkeypatch):
    import lab.texture
    calls=[]
    monkeypatch.setattr(lab.texture,'search_texture',lambda *args:(calls.append(True) or ([],[])))
    p=carrier();x=render(p)
    r=simplify(p,x,Weights(),test_shaping=False,protect_texture=False,test_noise=True)
    assert calls and r['noise_tested'] and not r['protect_texture']
    calls.clear()
    r=simplify(p,x,Weights(),test_shaping=False,protect_texture=True,test_noise=False)
    assert not calls and not r['noise_tested'] and r['protect_texture']


def test_shared_candidate_can_be_resimplified_after_serialization():
    from lab.compact import validate_simplification
    p=architecture(carrier(),'excitation-partagee')
    p=Patch.model_validate_json(p.model_dump_json());x=render(p)
    _,seeds=validate_simplification(p)
    assert len(seeds)==1 and seeds[0].type=='modal'
    r=simplify(p,x,Weights(),tolerance=0,test_shaping=False,test_noise=False)
    assert r['original']==p.model_dump() and r['final']<=r['limit']
    assert np.max(abs(render(Patch.model_validate(r['patch']))-x))<1e-10


def test_shared_midi_anchors_carrier_phase_and_rejects_ambiguous_envelopes():
    from lab.instrument import transpose,first_envelope,phase_wrap
    seed=carrier();seed.nodes[0].parameters.update(onset=.013,phase=.7)
    p=architecture(seed,'excitation-partagee');q,_=transpose(p,81,69)
    osc=next(n for n in q.nodes if n.type=='oscillator')
    assert abs(phase_wrap(osc.parameters['phase']+2*np.pi*600*.013)-.7)<1e-12
    assert first_envelope(p,'m').id=='nl-envelope'
    # A direct bypass makes an inferred common onset incorrect.
    p.nodes.append(Block(id='extra',type='sum'));p.edges=[e for e in p.edges if e.target!='o']+[link('nl-envelope','extra'),link('m','extra'),link('extra','o')]
    assert first_envelope(p,'m') is None
