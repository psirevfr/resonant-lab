"""Predeclared comb tolerance: 2e-12 absolute vs recurrence/lfilter.
Generation quality guard: each original objective term and band <= reference+1e-12.
"""
import numpy as np
import pytest
from scipy import signal
from lab.blocks import process,parameters,coefficients
from lab.schema import Block,Patch,Weights
from lab.graph import render
from lab.identify import generate,link
from lab.transfer import response,describe


@pytest.mark.parametrize('fs',[44100,48000,96000])
def test_comb_matches_reference_filter_without_dense_processing(fs):
    for f in (20,261.63,fs*.45):
        for g in (0,.95,.9999):
            p=parameters('comb',{'frequency':f,'feedback':g},fs)
            x=np.random.default_rng(7).normal(size=10000)
            b,a=coefficients('comb',p,fs)
            y=process('comb',p,[x],fs,len(x))
            assert np.max(abs(y-signal.lfilter(b,a,x)))<2e-12
            assert np.isfinite(y).all() and np.max(abs(y))<=np.max(abs(x))+1e-12


def test_comb_actual_harmonic_response_and_fractional_delay():
    fs=48000;p=parameters('comb',{'frequency':400,'feedback':.99},fs)
    h=response('comb',p,fs,np.array([400.,800.,600.]))
    assert abs(h[0])==pytest.approx(1,abs=1e-12)
    assert abs(h[1])==pytest.approx(1,abs=1e-12)
    assert abs(h[2])<.006
    d=describe(Block(id='comb',type='comb',parameters=p),fs)
    assert d['stable'] and d['dc_gain']==1 and d['poles'] is None
    with pytest.raises(ValueError):parameters('comb',{'feedback':1},fs)
    with pytest.raises(ValueError):parameters('comb',{'frequency':float('nan')},fs)


def test_comb_long_decay_finite_and_reproducible():
    fs=44100;p=parameters('comb',{'frequency':20.1,'feedback':.9999},fs)
    x=np.zeros(fs*4);x[0]=4
    y=process('comb',p,[x],fs,len(x))
    assert np.array_equal(y,process('comb',p,[x],fs,len(x)))
    assert np.isfinite(y).all() and y[0]==pytest.approx(.0004)


def test_generation_explores_compact_topologies_but_keeps_every_quality_guard():
    fs=44100;t=np.arange(6615)/fs
    x=(1-np.exp(-t/.003))*np.exp(-t/.3)*(.3*np.sin(2*np.pi*300*t)+.08*np.sin(2*np.pi*600*t))
    r=generate(x,fs,4,weights=Weights(),refine_modes=False,include_impact=False,detailed=False)
    candidates=r['candidates'];ref=next(c for c in candidates if c['reference']);best=candidates[0]
    assert any(any(n['type']=='comb' for n in c['patch']['nodes']) for c in candidates)
    assert any(any(n['type']=='asymmetric_saturation' for n in c['patch']['nodes']) for c in candidates)
    assert best['patch']==r['patch'] and ref['patch']==r['reference_patch']
    assert best['within_tolerance'] and not best['rejection_reasons']
    for k,v in best['errors'].items():assert v<=ref['errors'][k]+1e-12
    for k,v in best['bands'].items():assert v<=ref['bands'][k]+1e-12
    assert best['modules']<=ref['modules']
    for c in candidates:
        if c['patch']['name'].startswith('Compact · enveloppes partagées'):
            for node in c['patch']['nodes']:
                if node['type']=='sum':
                    assert sum(e['target']==node['id'] for e in c['patch']['edges'])>1
    assert np.array_equal(render(Patch.model_validate(r['patch'])),render(Patch.model_validate_json(Patch.model_validate(r['patch']).model_dump_json())))


def test_comb_midi_clamps_to_supported_frequency():
    from lab.instrument import transpose
    p=Patch(duration=.05,nodes=[Block(id='n',type='noise'),Block(id='c',type='comb'),Block(id='o',type='output')],edges=[link('n','c'),link('c','o')])
    q,_=transpose(p,0,69)
    assert next(n for n in q.nodes if n.type=='comb').parameters['frequency']>=20
    assert np.isfinite(render(q)).all()
