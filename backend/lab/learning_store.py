"""Shared, bounded statistics for choosing an optional local synthesis trial."""
from contextlib import closing
import hmac
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .auth import create_access_token, decode_session, get_db, session_secret

RETENTION = 60*86400
MAX_ROWS = 10_000
PER_OWNER = 24
MIN_CONTRIBUTORS = 5


class LearningReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticket: str = Field(min_length=1, max_length=550)
    profile: Literal['transient','decaying','sustained']
    strategy: Literal['adsr','decay']
    reward: float = Field(ge=0, le=1, allow_inf_nan=False)


def init_learning(db):
    db.execute('''CREATE TABLE IF NOT EXISTS acoustic_trials (
        owner INTEGER NOT NULL, excerpt TEXT NOT NULL,
        profile TEXT NOT NULL, strategy TEXT NOT NULL,
        reward INTEGER NOT NULL, received INTEGER NOT NULL,
        PRIMARY KEY (owner, excerpt, strategy))''')
    db.execute('CREATE INDEX IF NOT EXISTS acoustic_trials_recent ON acoustic_trials(received, owner)')


def make_ticket(owner, samples, fs):
    # Scoped to this owner and distinct from the public analysis cache digest.
    secret=session_secret().encode()
    scope=hmac.digest(secret, f'acoustic-learning-v1:{owner}:{fs}'.encode(), 'sha256')
    identifier=hmac.digest(scope, samples, 'sha256').hex()
    return create_access_token({'sub':str(owner),'purpose':'acoustic-learning-v1','excerpt':identifier})


def accept(owner, report):
    payload=decode_session(report.ticket)
    if not payload or payload.get('purpose')!='acoustic-learning-v1' or payload.get('sub')!=str(owner):
        raise HTTPException(403, 'Contribution expirée ou indisponible.')
    now=int(time.time())
    with closing(get_db()) as db, db:
        cursor=db.execute('INSERT OR IGNORE INTO acoustic_trials VALUES (?,?,?,?,?,?)',
                          (owner,payload['excerpt'],report.profile,report.strategy,round(1000*report.reward),now))
        db.execute('DELETE FROM acoustic_trials WHERE received < ?', (now-RETENTION,))
        db.execute('''DELETE FROM acoustic_trials WHERE rowid IN
                    (SELECT rowid FROM acoustic_trials WHERE owner=? ORDER BY received DESC,rowid DESC LIMIT -1 OFFSET ?)''',
                   (owner,PER_OWNER))
        db.execute('''DELETE FROM acoustic_trials WHERE rowid IN
                    (SELECT rowid FROM acoustic_trials ORDER BY received DESC,rowid DESC LIMIT -1 OFFSET ?)''',
                   (MAX_ROWS,))
        return bool(cursor.rowcount)


def summary():
    # Normalize each owner's trials as one voice. Small rounds remain private
    # and inactive. Clients use this only as a low-weight experimental prior.
    with closing(get_db()) as db:
        rows=db.execute('''SELECT profile,strategy,COUNT(*) AS owners,AVG(mean) AS reward
            FROM (SELECT profile,strategy,owner,AVG(reward) AS mean
                  FROM acoustic_trials WHERE received >= ? GROUP BY profile,strategy,owner)
            GROUP BY profile,strategy HAVING COUNT(*) >= ?''',
                        (int(time.time())-RETENTION,MIN_CONTRIBUTORS)).fetchall()
    out={}
    for row in rows:
        out.setdefault(row['profile'],{})[row['strategy']]={
            'contributors':row['owners'],'mean':round(row['reward']/1000,3)}
    return out


def reset(owner):
    with closing(get_db()) as db, db:
        db.execute('DELETE FROM acoustic_trials WHERE owner=?',(owner,))
