#!/usr/bin/env python3
"""Read-only deployment diagnosis. No auth imports, schema writes or secrets printed."""
import argparse,json,sqlite3,time
from pathlib import Path
from urllib.parse import quote


def inspect_database(path,job=None):
    path=Path(path).expanduser()
    if not path.is_absolute() or not path.is_file():raise ValueError('Existing absolute database required')
    connection=sqlite3.connect('file:'+quote(str(path))+'?mode=ro',uri=True,timeout=5)
    connection.row_factory=sqlite3.Row
    try:
        tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'compute_jobs' not in tables:return {'queue_schema':False,'worker':'unknown'}
        now=time.time();seen=connection.execute('SELECT max(heartbeat) FROM compute_workers').fetchone()[0] if 'compute_workers' in tables else None
        result={'queue_schema':True,'worker_presence_supported':'compute_workers' in tables,'worker_available':seen is not None and now-seen<=30,'job_counts':dict(connection.execute('SELECT status,count(*) FROM compute_jobs GROUP BY status'))}
        if job:
            r=connection.execute('SELECT id,kind,status,created,started,finished,heartbeat,cancel FROM compute_jobs WHERE id=?',(job,)).fetchone()
            result['job']=dict(r) if r else None
        result['oldest_queue_age_seconds']=connection.execute("SELECT ?-min(created) FROM compute_jobs WHERE status='queued'",(now,)).fetchone()[0]
        return result
    finally:connection.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--job');args=parser.parse_args()
    try:print(json.dumps(inspect_database(args.db,args.job),indent=2));raise SystemExit(0)
    except (ValueError,sqlite3.Error):print('Diagnostic impossible : base absente, chemin relatif, droits ou verrouillage. Aucun contenu privé affiché.');raise SystemExit(1)
