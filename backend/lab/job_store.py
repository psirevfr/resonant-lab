"""One persistent SQLite queue for all heavy computations.

Only short transactions. Inputs are bounded mono NPY blobs; no public file paths.
A worker lease is an execution fence: expired jobs fail, never automatically retry.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import os
import logging
import time
from uuid import uuid4
import numpy as np
from fastapi import HTTPException
from .auth import get_db

TERMINAL=('succeeded','failed','cancelled')
LEASE_SECONDS=30
PUBLIC_COLUMNS='id,kind,status,created,started,finished,error,progress,cancel,timings'
log=logging.getLogger('resonant.jobs')

@contextmanager
def db():
    c=get_db()
    try:yield c;c.commit()
    except BaseException:c.rollback();raise
    finally:c.close()


def init_jobs():
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS compute_jobs (
          id TEXT PRIMARY KEY, owner INTEGER NOT NULL, kind TEXT NOT NULL,
          status TEXT NOT NULL, created REAL NOT NULL, started REAL, finished REAL,
          heartbeat REAL, worker TEXT, request TEXT NOT NULL, input BLOB,
          result TEXT, progress TEXT NOT NULL DEFAULT '{}', error TEXT,
          cancel INTEGER NOT NULL DEFAULT 0, idem TEXT NOT NULL, fingerprint TEXT NOT NULL,
          UNIQUE(owner,idem));
          CREATE INDEX IF NOT EXISTS jobs_queue ON compute_jobs(status,created);
          CREATE INDEX IF NOT EXISTS jobs_owner ON compute_jobs(owner,created);
          CREATE TABLE IF NOT EXISTS compute_settings (id INTEGER PRIMARY KEY CHECK(id=1), concurrency INTEGER NOT NULL);
          INSERT OR IGNORE INTO compute_settings VALUES (1,1);
          CREATE TABLE IF NOT EXISTS compute_workers (id TEXT PRIMARY KEY, heartbeat REAL NOT NULL);''')
        c.execute('BEGIN IMMEDIATE')
        if 'timings' not in {r['name'] for r in c.execute('PRAGMA table_info(compute_jobs)')}:
            c.execute("ALTER TABLE compute_jobs ADD COLUMN timings TEXT NOT NULL DEFAULT '{}'")


def configure(concurrency):
    if not 1<=concurrency<=4:raise ValueError('Concurrence autorisée : 1 à 4.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT concurrency FROM compute_settings WHERE id=1').fetchone()[0]
        if current!=concurrency and c.execute("SELECT count(*) FROM compute_jobs WHERE status='running'").fetchone()[0]:raise ValueError('Arrêtez les calculs avant de modifier la concurrence globale.')
        c.execute('UPDATE compute_settings SET concurrency=? WHERE id=1',(concurrency,))


def enqueue(owner,kind,request,x,fs,idem):
    if not idem or len(idem)>100:raise HTTPException(422,'En-tête Idempotency-Key requis (1 à 100 caractères).')
    payload=json.dumps({'request':request,'sample_rate':fs},sort_keys=True,separators=(',',':'),allow_nan=False)
    buf=io.BytesIO();np.save(buf,np.asarray(x,dtype=np.float64),allow_pickle=False);data=buf.getvalue()
    if len(data)>10_000_000:raise HTTPException(413,'Sélection trop volumineuse pour la file de calcul.')
    fingerprint=hashlib.sha256(kind.encode()+payload.encode()+data).hexdigest()
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM compute_jobs WHERE owner=? AND idem=?',(owner,idem)).fetchone()
        if old:
            if old['fingerprint']!=fingerprint:raise HTTPException(409,'Cette clé de soumission correspond à une autre demande.')
            return public(old)
        active=c.execute("SELECT owner FROM compute_jobs WHERE status IN ('queued','running')").fetchall()
        if len(active)>=int(os.environ.get('RESONANT_MAX_JOBS','6')) or sum(r['owner']==owner for r in active)>=2:
            raise HTTPException(429,'File de calcul pleine. Réessayez plus tard.',headers={'Retry-After':'15'})
        key=uuid4().hex
        c.execute("INSERT INTO compute_jobs(id,owner,kind,status,created,request,input,idem,fingerprint) VALUES (?,?,?,'queued',?,?,?,?,?)",(key,owner,kind,time.time(),payload,data,idem,fingerprint))
        return public(c.execute('SELECT * FROM compute_jobs WHERE id=?',(key,)).fetchone())


def public(row,include_result=False):
    result={k:row[k] for k in ('id','kind','status','created','started','finished','error')}
    result['timings']=json.loads(row['timings']);result['queue_wait_ms']=max(0,((row['started'] or row['finished'] or time.time())-row['created'])*1000)
    result['progress']=json.loads(row['progress']);result['cancel_requested']=bool(row['cancel'])
    result['status_url']=f"/api/jobs/{row['id']}";result['result_url']=f"/api/jobs/{row['id']}/result"
    if include_result and row['status']=='succeeded':result['result']=json.loads(row['result'])
    return result


def read(key,owner,include_result=False):
    with db() as c:row=c.execute(f"SELECT {PUBLIC_COLUMNS}{',result' if include_result else ''} FROM compute_jobs WHERE id=? AND owner=?",(key,owner)).fetchone()
    if not row:raise HTTPException(404,'Tâche absente ou expirée.')
    result=public(row,include_result)
    if row['status']=='queued':
        result['worker']=worker_status()
        result['queue_warning']=('Aucun worker de calcul ne répond sur cette base. La demande est conservée ; prévenir l’administrateur.' if not result['worker']['available'] else ('Attente prolongée : le worker est disponible, mais la capacité de calcul est occupée.' if result['queue_wait_ms']>30000 else None))
    return result


def recent(owner):
    with db() as c:return [public(r) for r in c.execute(f'SELECT {PUBLIC_COLUMNS} FROM compute_jobs WHERE owner=? ORDER BY created DESC LIMIT 20',(owner,))]


def cancel(key,owner):
    with db() as c:
        c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT status FROM compute_jobs WHERE id=? AND owner=?',(key,owner)).fetchone()
        if not r:raise HTTPException(404,'Tâche absente ou expirée.')
        if r['status']=='queued':c.execute("UPDATE compute_jobs SET cancel=1,status='cancelled',finished=?,input=NULL WHERE id=?",(time.time(),key))
        elif r['status']=='running':c.execute('UPDATE compute_jobs SET cancel=1 WHERE id=?',(key,))
    return read(key,owner)


def claim(worker):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        cap=c.execute('SELECT concurrency FROM compute_settings WHERE id=1').fetchone()[0]
        if c.execute("SELECT count(*) FROM compute_jobs WHERE status='running'").fetchone()[0]>=cap:return None
        row=c.execute("SELECT id FROM compute_jobs WHERE status='queued' ORDER BY created,id LIMIT 1").fetchone()
        if not row:return None
        now=time.time();log.info('job=%s transition=queued_to_running worker=%s queue_ms=%.3f',row['id'],worker,(now-c.execute('SELECT created FROM compute_jobs WHERE id=?',(row['id'],)).fetchone()[0])*1000);c.execute("UPDATE compute_jobs SET status='running',started=?,heartbeat=?,worker=? WHERE id=? AND status='queued'",(now,now,worker,row['id']))
        return row['id']


def load(key,worker):
    with db() as c:row=c.execute("SELECT request,input,kind FROM compute_jobs WHERE id=? AND worker=? AND status='running'",(key,worker)).fetchone()
    if not row:raise RuntimeError('Lease lost')
    return row['kind'],json.loads(row['request']),np.load(io.BytesIO(row['input']),allow_pickle=False)


def heartbeat(key,worker):
    with db() as c:
        r=c.execute("UPDATE compute_jobs SET heartbeat=? WHERE id=? AND worker=? AND status='running'",(time.time(),key,worker))
        if r.rowcount!=1:return None
        return bool(c.execute('SELECT cancel FROM compute_jobs WHERE id=?',(key,)).fetchone()[0])


def progress(key,worker,value):
    with db() as c:c.execute("UPDATE compute_jobs SET progress=? WHERE id=? AND worker=? AND status='running'",(json.dumps(value,allow_nan=False),key,worker))


def finish(key,worker,status,result=None,error=None,timings=None):
    encoded=json.dumps(result,allow_nan=False) if result is not None else None
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute("SELECT cancel FROM compute_jobs WHERE id=? AND worker=? AND status='running'",(key,worker)).fetchone()
        if not r:return False
        if r['cancel'] and status=='succeeded':status='cancelled';encoded=None
        c.execute("UPDATE compute_jobs SET status=?,finished=?,result=?,error=?,input=NULL,heartbeat=NULL WHERE id=?",(status,time.time(),encoded,error,key))
        if timings is not None:c.execute('UPDATE compute_jobs SET timings=? WHERE id=?',(json.dumps(timings,allow_nan=False),key))
        log.info('job=%s transition=running_to_%s worker=%s',key,status,worker)
        return True


def maintain(now=None):
    now=time.time() if now is None else now
    retention=max(3600,int(os.environ.get('RESONANT_JOB_RETENTION_SECONDS','604800')))
    queued_ttl=max(60,int(os.environ.get('RESONANT_QUEUE_TTL_SECONDS','86400')))
    with db() as c:
        c.execute("UPDATE compute_jobs SET status='failed',finished=?,input=NULL,error='Calcul interrompu. Vous pouvez lancer une nouvelle tentative.' WHERE status='running' AND (heartbeat<? OR (heartbeat IS NULL AND coalesce(started,created)<?))",(now,now-LEASE_SECONDS,now-LEASE_SECONDS))
        c.execute("UPDATE compute_jobs SET status='failed',finished=?,input=NULL,error='Attente expirée. Le worker est peut-être indisponible.' WHERE status='queued' AND created<?",(now,now-queued_ttl))
        c.execute("DELETE FROM compute_jobs WHERE status IN ('succeeded','failed','cancelled') AND finished<?",(now-retention,))
        c.execute('DELETE FROM revoked_sessions WHERE expires<?',(now,))
        c.execute('DELETE FROM compute_workers WHERE heartbeat<?',(now-86400,))


def replay(owner,kind,request,idem):
    if not idem or len(idem)>100:raise HTTPException(422,'En-tête Idempotency-Key requis (1 à 100 caractères).')
    with db() as c:row=c.execute('SELECT * FROM compute_jobs WHERE owner=? AND idem=?',(owner,idem)).fetchone()
    if not row:return None
    if row['kind']!=kind or json.loads(row['request'])['request']!=request:raise HTTPException(409,'Cette clé de soumission correspond à une autre demande.')
    return public(row)


def worker_seen(worker,now=None):
    with db() as c:
        c.execute('INSERT INTO compute_workers(id,heartbeat) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat',(worker,time.time() if now is None else now))


def worker_gone(worker):
    with db() as c:c.execute('DELETE FROM compute_workers WHERE id=?',(worker,))


def worker_status(now=None):
    now=time.time() if now is None else now
    with db() as c:seen=c.execute('SELECT max(heartbeat) FROM compute_workers').fetchone()[0]
    return {'available':bool(seen is not None and now-seen<=LEASE_SECONDS),'last_seen_age_seconds':max(0,now-seen) if seen is not None else None}
