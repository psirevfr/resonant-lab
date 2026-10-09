"""Cookie sessions and user-scoped API keys; additive SQLite migrations."""
import datetime
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import time
import bcrypt
from fastapi import Request, HTTPException
from jose import jwt, JWTError

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
        if os.environ.get('RESONANT_SQLITE_WAL')=='1':conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.execute('BEGIN IMMEDIATE')
        if 'api_key' not in {row['name'] for row in conn.execute('PRAGMA table_info(users)')}:
            conn.execute('ALTER TABLE users ADD COLUMN api_key TEXT')
        conn.execute('CREATE TABLE IF NOT EXISTS revoked_sessions (digest TEXT PRIMARY KEY, expires REAL NOT NULL)')
        conn.commit()
    finally:conn.close()


def hash_password(password):
    if not 8<=len(password) or len(password.encode())>72:raise ValueError('Mot de passe : au moins 8 caractères, au plus 72 octets UTF-8.')
    return bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()


def verify_password(plain_password,hashed_password):
    try:return bcrypt.checkpw(plain_password.encode(),hashed_password.encode())
    except (ValueError,TypeError):return False


def create_access_token(data):
    return jwt.encode({**data,'jti':secrets.token_urlsafe(24),'exp':datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=TOKEN_EXPIRE_HOURS)},session_secret(),algorithm=ALGORITHM)


def get_current_user(request):
    token=request.cookies.get('access_token')
    if not token:return None
    try:payload=jwt.decode(token,session_secret(),algorithms=[ALGORITHM])
    except JWTError:return None
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


def check_origin(request):
    from urllib.parse import urlsplit
    origin=request.headers.get('origin')
    if request.headers.get('sec-fetch-site')=='cross-site' or (origin and urlsplit(origin).netloc!=request.headers.get('host')):
        raise HTTPException(403,'Requête intersite refusée.')


def require_user(request:Request):
    user=get_current_user(request)
    if not user:raise HTTPException(401,'Session expirée. Reconnectez-vous pour continuer.')
    return user


def require_api_user(request:Request):
    user=get_current_user(request)
    if user:
        if request.method not in ('GET','HEAD','OPTIONS'):
            check_origin(request)
            if not hmac.compare_digest(request.headers.get('x-csrf-token',''),csrf_token(request.cookies['access_token'])):
                raise HTTPException(403,'Session à actualiser avant cette action.')
        return user
    key=request.headers.get('x-api-key')
    if not key:raise HTTPException(401,'Session expirée. Reconnectez-vous pour continuer.')
    conn=get_db()
    try:
        users=conn.execute('SELECT id,username,email FROM users WHERE api_key=?',(key,)).fetchall()
    finally:conn.close()
    if len(users)!=1:raise HTTPException(403,'Clé API invalide.')
    return dict(users[0])
