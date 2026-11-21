"""Uploads and generated examples share persistent quotas and one decoding slot."""
import importlib
import numpy as np
from fastapi.testclient import TestClient
from lab.app import app,upload_guard
from lab.auth import require_api_user
from lab.audio import wav_bytes


def assert_limited(response):
    assert response.status_code==429
    assert int(response.headers['retry-after'])>0
    assert response.headers['cache-control']=='no-store'


def test_uploads_and_demos_share_owner_quota_and_rejected_calls_do_no_work(monkeypatch):
    module=importlib.import_module('lab.app');client=TestClient(app)
    raw=wav_bytes(np.zeros(2205),44100)
    # Alternate both entrances; a separate quota for each would admit too much.
    for i in range(20):
        response=client.post('/api/demo') if i%2 else client.post('/api/audio',files={'file':('synthetic.wav',raw,'audio/wav')})
        assert response.status_code==200,response.text
    def unexpected(*args,**kwargs):
        raise AssertionError('Rejected admission must not calculate, decode or persist audio')
    for name in ('read_wav','wav_bytes','store_audio','view'):
        monkeypatch.setattr(module,name,unexpected)
    assert_limited(client.post('/api/demo'))
    assert_limited(client.post('/api/audio',files={'file':('synthetic.wav',raw,'audio/wav')}))
    # Replacing the client/cookies does not replace its owner quota.
    assert_limited(TestClient(app).post('/api/demo'))


def test_ip_quota_is_shared_across_different_owners(monkeypatch):
    module=importlib.import_module('lab.app');client=TestClient(app)
    for owner in range(1,5):
        app.dependency_overrides[require_api_user]=lambda owner=owner:{'id':owner,'username':'synthetic'}
        for _ in range(10):assert client.post('/api/demo').status_code==200
    app.dependency_overrides[require_api_user]=lambda:{'id':99,'username':'synthetic'}
    monkeypatch.setattr(module,'store_audio',lambda *args:(_ for _ in ()).throw(AssertionError('IP quota was bypassed')))
    assert_limited(client.post('/api/demo'))


def test_shared_decoding_slot_rejects_demo_and_upload_and_recovers(monkeypatch):
    module=importlib.import_module('lab.app');client=TestClient(app)
    raw=wav_bytes(np.zeros(2205),44100)
    assert upload_guard.acquire(blocking=False)
    try:
        assert_limited(client.post('/api/demo'))
        assert_limited(client.post('/api/audio',files={'file':('synthetic.wav',raw,'audio/wav')}))
    finally:upload_guard.release()
    # A decoding failure must release the same slot too.
    original=module.read_wav
    monkeypatch.setattr(module,'read_wav',lambda *args:(_ for _ in ()).throw(ValueError('synthetic decoding failure')))
    assert client.post('/api/demo').status_code==422
    monkeypatch.setattr(module,'read_wav',original)
    assert client.post('/api/demo').status_code==200
