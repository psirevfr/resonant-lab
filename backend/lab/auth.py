"""Cookie sessions and user-scoped API keys; additive SQLite migrations."""
import datetime
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import time
from functools import lru_cache
import bcrypt
from fastapi import Request, HTTPException, Depends
import jwt
from jwt import PyJWTError

ROOT=Path(__file__).resolve().parents[2]
ALGORITHM='HS256'
TOKEN_EXPIRE_HOURS=24


def database_path():
    path=Path(os.environ.get('RESONANT_DB_PATH',str(ROOT/'users.db'))).expanduser()
    if not path.is_absolute():
        raise RuntimeError('RESONANT_DB_PATH doit être absolu et identique pour le web et le worker.')
    return path.resolve()


def get_db():
    conn=sqlite3.connect(database_path(),timeout=5)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def session_secret():
    configured=os.environ.get('RESONANT_SESSION_SECRET')
    if configured:
        if len(configured)<32:raise RuntimeError('RESONANT_SESSION_SECRET doit contenir au moins 32 caractères.')
        return configured
    # Development fallback is private and persistent, never a shared default.
    path=ROOT/'.local'/'session.key';path.parent.mkdir(exist_ok=True)
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:pass
    else:
        with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(48))
    return path.read_text().strip()


def init_db():
    conn=get_db()
    try:
        # SQLite holds private account/job data, including owner-scoped API keys.
        os.chmod(database_path(),0o600)
        if os.environ.get('RESONANT_SQLITE_WAL')=='1':conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.execute('BEGIN IMMEDIATE')
        if 'api_key' not in {row['name'] for row in conn.execute('PRAGMA table_info(users)')}:
            conn.execute('ALTER TABLE users ADD COLUMN api_key TEXT')
        conn.execute('CREATE TABLE IF NOT EXISTS revoked_sessions (digest TEXT PRIMARY KEY, expires REAL NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS visitor_sessions (owner INTEGER PRIMARY KEY, expires REAL NOT NULL, claimed INTEGER NOT NULL DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS auth_rate_limits (bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL)')
        conn.execute('CREATE INDEX IF NOT EXISTS auth_limits_expiry ON auth_rate_limits(expires)')
        conn.commit()
    finally:conn.close()


def hash_password(password):
    if not 8<=len(password) or len(password.encode())>72:raise ValueError('Mot de passe : au moins 8 caractères, au plus 72 octets UTF-8.')
    return bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()


@lru_cache(maxsize=1)
def dummy_password_hash():
    # Reduce username-enumeration timing differences by performing bcrypt too.
    return hash_password(secrets.token_urlsafe(24))


def verify_password(plain_password,hashed_password):
    if not isinstance(plain_password,str) or len(plain_password.encode())>72:return False
    try:return bcrypt.checkpw(plain_password.encode(),hashed_password.encode())
    except (ValueError,TypeError):return False


def create_access_token(data):
    return jwt.encode({**data,'jti':secrets.token_urlsafe(24),'exp':datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=TOKEN_EXPIRE_HOURS)},session_secret(),algorithm=ALGORITHM)


def decode_session(token):
    if not isinstance(token,str) or len(token)>4096:return None
    try:
        payload=jwt.decode(token,session_secret(),algorithms=[ALGORITHM],options={'require':['exp','sub']})
        # bool and string dates are not issued by this application.
        if type(payload['exp']) not in (int,float):return None
        return payload
    except PyJWTError:return None


