"""Shared, bounded statistics for choosing an optional local synthesis trial."""
from contextlib import closing
import hmac
import secrets
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .auth import create_access_token, decode_session, get_db, session_secret

RETENTION = 60*86400
MAX_ROWS = 10_000
PER_OWNER = 24
MIN_CONTRIBUTORS = 5
CONSENT_VERSION = 1
TICKET_PURPOSE = 'acoustic-contribution-v2'


class LearningChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(strict=True, ge=CONSENT_VERSION, le=CONSENT_VERSION)
    decision: Literal['accepted', 'refused']


class LearningReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticket: str = Field(min_length=1, max_length=550)
    profile: Literal['transient','decaying','sustained']
    strategy: Literal['adsr','decay']
    reward: float = Field(gt=0, le=1, allow_inf_nan=False, strict=True)


def init_learning(db):
    db.execute('''CREATE TABLE IF NOT EXISTS acoustic_trials (
        owner INTEGER NOT NULL, excerpt TEXT NOT NULL,
        profile TEXT NOT NULL, strategy TEXT NOT NULL,
        reward INTEGER NOT NULL, received INTEGER NOT NULL,
        PRIMARY KEY (owner, excerpt, strategy))''')
    db.execute('CREATE INDEX IF NOT EXISTS acoustic_trials_recent ON acoustic_trials(received, owner)')
    db.execute('''CREATE TABLE IF NOT EXISTS acoustic_consent (
        owner INTEGER PRIMARY KEY, version INTEGER NOT NULL,
        decision TEXT NOT NULL CHECK(decision IN ('accepted', 'refused')),
        revision TEXT NOT NULL, updated INTEGER NOT NULL)''')


def _consent(db, owner):
    return db.execute('SELECT decision,revision FROM acoustic_consent WHERE owner=? AND version=?',
                      (owner, CONSENT_VERSION)).fetchone()


def consent(owner):
    with closing(get_db()) as db:
        row = _consent(db, owner)
    return {'version': CONSENT_VERSION, 'decision': row['decision'] if row else None}


def set_consent(owner, decision):
    now = int(time.time())
    with closing(get_db()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = _consent(db, owner)
        if not row or row['decision'] != decision:
            db.execute('INSERT OR REPLACE INTO acoustic_consent VALUES (?,?,?,?,?)',
                       (owner, CONSENT_VERSION, decision, secrets.token_urlsafe(18), now))
            # Previous receipts are invalidated and legacy rows never become active
            # simply by accepting new terms.
            db.execute('DELETE FROM acoustic_trials WHERE owner=?', (owner,))
        db.execute('DELETE FROM acoustic_trials WHERE received < ?', (now-RETENTION,))
        db.execute('''DELETE FROM acoustic_consent WHERE owner < 0 AND updated < ?
                      AND NOT EXISTS (SELECT 1 FROM acoustic_trials WHERE owner=acoustic_consent.owner)''',
                   (now-RETENTION,))
    return {'version': CONSENT_VERSION, 'decision': decision}


def make_ticket(owner, samples, fs):
    with closing(get_db()) as db:
        row = _consent(db, owner)
    if not row or row['decision'] != 'accepted':
        return None
    # Scoped to this owner and distinct from the public analysis cache digest.
    secret=session_secret().encode()
    scope=hmac.digest(secret, f'acoustic-learning-v1:{owner}:{fs}'.encode(), 'sha256')
    identifier=hmac.digest(scope, samples, 'sha256').hex()
    return create_access_token({'sub':str(owner), 'purpose':TICKET_PURPOSE,
                                'excerpt':identifier, 'revision':row['revision']})


def accept(owner, report):
    payload=decode_session(report.ticket)
    if not payload or payload.get('purpose')!=TICKET_PURPOSE or payload.get('sub')!=str(owner):
        raise HTTPException(403, 'Contribution expirée ou indisponible.')
    now=int(time.time())
    with closing(get_db()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = _consent(db, owner)
        if not row or row['decision'] != 'accepted' or payload.get('revision') != row['revision']:
            raise HTTPException(403, 'Contribution expirée ou indisponible.')
        cursor=db.execute('INSERT OR IGNORE INTO acoustic_trials VALUES (?,?,?,?,?,?)',
                          (owner,payload['excerpt'],report.profile,report.strategy,max(1,round(1000*report.reward)),now))
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
            FROM (SELECT t.profile,t.strategy,t.owner,AVG(t.reward) AS mean
                  FROM acoustic_trials t JOIN acoustic_consent c ON c.owner=t.owner
                  WHERE t.received >= ? AND t.reward>0 AND c.version=? AND c.decision='accepted'
                  GROUP BY t.profile,t.strategy,t.owner)
            GROUP BY profile,strategy HAVING COUNT(*) >= ?''',
                        (int(time.time())-RETENTION,CONSENT_VERSION,MIN_CONTRIBUTORS)).fetchall()
    out={}
    for row in rows:
        out.setdefault(row['profile'],{})[row['strategy']]={
            'contributors':row['owners'],'mean':round(row['reward']/1000,3)}
    return out


def reset(owner):
    with closing(get_db()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM acoustic_trials WHERE owner=?',(owner,))
        db.execute('UPDATE acoustic_consent SET revision=? WHERE owner=?',
                   (secrets.token_urlsafe(18), owner))
