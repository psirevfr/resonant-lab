"""Private, bounded temporary WAV references; SQLite contains metadata only."""
import os
import shutil
import time
from uuid import uuid4
from fastapi import HTTPException
from .auth import get_db,database_path


def directory():
    path=database_path().parent/'.resonant-audio'
    path.mkdir(mode=0o700,exist_ok=True)
    if path.is_symlink():raise RuntimeError('Audio storage must not be a symlink')
    return path


def connection():
    c=get_db()
    c.execute('CREATE TABLE IF NOT EXISTS audio_references (id TEXT PRIMARY KEY, owner INTEGER NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL, created REAL NOT NULL)')
    c.commit()
    return c


def cleanup():
    cutoff=time.time()-int(os.environ.get('RESONANT_AUDIO_TTL_SECONDS','604800'))
    visitor_cutoff=time.time()-86400
    c=connection()
    try:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT id FROM audio_references WHERE created<? OR (owner<0 AND created<?)',(cutoff,visitor_cutoff)).fetchall()
        c.execute('DELETE FROM audio_references WHERE created<? OR (owner<0 AND created<?)',(cutoff,visitor_cutoff));c.commit()
    finally:c.close()
    root=directory()
    for row in old:
        key=row['id']
        if len(key)==32 and all(x in '0123456789abcdef' for x in key):
            (root/(key+'.wav')).unlink(missing_ok=True)
    # Uncommitted files after a crash are discarded after one hour.
    c=connection()
    try:known={row['id']+'.wav' for row in c.execute('SELECT id FROM audio_references')}
    finally:c.close()
    for path in root.glob('*.wav'):
        if path.name not in known and path.stat().st_mtime<time.time()-3600:path.unlink(missing_ok=True)


def save(record,owner):
    cleanup();key=uuid4().hex;path=directory()/(key+'.wav')
    size=len(record.original)
    if shutil.disk_usage(path.parent).free-size<int(os.environ.get('RESONANT_AUDIO_MIN_FREE_BYTES','134217728')):
        raise HTTPException(507,'Espace disque insuffisant pour conserver la référence audio.')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as output:output.write(record.original)
        c=connection()
        try:
            c.execute('BEGIN IMMEDIATE')
            total=c.execute('SELECT coalesce(sum(size),0) FROM audio_references').fetchone()[0]
            personal=c.execute('SELECT coalesce(sum(size),0) FROM audio_references WHERE owner=?',(owner,)).fetchone()[0]
            if total+size>int(os.environ.get('RESONANT_AUDIO_MAX_BYTES','536870912')) or personal+size>int(os.environ.get('RESONANT_AUDIO_USER_MAX_BYTES','268435456')):
                raise HTTPException(507,'Stockage audio temporaire plein. Réessayez après expiration des anciennes références.')
            c.execute('INSERT INTO audio_references VALUES (?,?,?,?,?)',(key,owner,record.name,size,time.time()));c.commit()
        finally:c.close()
    except BaseException:
        path.unlink(missing_ok=True);raise
    return key


def load(key,owner):
    # Validate before constructing a filesystem path, including database contents.
    if len(key)!=32 or any(x not in '0123456789abcdef' for x in key):return None
    c=connection()
    try:row=c.execute('SELECT name,size,created FROM audio_references WHERE id=? AND owner=?',(key,owner)).fetchone()
    finally:c.close()
    if row is None or row['created']<time.time()-int(os.environ.get('RESONANT_AUDIO_TTL_SECONDS','604800')):return None
    path=directory()/(key+'.wav')
    if path.is_symlink() or not path.is_file():return None
    try:data=path.read_bytes()
    except FileNotFoundError:return None
    if len(data)!=row['size']:return None
    from .audio import read_wav
    return read_wav(data,row['name'])
