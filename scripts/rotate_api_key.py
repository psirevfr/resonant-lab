"""Rotate a user-scoped API key into private dotenv + SQLite, never stdout/Git."""
import argparse
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tempfile


def setting(text, name):
    values=re.findall(r'^'+re.escape(name)+r'=(.*)$',text,re.M)
    if len(values)!=1:raise ValueError('Configuration manquante ou ambiguë.')
    return values[0].strip().strip('\"\'')


def replace_setting(text,name,value):
    line=name+'='+value
    if re.search(r'^'+re.escape(name)+r'=',text,re.M):
        return re.sub(r'^'+re.escape(name)+r'=.*$',lambda _:line,text,flags=re.M)
    return text.rstrip()+'\n'+line+'\n'


def private_write(path,text):
    fd,temp=tempfile.mkstemp(prefix='.resonant-env-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            os.fchmod(f.fileno(),0o600);f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        Path(temp).unlink(missing_ok=True)


def rotate(env_file,username):
    path=Path(env_file)
    if path.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Le fichier de secrets doit être hors du dépôt.')
    if path.is_symlink() or not path.is_file():raise ValueError('Fichier privé existant requis, sans lien symbolique.')
    old=path.read_text()
    db=Path(setting(old,'RESONANT_DB_PATH'))
    if not db.is_absolute() or not db.is_file():raise ValueError('Base existante et chemin absolu requis.')
    key='res_live_'+secrets.token_hex(32)
    new=replace_setting(old,'RESONANT_LAB_API_KEY',key)
    session=setting(old,'RESONANT_SESSION_SECRET')
    if not session or session.startswith('REPLACE_WITH_'):
        new=replace_setting(new,'RESONANT_SESSION_SECRET',secrets.token_urlsafe(48))
    elif len(session)<32:raise ValueError('Secret de session existant trop court ; corriger la configuration.')
    # Never create a new users database or an account accidentally.
    with sqlite3.connect(db.as_uri()+'?mode=rw',uri=True,timeout=5) as conn:
        conn.execute('BEGIN IMMEDIATE')
        rows=conn.execute('SELECT id FROM users WHERE username=?',(username,)).fetchall()
        if len(rows)!=1:raise ValueError('Pseudo applicatif absent ou ambigu.')
        conn.execute('UPDATE users SET api_key=? WHERE id=?',(key,rows[0][0]))
        private_write(path,new)
        try:conn.commit()
        except BaseException:
            private_write(path,old)
            raise
    # Filesystem + SQLite are not a shared crash-atomic transaction. See deployment doc.


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--env-file',default='/etc/resonant-lab.env')
    parser.add_argument('--username',required=True,help='Pseudo du compte Resonant, distinct du compte Linux.')
    args=parser.parse_args()
    try:rotate(args.env_file,args.username)
    except Exception:
        parser.exit(1,'Rotation non terminée. Vérifier la base, le pseudo, les permissions et la configuration ; aucun secret affiché.\n')
    print('Clé renouvelée dans le fichier privé et pour ce compte SQLite. Aucun secret affiché.')
