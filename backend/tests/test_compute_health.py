import time
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient
from lab.app import app
from lab.auth import database_path
from lab import job_store as store
from lab.compute import compute
from test_jobs import enqueue


def test_worker_absent_is_visible_without_failing_or_requeueing():
    job=enqueue();state=store.read(job['id'],1)
    assert state['status']=='queued' and not state['worker']['available']
    assert 'Aucun worker' in state['queue_warning']
    store.worker_seen('worker');assert store.read(job['id'],1)['worker']['available']
    store.worker_gone('worker');assert not store.worker_status()['available']
    assert store.read(job['id'],1)['status']=='queued'


def test_worker_lease_expires_and_no_double_execution():
    job=enqueue();store.worker_seen('crashed',time.time()-31)
    assert not store.worker_status()['available']
    assert store.claim('crashed')==job['id']
    store.maintain(time.time()+31)
    assert store.read(job['id'],1)['status']=='failed'
    assert store.claim('replacement') is None
    assert not store.finish(job['id'],'crashed','succeeded',{'late':True})


def test_relative_database_is_rejected(monkeypatch):
    monkeypatch.setenv('RESONANT_DB_PATH','users.db')
    with pytest.raises(RuntimeError,match='absolu'):database_path()


def test_local_input_is_exact_double_and_does_not_queue():
    import numpy as np
    from lab.app import get_recording
    from lab.audio import excerpt
    c=TestClient(app);audio=c.post('/api/demo').json()
    request={'audio_id':audio['id'],'duration':.05,'max_partials':1,'refine_modes':False,'detailed':False,'include_impact':False}
    response=c.post('/api/compute/input',json={'kind':'generate','request':request})
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    samples=np.frombuffer(response.content,dtype='<f8')
    assert np.array_equal(samples,excerpt(get_recording(audio['id'],1),0,.05,44100))
    assert store.recent(1)==[]
    result=compute('generate',request,samples,44100)
    assert result['patch'] and result['compute_metrics']['algorithm_ms']>0


def test_local_inputs_validate_and_isolate_owners():
    from lab.auth import require_api_user
    c=TestClient(app);audio=c.post('/api/demo').json();req={'audio_id':audio['id'],'duration':.05}
    app.dependency_overrides[require_api_user]=lambda:{'id':2,'username':'other','email':'other@example.invalid'}
    assert c.post('/api/compute/input',json={'kind':'generate','request':req}).status_code==404
    assert c.post('/api/compute/input',json={'kind':'unknown','request':req}).status_code==422


def test_numerical_bundle_allowlist_excludes_private_modules(tmp_path):
    import importlib.util,zipfile
    spec=importlib.util.spec_from_file_location('prepare',Path(__file__).resolve().parents[2]/'scripts/prepare_local_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest=module.prepare(tmp_path)
    assert not manifest['ready']
    with zipfile.ZipFile(tmp_path/'numerical.zip') as archive:
        assert 'lab/compute.py' in archive.namelist()
        assert not {'lab/auth.py','lab/app.py','lab/worker.py','drive_token.json','.env'}&set(archive.namelist())


def test_legacy_running_job_without_heartbeat_is_terminal():
    job=enqueue();store.claim('crashed')
    with store.db() as c:c.execute('UPDATE compute_jobs SET heartbeat=NULL,started=NULL,created=? WHERE id=?',(time.time()-60,job['id']))
    store.maintain();assert store.read(job['id'],1)['status']=='failed'


def test_temporary_sqlite_lock_does_not_duplicate_claim():
    from concurrent.futures import ThreadPoolExecutor
    from lab.auth import get_db
    job=enqueue();connection=get_db();connection.execute('BEGIN IMMEDIATE')
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(store.claim,'waiting-worker')
        time.sleep(.1);assert not future.done()
        connection.rollback();connection.close()
        assert future.result(timeout=3)==job['id']
    assert store.claim('second-worker') is None


def test_idle_worker_presence_and_shutdown_are_real():
    import os,subprocess,sys
    process=subprocess.Popen([sys.executable,'-m','lab.worker'],env=dict(os.environ),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        end=time.monotonic()+5
        while time.monotonic()<end and not store.worker_status()['available']:time.sleep(.05)
        assert store.worker_status()['available']
    finally:process.terminate();process.wait(timeout=5)
    assert not store.worker_status()['available']


def test_runtime_directory_cannot_serve_accidentally_copied_secret(tmp_path,monkeypatch):
    import importlib,json
    module=importlib.import_module('lab.app');monkeypatch.setattr(module,'COMPUTE_RUNTIME',tmp_path)
    (tmp_path/'private.env').write_text('test-private-data')
    (tmp_path/'manifest.json').write_text(json.dumps({'files':{'private.env':{}},'ready':False}))
    response=TestClient(app).get('/compute-runtime/private.env')
    assert response.status_code==404 and 'test-private-data' not in response.text


def test_invalid_local_kind_returns_422_not_500():
    assert TestClient(app).post('/api/compute/input',json={'kind':[],'request':{}}).status_code==422


def test_runtime_incomplete_dependencies_cannot_be_announced_ready(tmp_path):
    import importlib.util,json
    spec=importlib.util.spec_from_file_location('prepare',Path(__file__).resolve().parents[2]/'scripts/prepare_local_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    packages={name:{'depends':[],'file_name':name+'.whl','sha256':'missing'} for name in ('numpy','scipy','pydantic')}
    for filename in module.CORE:(tmp_path/filename).write_bytes(b'core')
    (tmp_path/'pyodide-lock.json').write_text(json.dumps({'packages':packages}))
    (tmp_path/'private.env').write_text('must not be public')
    manifest=module.prepare(tmp_path)
    assert not manifest['ready'] and 'private.env' not in manifest['files']


def test_generation_keeps_actual_resampled_excerpt_length():
    import numpy as np
    from lab.compute import validate_input
    # .05005 seconds at 8 kHz rounds to 400 source frames, or 2205 at 44.1 kHz;
    # independently rounding .05005*44100 would produce 2207 instead.
    x=np.zeros(2205)
    _,validated=validate_input('generate',{'audio_id':'test','duration':.05005},x,44100)
    assert len(validated)==2205 and np.array_equal(validated,x)


def test_parallel_additive_initialization_preserves_existing_accounts(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from lab.auth import init_db
    path=tmp_path/'legacy.sqlite';monkeypatch.setenv('RESONANT_DB_PATH',str(path))
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE users (id INTEGER PRIMARY KEY,username TEXT,email TEXT,hashed_password TEXT)')
        c.execute("INSERT INTO users VALUES (1,'synthetic','test@example.invalid','fake-hash')")
    def initialize(_):init_db();store.init_jobs()
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(initialize,range(3)))
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT username FROM users').fetchone()[0]=='synthetic'
        assert 'api_key' in {r[1] for r in c.execute('PRAGMA table_info(users)')}
        assert 'timings' in {r[1] for r in c.execute('PRAGMA table_info(compute_jobs)')}
