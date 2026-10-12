#!/usr/bin/env python3
"""Temporary LOCAL server with real visitor/account authentication, never production."""
import importlib
import os
from pathlib import Path
import secrets
import tempfile

os.environ['RESONANT_DB_PATH']=str(Path(tempfile.mkdtemp(prefix='resonant-visitors-'))/'test.sqlite')
os.environ['RESONANT_SESSION_SECRET']=secrets.token_urlsafe(48)
from lab.auth import init_db,get_db,hash_password
from lab.job_store import init_jobs
init_db();init_jobs()
c=get_db()
try:
    c.execute('INSERT INTO users(username,email,hashed_password) VALUES (?,?,?)',('export-test','export@example.invalid',hash_password('local-test-only-password')));c.commit()
finally:c.close()

if __name__=='__main__':
    import uvicorn
    uvicorn.run(importlib.import_module('lab.app').app,host='127.0.0.1',port=8011,log_level='warning')
