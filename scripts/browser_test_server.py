#!/usr/bin/env python3
"""LOCAL synthetic test server only. Never run this authentication override in production."""
import importlib,os,tempfile
from pathlib import Path
os.environ['RESONANT_DB_PATH']=str(Path(tempfile.mkdtemp(prefix='resonant-browser-'))/'test.sqlite')
os.environ['RESONANT_SESSION_SECRET']='local-test-only-session-secret-64-character-value'
from lab.auth import init_db,require_user,require_api_user
from lab.job_store import init_jobs
init_db();init_jobs()
m=importlib.import_module('lab.app');user={'id':1,'username':'local-test','email':'test@example.invalid'}
m.app.dependency_overrides[require_user]=lambda:user
m.app.dependency_overrides[require_api_user]=lambda:user
m.get_current_user=lambda request:user
if __name__=='__main__':
    import uvicorn
    uvicorn.run(m.app,host='127.0.0.1',port=8011,log_level='warning')
