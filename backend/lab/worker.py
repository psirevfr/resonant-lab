"""Isolated CPU worker: python -m lab.worker (Linux/macOS)."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
import argparse
import fcntl
import logging
import multiprocessing as mp
from pathlib import Path
import signal
import threading
import time
from uuid import uuid4
from .auth import init_db,get_db
from . import job_store as store

log=logging.getLogger('resonant.worker')


def compute(kind,payload,x,progress,cancel):
    from .schema import GenerateRequest,OptimizeRequest,CompactRequest
    if kind=='generate':
        from .identify import generate
        r=GenerateRequest.model_validate(payload['request'])
        return generate(x,payload['sample_rate'],r.max_partials,r.complexity_penalty,r.weights,r.refine_modes,r.include_impact,r.detailed)
    if kind=='optimize':
        from .optimization import run_optimization
        return run_optimization(OptimizeRequest.model_validate(payload['request']),x,progress,cancel)
    if kind=='compact':
        from .compact import simplify
        r=CompactRequest.model_validate(payload['request'])
        return simplify(r.patch,x,r.weights,r.tolerance,r.test_shaping,r.protect_texture)
    raise ValueError('Unknown job kind')


def execute(key,worker,cancel):
    # Advisory OS slots also bound orphan children while their lease expires.
    # SQLite remains the authority for claiming and publishing job results.
    parent=mp.parent_process()
    def orphan_watch():
        while True:
            time.sleep(2)
            if parent is not None and not parent.is_alive():os._exit(1)
    threading.Thread(target=orphan_watch,daemon=True).start()
    c=get_db()
    try:
        path=Path(c.execute('PRAGMA database_list').fetchone()[2]).resolve()
        cap=c.execute('SELECT concurrency FROM compute_settings WHERE id=1').fetchone()[0]
    finally:c.close()
    directory=path.parent/'.resonant-locks';directory.mkdir(mode=0o700,exist_ok=True)
    slot=None
    while slot is None:
        if cancel.wait(.1):return
        for i in range(cap):
            f=open(directory/f'{path.name}.{i}.lock','a')
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);slot=f;break
            except BlockingIOError:f.close()
    try:
        kind,payload,x=store.load(key,worker);last=[0.]
        def progress(value):
            if time.monotonic()-last[0]>=1:
                store.progress(key,worker,value);last[0]=time.monotonic()
        result=compute(kind,payload,x,progress,cancel)
        store.finish(key,worker,'succeeded',result=result)
    except Exception as exc:
        # No exception text/locals: those can contain filenames or uploaded data.
        log.error('job=%s exception=%s',key,type(exc).__name__)
        store.finish(key,worker,'failed',error='Le calcul a échoué. Vérifiez la sélection et les paramètres, puis réessayez.')
    finally:
        fcntl.flock(slot,fcntl.LOCK_UN);slot.close()


def stop_process(process):
    if process.is_alive():process.terminate();process.join(2)
    if process.is_alive():process.kill();process.join(2)
    process.close()


def run(concurrency=1,timeout=600,stop=None):
    init_db();store.init_jobs();store.configure(concurrency)
    stop=stop or threading.Event();context=mp.get_context('spawn');worker=uuid4().hex;running={};last_cleanup=0
    try:
        while not stop.is_set():
            now=time.monotonic()
            if now-last_cleanup>=10:store.maintain();last_cleanup=now
            for key,(process,cancel,started,last_beat) in list(running.items()):
                done=not process.is_alive();timed_out=now-started>=timeout
                requested=store.heartbeat(key,worker) if now-last_beat>=2 else False
                if now-last_beat>=2:running[key]=(process,cancel,started,now)
                if requested is None or requested or timed_out or done:
                    if requested:cancel.set()
                    stop_process(process)
                    if requested:store.finish(key,worker,'cancelled')
                    elif timed_out:store.finish(key,worker,'failed',error='Durée maximale de calcul atteinte. Réduisez la sélection ou les options détaillées.')
                    elif done:store.finish(key,worker,'failed',error='Le processus de calcul a été interrompu. Vous pouvez réessayer.')
                    del running[key]
            while len(running)<concurrency and not stop.is_set():
                key=store.claim(worker)
                if key is None:break
                cancel=context.Event();process=context.Process(target=execute,args=(key,worker,cancel),name='resonant-compute')
                try:process.start()
                except Exception:
                    store.finish(key,worker,'failed',error='Impossible de démarrer le calcul. Réessayez plus tard.');raise
                running[key]=(process,cancel,time.monotonic(),time.monotonic())
            stop.wait(.5)
    finally:
        for key,(process,cancel,*_) in running.items():
            cancel.set();stop_process(process)
            store.finish(key,worker,'failed',error='Calcul interrompu lors de l’arrêt du worker. Vous pouvez réessayer.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--concurrency',type=int,default=int(os.environ.get('RESONANT_CONCURRENCY','1')));parser.add_argument('--timeout',type=float,default=float(os.environ.get('RESONANT_JOB_TIMEOUT','600')))
    args=parser.parse_args()
    if not 1<=args.concurrency<=4 or not 1<=args.timeout<=3600:parser.error('concurrency 1–4, timeout 1–3600 s')
    logging.basicConfig(level=logging.INFO);stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    run(args.concurrency,args.timeout,stop)

if __name__=='__main__':main()