def get_current_user(request):
    token=request.cookies.get('access_token')
    if not token:return None
    payload=decode_session(token)
    if payload is None:return None
    if payload.get('purpose') is not None:return None
    if not isinstance(payload.get('sub'),str):return None
    conn=get_db()
    try:
        if conn.execute('SELECT 1 FROM revoked_sessions WHERE digest=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone():return None
        user=conn.execute('SELECT id,username,email FROM users WHERE username=?',(payload['sub'],)).fetchone()
        return dict(user) if user else None
    finally:conn.close()


def revoke_session(request):
    token=request.cookies.get('access_token')
    if not token:return
    conn=get_db()
    try:
        conn.execute('INSERT OR REPLACE INTO revoked_sessions VALUES (?,?)',(hashlib.sha256(token.encode()).hexdigest(),time.time()+TOKEN_EXPIRE_HOURS*3600))
        conn.execute('DELETE FROM revoked_sessions WHERE expires<?',(time.time(),));conn.commit()
    finally:conn.close()


def csrf_token(token):
    return hmac.new(session_secret().encode(),('csrf:'+token).encode(),hashlib.sha256).hexdigest()


def valid_csrf(value,token):
    return len(value)==64 and hmac.compare_digest(value.encode(),csrf_token(token).encode())


def check_origin(request):
    from urllib.parse import urlsplit
    origin=request.headers.get('origin')
    try:
        parsed=urlsplit(origin) if origin else None
        valid=not parsed or (parsed.scheme in ('https','http') and parsed.netloc==request.headers.get('host') and parsed.scheme==request.url.scheme and not parsed.path and not parsed.query and not parsed.fragment)
    except ValueError:valid=False
    if request.headers.get('sec-fetch-site')=='cross-site' or not valid:
        raise HTTPException(403,'Requête intersite refusée.')


def rate_limit(request,action,subject='',limit=10,window=600):
    """Atomic fixed-window quotas, shared by processes; never trust raw XFF.

    Uvicorn must trust forwarding headers only from the loopback reverse proxy.
    IPs and usernames are represented only by keyed digests, expiring in <= 1h.
    """
    identity=subject if subject else (request.client.host if request.client else 'unknown')
    bucket=hmac.new(session_secret().encode(),(action+':'+identity).encode(),hashlib.sha256).hexdigest()
    now=time.time();c=get_db()
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM auth_rate_limits WHERE expires<=?',(now,))
        row=c.execute('SELECT count,expires FROM auth_rate_limits WHERE bucket=?',(bucket,)).fetchone()
        if row is None and c.execute('SELECT count(*) FROM auth_rate_limits').fetchone()[0]>=10000:
            raise HTTPException(429,'Protection temporairement occupée. Réessayez plus tard.',headers={'Retry-After':'60'})
        if row and row['count']>=limit:
            raise HTTPException(429,'Trop de tentatives. Réessayez plus tard.',headers={'Retry-After':str(max(1,int(row['expires']-now)+1))})
        c.execute('INSERT INTO auth_rate_limits VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(bucket,now+window))
        c.commit()
    finally:c.close()


def require_user(request:Request):
    user=get_current_user(request)
    if not user:raise HTTPException(401,'Session expirée. Reconnectez-vous pour continuer.')
    return user


def require_api_user(request:Request):
    user=get_current_user(request)
    if user:
        if request.method not in ('GET','HEAD','OPTIONS'):
            check_origin(request)
            if not valid_csrf(request.headers.get('x-csrf-token',''),request.cookies['access_token']):
                raise HTTPException(403,'Session à actualiser avant cette action.')
        return user
    key=request.headers.get('x-api-key')
    if not key:
        visitor=get_visitor(request)
        if visitor:
            if request.method not in ('GET','HEAD','OPTIONS'):
                check_origin(request)
                if not valid_csrf(request.headers.get('x-csrf-token',''),request.cookies['visitor_token']):
                    raise HTTPException(403,'Session visiteur à actualiser avant cette action.')
            return visitor
        raise HTTPException(401,'Session expirée. Rechargez le laboratoire pour continuer.')
    if len(key)>256:raise HTTPException(403,'Clé API invalide.')
    conn=get_db()
    try:
        users=conn.execute('SELECT id,username,email FROM users WHERE api_key=?',(key,)).fetchall()
    finally:conn.close()
    if len(users)!=1:raise HTTPException(403,'Clé API invalide.')
    return dict(users[0])


def get_visitor(request):
    token=request.cookies.get('visitor_token')
    if not token:return None
    payload=decode_session(token)
    if payload is None:return None
    owner=payload.get('owner')
    if payload.get('purpose')!='visitor' or type(owner) is not int or owner>=0:return None
    c=get_db()
    try:row=c.execute('SELECT expires,claimed FROM visitor_sessions WHERE owner=?',(owner,)).fetchone()
    finally:c.close()
    if not row or row['claimed'] or row['expires']<=time.time():return None
    return {'id':owner,'username':'Visiteur','email':'','guest':True}


def create_visitor():
    owner=-(secrets.randbits(52)+1);expires=time.time()+86400
    c=get_db()
    try:
        c.execute('DELETE FROM visitor_sessions WHERE expires<?',(time.time(),))
        c.execute('INSERT INTO visitor_sessions(owner,expires) VALUES (?,?)',(owner,expires));c.commit()
    finally:c.close()
    return jwt.encode({'sub':'visitor','purpose':'visitor','owner':owner,'exp':expires},session_secret(),algorithm=ALGORITHM)


def claim_visitor(request,owner):
    visitor=get_visitor(request)
    if not visitor:return None
    c=get_db()
    try:
        c.execute('BEGIN IMMEDIATE')
        changed=c.execute('UPDATE visitor_sessions SET claimed=1 WHERE owner=? AND claimed=0 AND expires>?',(visitor['id'],time.time())).rowcount
        if not changed:c.rollback();return None
        tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'compute_jobs' in tables:
            collisions=c.execute('SELECT id FROM compute_jobs g WHERE g.owner=? AND EXISTS (SELECT 1 FROM compute_jobs a WHERE a.owner=? AND a.idem=g.idem)',(visitor['id'],owner)).fetchall()
            for row in collisions:
                new_key='claimed:'+secrets.token_urlsafe(32)
                while c.execute('SELECT 1 FROM compute_jobs WHERE owner=? AND idem=?',(owner,new_key)).fetchone():new_key='claimed:'+secrets.token_urlsafe(32)
                c.execute('UPDATE compute_jobs SET idem=? WHERE id=?',(new_key,row['id']))
        for table in ('compute_jobs','audio_references'):
            if table in tables:c.execute(f'UPDATE {table} SET owner=? WHERE owner=?',(owner,visitor['id']))
        c.commit()
    finally:c.close()
    return visitor['id']


def require_account(user:dict=Depends(require_api_user)):
    if user.get('guest'):raise HTTPException(401,'Connectez-vous ou créez un compte pour cette action.')
    return user
