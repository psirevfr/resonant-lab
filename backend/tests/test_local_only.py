"""The normal web process admits inputs, never heavy legacy CPU calculations."""
import importlib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from lab.app import app
from lab import job_store


def patch():
    return {'duration':.05,'nodes':[{'id':'osc','type':'oscillator'},{'id':'out','type':'output'}],
            'edges':[{'id':'e','source':'osc','target':'out'}]}


def test_default_blocks_every_heavy_route_before_loading_or_computing(monkeypatch):
    monkeypatch.delenv('RESONANT_SERVER_COMPUTE',raising=False)
    module=importlib.import_module('lab.app')
    def unexpected(*args,**kwargs):
        pytest.fail('A disabled server calculation must not load input, compute or enqueue')
    for name in ('get_recording','analyze','render','simulate_rc'):
        monkeypatch.setattr(module,name,unexpected)
    monkeypatch.setattr(job_store,'enqueue',unexpected)
    model=patch()
    requests={
        '/api/analyze':{'audio_id':'synthetic','duration':.05},
        '/api/generate':{'audio_id':'synthetic','duration':.05},
        '/api/compact':{'patch':model,'audio_id':'synthetic'},
        '/api/optimize':{'patch':model,'audio_id':'synthetic'},
        '/api/render':{'patch':model,'audio_id':'synthetic'},
        '/api/instrument/note':{'patch':model},
        '/api/circuit/simulate':{}
    }
    client=TestClient(app)
    for route,body in requests.items():
        response=client.post(route,json=body,headers={'Idempotency-Key':'disabled-test'})
        assert response.status_code==503,(route,response.text)
        assert response.json()['detail']=='Le calcul serveur est désactivé. Utilisez le calcul local sur cet appareil.'
        assert response.headers['cache-control']=='no-store'
    assert client.get('/api/jobs').json()==[]


@pytest.mark.parametrize('value',['0','true','yes',''])
def test_only_exact_opt_in_enables_legacy_cpu_routes(monkeypatch,value):
    monkeypatch.setenv('RESONANT_SERVER_COMPUTE',value)
    assert TestClient(app).post('/api/analyze',json={'audio_id':'synthetic'}).status_code==503


def test_explicit_opt_in_preserves_legacy_api_for_controlled_compatibility(monkeypatch):
    monkeypatch.setenv('RESONANT_SERVER_COMPUTE','1')
    module=importlib.import_module('lab.app');client=TestClient(app)
    audio=client.post('/api/demo').json()['id'];calls=[]
    monkeypatch.setattr(module,'analyze',lambda *args:calls.append(True) or {'synthetic':True})
    response=client.post('/api/analyze',json={'audio_id':audio,'duration':.05,'max_partials':1})
    assert response.status_code==200 and response.json()=={'synthetic':True} and calls==[True]


def test_local_input_validation_and_old_result_access_remain_available(monkeypatch):
    monkeypatch.delenv('RESONANT_SERVER_COMPUTE',raising=False)
    client=TestClient(app);audio=client.post('/api/demo').json()['id']
    model=patch()
    assert client.post('/api/patch/validate',json=model).status_code==200
    result=client.post('/api/compute/input',json={'kind':'generate','request':{'audio_id':audio,'duration':.05,'max_partials':1}})
    assert result.status_code==200 and len(result.content)>0
    assert result.headers['content-type']=='application/octet-stream'
    task=job_store.enqueue(1,'generate',{'audio_id':audio,'duration':.05},np.zeros(2205),44100,'previous-result')
    assert job_store.claim('synthetic-worker')==task['id']
    job_store.finish(task['id'],'synthetic-worker','succeeded',{'synthetic':True})
    assert client.get(task['status_url']).status_code==200
    assert client.get(task['result_url']).json()=={'synthetic':True}
    assert client.get('/api/health').json()=={'status':'ok','version':'1.1.0'}
