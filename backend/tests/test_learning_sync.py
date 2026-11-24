import io
import json
from email.message import Message
import time
from threading import Event

import pytest
from fastapi.testclient import TestClient

from lab import learning_store, learning_sync
from lab.app import app


HISTORY = {'sustained': {'adsr': {'contributors': 5, 'mean': .25}}}
SNAPSHOT = {'version': learning_sync.SUMMARY_VERSION, 'history': HISTORY}


def test_snapshot_exchange_is_bounded_read_only_and_keeps_last_good_copy(tmp_path, monkeypatch):
    path = tmp_path/'community-summary.json'
    payload = json.dumps(SNAPSHOT).encode()

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == learning_sync.PUBLIC_SUMMARY
            assert request.get_method() == 'GET'
            assert request.header_items() == [('Accept', 'application/json')]
            assert timeout == 8
            response = io.BytesIO(payload)
            response.status = 200
            response.headers = Message()
            response.headers['Content-Type'] = 'application/json'
            return response

    monkeypatch.setattr(learning_sync, 'build_opener', lambda handler: Opener())
    learning_sync.sync_once(path)
    assert learning_sync.read_snapshot(path) == HISTORY
    for bad in (b' '*5000, b'{}', json.dumps({**SNAPSHOT,'history':{
            'sustained':{'adsr':{'contributors':4,'mean':.3}}}}).encode()):
        payload = bad
        with pytest.raises(ValueError):
            learning_sync.sync_once(path)
        assert learning_sync.read_snapshot(path) == HISTORY
    payload = json.dumps({**SNAPSHOT,'history':{}}).encode()
    learning_sync.sync_once(path)
    assert learning_sync.read_snapshot(path) == {}
    assert not list(tmp_path.glob('tmp*'))


def test_expired_or_linked_snapshot_is_ignored(tmp_path):
    path = tmp_path/'community-summary.json'
    path.write_text(json.dumps({'received': int(time.time())-learning_sync.MAX_AGE-2, 'summary': SNAPSHOT}))
    assert learning_sync.read_snapshot(path) is None
    path.write_text(json.dumps({'received': int(time.time()), 'summary': SNAPSHOT}))
    link = tmp_path/'link'
    link.symlink_to(path)
    assert learning_sync.read_snapshot(link) is None


def test_public_summary_contains_only_local_aggregate_and_never_the_mirror(tmp_path, monkeypatch):
    monkeypatch.setenv('RESONANT_LEARNING_SYNC_DIR', str(tmp_path.resolve()))
    path = learning_sync.snapshot_path()
    path.write_text(json.dumps({'received': int(time.time()), 'summary': SNAPSHOT}))
    client = TestClient(app)
    assert client.get('/api/acoustic-learning').json() == {'history': HISTORY, 'source': 'production'}
    app.dependency_overrides.clear()
    response = client.get('/api/acoustic-learning/public-summary')
    assert response.status_code == 200
    assert response.json() == {'version':learning_sync.SUMMARY_VERSION, 'history':learning_store.summary()}
    assert response.json()['history'] == {}
    assert 'set-cookie' not in response.headers
    assert client.get('/api/acoustic-learning/consent').status_code == 401
    assert client.post('/api/acoustic-learning', json={}).status_code == 401


def test_local_server_starts_and_stops_synchronization(tmp_path, monkeypatch):
    started, finished = Event(), Event()
    monkeypatch.setenv('RESONANT_LEARNING_SYNC_DIR', str(tmp_path.resolve()))
    def synchronize(path, stop):
        assert path == tmp_path.resolve()/'community-summary.json'
        started.set()
        stop.wait(3)
        finished.set()
    monkeypatch.setattr(learning_sync, 'synchronize', synchronize)
    with TestClient(app) as client:
        assert started.wait(1)
        assert client.get('/api/health').status_code == 200
        assert not finished.is_set()
    assert finished.wait(1)
