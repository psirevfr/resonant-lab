import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from lab.app import app,recordings
from lab.auth import require_api_user
from lab import job_store as s

client=TestClient(app)


def enqueue(i='one',owner=1):
    return s.enqueue(owner,'generate',{'audio_id':'test','duration':.05,'max_partials':1,'refine_modes':False,'detailed':False,'include_impact':False},np.sin(np.arange(2205)*.1),44100,i)


def test_api_accepts_without_computing_and_retries_survive_lost_audio(complete_job):
    audio=client.post('/api/demo').json()
    request={'audio_id':audio['id'],'duration':.05,'max_partials':1,'refine_modes':False,'include_impact':False}
    response=client.post('/api/generate',json=request,headers={'Idempotency-Key':'first'})
    assert response.status_code==202 and response.json()['status']=='queued'
    recordings.clear()
    retry=client.post('/api/generate',json=request,headers={'Idempotency-Key':'first'})
    assert retry.json()['id']==response.json()['id']
    assert client.post('/api/generate',json={**request,'duration':.2},headers={'Idempotency-Key':'first'}).status_code==409
    result=complete_job(response)
    assert client.get(response.json()['result_url']).json()==result
    assert client.get(response.json()['status_url']).json()['status']=='succeeded'


def test_invalid_input_ownership_quota_and_global_claim():
    assert client.post('/api/generate',json={'audio_id':'missing','duration':-1}).status_code==422
    assert s.recent(1)==[]
    audio=client.post('/api/demo').json()
    app.dependency_overrides[require_api_user]=lambda:{'id':2,'username':'other','email':'other@example.invalid'}
    assert client.post('/api/generate',json={'audio_id':audio['id']},headers={'Idempotency-Key':'other'}).status_code==404
    job=enqueue()
    assert client.get(job['status_url']).status_code==404
    assert client.get(job['result_url']).status_code==404
    assert client.post(job['status_url']+'/cancel',json={}).status_code==404
    enqueue('two')
    with pytest.raises(HTTPException) as e:enqueue('three')
    assert e.value.status_code==429
    assert s.claim('worker-a') is not None
    assert s.claim('worker-b') is None


def test_atomic_claim_and_completion_fence():
    job=enqueue()
    with ThreadPoolExecutor(max_workers=5) as pool:claims=list(pool.map(s.claim,[str(i) for i in range(5)]))
    assert claims.count(job['id'])==1
    with s.db() as c:worker=c.execute('SELECT worker FROM compute_jobs').fetchone()[0]
    assert not s.finish(job['id'],'wrong-worker','succeeded',{})
    assert s.finish(job['id'],worker,'succeeded',{'answer':1})
    assert not s.finish(job['id'],worker,'failed',error='late')
    assert s.read(job['id'],1,True)['result']=={'answer':1}


def test_restart_lease_queue_expiry_cleanup_and_input_erasure(monkeypatch):
    job=enqueue();s.claim('dead-worker')
    s.maintain(time.time()+s.LEASE_SECONDS+1)
    state=s.read(job['id'],1)
    assert state['status']=='failed' and state['error']
    assert s.claim('new-worker') is None
    with s.db() as c:assert c.execute('SELECT input FROM compute_jobs').fetchone()[0] is None
    queue=enqueue('queued');s.maintain(time.time()+86401)
    assert s.read(queue['id'],1)['status']=='failed'
    s.maintain(time.time()+700000)
    assert s.recent(1)==[]


def test_cancellation_is_real_and_no_result_leaks():
    job=enqueue();assert s.cancel(job['id'],1)['status']=='cancelled'
    assert s.claim('w') is None
    job=enqueue('running');s.claim('w');s.cancel(job['id'],1)
    assert s.heartbeat(job['id'],'w') is True
    s.finish(job['id'],'w','succeeded',{'ignored':True})
    assert s.read(job['id'],1,True)['status']=='cancelled'
    assert 'result' not in s.read(job['id'],1,True)


