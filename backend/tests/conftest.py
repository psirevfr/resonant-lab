import pytest
from lab.app import app,recordings,renders,downloads
from lab.auth import require_user,require_api_user,init_db
from lab.job_store import init_jobs

@pytest.fixture(autouse=True)
def authenticated_lab(monkeypatch,tmp_path):
    monkeypatch.setenv('RESONANT_DB_PATH',str(tmp_path/'test.sqlite'))
    monkeypatch.setenv('RESONANT_SESSION_SECRET','test-session-signing-secret-not-for-production')
    init_db();init_jobs()
    user=lambda: {'id':1,'username':'test','email':'test@example.invalid'}
    app.dependency_overrides[require_user]=user
    app.dependency_overrides[require_api_user]=user
    recordings.clear();renders.clear();downloads.clear()
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def complete_job():
    def complete(response):
        from lab import job_store as s
        from lab.worker import compute
        from threading import Event
        assert response.status_code==202,response.text
        key=s.claim('test-worker');assert key==response.json()['id']
        kind,payload,x=s.load(key,'test-worker')
        result=compute(kind,payload,x,lambda _:None,Event())
        s.finish(key,'test-worker','succeeded',result)
        return result
    return complete
