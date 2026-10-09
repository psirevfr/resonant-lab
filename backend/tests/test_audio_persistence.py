import subprocess
import sys
import hashlib
from fastapi.testclient import TestClient
from lab.app import app,recordings,get_recording
from lab.auth import require_api_user
from lab import audio_store


def test_reference_survives_memory_eviction_and_process_cache_loss():
    client=TestClient(app)
    original=client.post('/api/demo').json()['id']
    expected=client.get(f'/api/audio/{original}/wav').content
    for _ in range(5):assert client.post('/api/demo').status_code==200
    assert original not in recordings
    assert client.get(f'/api/audio/{original}/wav').content==expected
    recordings.clear()
    assert client.post('/api/compute/input',json={'kind':'generate','request':{'audio_id':original,'duration':.05}}).status_code==200
    app.dependency_overrides[require_api_user]=lambda:{'id':2}
    assert client.get(f'/api/audio/{original}/wav').status_code==404


def test_quota_rejection_keeps_previous_reference_and_no_orphans(monkeypatch):
    client=TestClient(app);key=client.post('/api/demo').json()['id']
    paths=set(audio_store.directory().glob('*.wav'))
    monkeypatch.setenv('RESONANT_AUDIO_MAX_BYTES','1')
    assert client.post('/api/demo').status_code==507
    assert set(audio_store.directory().glob('*.wav'))==paths
    recordings.clear();assert client.get(f'/api/audio/{key}/wav').status_code==200


def test_expiration_and_symlink_are_not_served(monkeypatch,tmp_path):
    client=TestClient(app);key=client.post('/api/demo').json()['id']
    path=audio_store.directory()/(key+'.wav')
    path.unlink();secret=tmp_path/'secret';secret.write_bytes(b'private');path.symlink_to(secret)
    recordings.clear();assert client.get(f'/api/audio/{key}/wav').status_code==404
    monkeypatch.setenv('RESONANT_AUDIO_TTL_SECONDS','-1')
    audio_store.cleanup()
    assert not path.is_symlink() and secret.read_bytes()==b'private'


def test_path_traversal_cannot_load_private_file():
    assert audio_store.load('../users.db',1) is None


def test_disk_reserve_rejects_without_writing(monkeypatch):
    monkeypatch.setenv('RESONANT_AUDIO_MIN_FREE_BYTES',str(10**18))
    assert TestClient(app).post('/api/demo').status_code==507
    assert list(audio_store.directory().glob('*.wav'))==[]


def test_reference_can_be_loaded_by_an_independent_process():
    client=TestClient(app);key=client.post('/api/demo').json()['id']
    expected=hashlib.sha256(client.get(f'/api/audio/{key}/wav').content).hexdigest()
    result=subprocess.check_output([sys.executable,'-c',
        'import sys,hashlib; from lab.audio_store import load; print(hashlib.sha256(load(sys.argv[1],1).original).hexdigest())',key],text=True)
    assert result.strip()==expected