def run_worker_until_terminal(timeout=10,job_timeout=10):
    process=subprocess.Popen([sys.executable,'-m','lab.worker','--timeout',str(job_timeout)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            states=s.recent(1)
            if states and states[0]['status'] in s.TERMINAL:return states[0]
            time.sleep(.15)
        raise AssertionError('Worker did not finish in bounded test')
    finally:
        process.terminate();process.wait(timeout=5)


def test_real_isolated_worker_success():
    job=enqueue();state=run_worker_until_terminal()
    assert state['status']=='succeeded',state
    assert 'patch' in s.read(job['id'],1,True)['result']


def test_worker_failure_is_public_and_terminal():
    job=s.enqueue(1,'invalid-kind',{},np.ones(2205),44100,'fail')
    state=run_worker_until_terminal()
    assert state['status']=='failed'
    assert 'Traceback' not in state['error'] and 'invalid-kind' not in state['error']


def test_shared_limit_between_all_kinds():
    enqueue()
    s.enqueue(2,'optimize',{},np.zeros(2205),44100,'optimization')
    s.enqueue(3,'compact',{},np.zeros(2205),44100,'compact')
    assert s.claim('generation-worker')
    assert s.claim('optimization-worker') is None
    assert s.claim('compact-worker') is None


def slow_worker(job_timeout='10'):
    from pathlib import Path
    return subprocess.Popen([sys.executable,str(Path(__file__).with_name('worker_harness.py'))],env={**os.environ,'TEST_TIMEOUT':job_timeout},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def wait_state(key,statuses,seconds=8):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        state=s.read(key,1)
        if state['status'] in statuses:return state
        time.sleep(.1)
    raise AssertionError(f'Expected {statuses}, got {state["status"]}')


def test_worker_hard_timeout_stops_child_and_frees_global_slot():
    job=enqueue();process=slow_worker('1')
    try:
        state=wait_state(job['id'],['failed'])
        assert 'maximale' in state['error']
        assert enqueue('next')['status']=='queued'
    finally:process.terminate();process.wait(timeout=5)


def test_worker_cancels_running_child():
    job=enqueue();process=slow_worker()
    try:
        wait_state(job['id'],['running']);s.cancel(job['id'],1)
        assert wait_state(job['id'],['cancelled'])['status']=='cancelled'
        assert s.read(job['id'],1).get('result') is None
    finally:process.terminate();process.wait(timeout=5)


def test_independent_processes_cannot_claim_same_job():
    enqueue()
    from pathlib import Path
    command=[sys.executable,'-c',"from lab.job_store import claim; print(claim('concurrent'))"]
    processes=[subprocess.Popen(command,stdout=subprocess.PIPE,text=True) for _ in range(3)]
    results=[p.communicate(timeout=10)[0].strip() for p in processes]
    assert sum(r!='None' for r in results)==1


def test_compact_rejects_non_modal_graph_before_queue():
    from lab.schema import Patch,Block,Edge
    audio=client.post('/api/demo').json()
    patch=Patch(duration=.05,nodes=[Block(id='s',type='oscillator'),Block(id='o',type='output')],edges=[Edge(id='e',source='s',target='o')])
    response=client.post('/api/compact',json={'audio_id':audio['id'],'patch':patch.model_dump()})
    assert response.status_code==422
    assert s.recent(1)==[]


def test_backup_preserves_data_and_refuses_overwrite(tmp_path):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('backup_db',Path(__file__).resolve().parents[2]/'scripts/backup_db.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    destination=tmp_path/'backup.sqlite'
    enqueue()
    module.backup(os.environ['RESONANT_DB_PATH'],destination)
    import sqlite3
    with sqlite3.connect(destination) as c:
        assert c.execute('SELECT COUNT(*) FROM compute_jobs').fetchone()[0]==1
    with pytest.raises(FileExistsError):module.backup(os.environ['RESONANT_DB_PATH'],destination)
    assert destination.stat().st_mode&0o777==0o600
