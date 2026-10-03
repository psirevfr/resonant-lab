import numpy as np
import pytest
from fastapi.testclient import TestClient
from lab.app import app
from lab.auth import require_user
from lab.schema import Patch,Block,Weights
from lab.identify import link
from lab.graph import render
from lab.instrument import expand_modes,collapse_modes,prepare,transpose,physical_count
from lab.texture import band_errors,fit_texture
from lab.metrics import Objective


def source():
    return Patch(duration=.3,nodes=[Block(id='m',type='modal',parameters={'frequency':440,'amplitude':.2,'phase':.7,'tau':.2,'attack':.002,'onset':.014}),Block(id='out',type='output')],edges=[link('m','out')])


def test_expansion_is_exact_including_nonzero_onset_phase():
    p=source();before=p.model_dump();q=expand_modes(p)
    assert len(q.nodes)==physical_count(p)==3
    assert np.max(abs(render(p)-render(q)))<1e-12
    assert np.max(abs(render(p)-render(collapse_modes(q))))<1e-12
    assert p.model_dump()==before
    assert np.array_equal(render(q),render(Patch.model_validate_json(q.model_dump_json())))


def test_midi_pitch_velocity_release_and_nyquist():
    p=source();q,_=transpose(p,69,69)
    assert np.allclose(render(q),render(p),atol=1e-12)
    up,_=transpose(p,81,69);expected=p.model_copy(deep=True);expected.nodes[0].parameters['frequency']=880
    assert np.allclose(render(up),render(expected),atol=1e-12)
    soft,_=transpose(p,69,69,64)
    assert np.allclose(render(soft),render(p)*64/127,atol=1e-12)
    silent,_=transpose(p,69,69,0);assert not np.any(render(silent))
    released,_=transpose(p,69,69,gate=.03)
    assert np.max(abs(render(released)[int(.24*p.sample_rate):]))==0
    p.nodes[0].parameters['frequency']=18000
    high,muted=transpose(p,81,69)
    assert muted==['m'] and not np.any(render(high))


def test_midi_reserved_ids_and_preparation_idempotence():
    p=prepare(source());assert prepare(p)==p
    p.nodes=[n for n in p.nodes if n.id!='keyboard-adsr'];p.edges=[link('m','m-env'),link('m-env','keyboard-velocity'),link('keyboard-velocity','out')]
    with pytest.raises(ValueError,match='incomplets'):prepare(p)


def test_band_diagnostics_detect_quiet_missing_treble():
    fs=44100;t=np.arange(fs//4)/fs;low=np.sin(2*np.pi*220*t);high=.02*np.sin(2*np.pi*9000*t)
    errors=band_errors(low+high,low,fs)
    assert errors['aigu']>.9 and errors['grave']<.001


def test_noise_texture_has_explicit_amplification_and_filters():
    p=source();x=render(p);x+=np.random.default_rng(42).normal(0,.01,len(x))*np.exp(-np.arange(len(x))/p.sample_rate/.05)
    q=fit_texture(p,x,Objective(x,p.sample_rate,Weights()))
    assert {'noise','highpass','lowpass','envelope','gain','sum'}<=set(n.type for n in q.nodes)
    assert np.isfinite(render(q)).all()
    assert np.array_equal(render(q),render(Patch.model_validate_json(q.model_dump_json())))


def test_audio_routes_coexist_with_account_routes_and_require_auth():
    c=TestClient(app);p=source().model_dump()
    assert c.post('/api/instrument/prepare',json=p).status_code==200
    r=c.post('/api/instrument/note',json={'patch':p,'note':69,'reference_note':69})
    assert r.status_code==200 and r.content[:4]==b'RIFF'
    assert c.post('/api/instrument/note',json={'patch':p,'note':109}).status_code==422
    app.dependency_overrides.pop(require_user)
    assert c.post('/api/instrument/prepare',json=p).status_code==401
    assert c.get('/dashboard').status_code==401
    assert c.get('/login').status_code==200
    assert c.get('/api/health').status_code==200


def test_shared_envelope_replaces_three_controls_without_hidden_sources():
    from lab.shared_envelopes import share_envelopes
    from lab.instrument import physical_count
    p=source();p.nodes.pop();p.nodes.extend([p.nodes[0].model_copy(update={'id':'n'},deep=True),p.nodes[0].model_copy(update={'id':'o'},deep=True),Block(id='mix',type='sum'),Block(id='out',type='output')])
    p.nodes[1].parameters['frequency']=701;p.nodes[2].parameters['frequency']=902
    p.edges=[link(k,'mix') for k in ('m','n','o')]+[link('mix','out')]
    q=share_envelopes(p,1)
    assert physical_count(q)==physical_count(p)-1
    assert sum(n.type=='oscillator' for n in q.nodes)==3
    assert sum(n.type=='envelope' for n in q.nodes)==1
    assert np.allclose(render(p),render(q),atol=1e-12)
    assert np.allclose(render(p),render(collapse_modes(q)),atol=1e-12)
    shifted,_=transpose(q,81,69)
    shifted_original,_=transpose(p,81,69)
    assert np.allclose(render(shifted),render(shifted_original),atol=1e-12)
