import re
import time
from fastapi.testclient import TestClient
from lab.app import app,recordings
from lab.auth import get_db
from test_auth import user as create_user


def visitor():
    app.dependency_overrides.clear()
    client=TestClient(app,base_url='https://testserver')
    response=client.get('/mon-lab/')
    assert response.status_code==200
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    identity=client.get('/api/me').json()
    assert identity['guest'] and identity['id']<0 and identity['email']==''
    return client,identity,{'X-CSRF-Token':identity['csrf_token']}


def test_visitors_can_use_lab_but_sessions_are_private_and_csrf_protected():
    first,_,headers=visitor()
    assert first.post('/api/demo').status_code==403
    assert first.post('/api/demo',headers={**headers,'Origin':'https://evil.invalid'}).status_code==403
    audio=first.post('/api/demo',headers=headers).json()['id']
    assert first.get(f'/api/audio/{audio}/segment?duration=.05').status_code==200
    second,_,_=visitor()
    assert second.get(f'/api/audio/{audio}/segment?duration=.05').status_code==404
    request={'audio_id':audio,'duration':.05,'max_partials':1,'refine_modes':False,'detailed':False,'include_impact':False}
    assert first.post('/api/compute/input',json={'kind':'generate','request':request},headers=headers).status_code==200
    job=first.post('/api/generate',json=request,headers={**headers,'Idempotency-Key':'guest-generation'})
    assert job.status_code==202
    assert first.get(job.json()['status_url']).status_code==200
    assert second.get(job.json()['status_url']).status_code==404
    assert second.get(job.json()['result_url']).status_code==404


def test_export_endpoints_require_a_real_account():
    client,_,headers=visitor()
    patch={'nodes':[{'id':'out','type':'output'}]}
    for path in ('/api/export/svg','/api/export/csv'):
        assert client.post(path,json=patch,headers=headers).status_code==401
    assert client.post('/api/exports',files={'file':('model.json',b'{}','application/json')},headers=headers).status_code==401
    assert client.get('/api/exports/anything').status_code==401
    assert client.post('/api/account',json={'email':'test@example.invalid','current_password':'test password'},headers=headers).status_code==401
    assert client.post('/api/render',json={'patch':patch},headers=headers).status_code==401


def test_login_claims_references_and_jobs_and_revokes_old_visitor_cookie():
    client,identity,headers=visitor();old_token=client.cookies.get('visitor_token')
    audio=client.post('/api/demo',headers=headers).json()['id']
    request={'audio_id':audio,'duration':.05,'max_partials':1}
    response=client.post('/api/generate',json=request,headers={**headers,'Idempotency-Key':'guest-job'})
    assert response.status_code==202
    create_user('registered')
    page=client.get('/login');csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
    assert client.post('/login',data={'username':'registered','password':'test password','csrf':csrf},follow_redirects=False).status_code==303
    account=client.get('/api/me').json()
    assert account['id']>0 and not account.get('guest')
    assert client.get(response.json()['status_url']).status_code==200
    recordings.clear()
    assert client.get(f'/api/audio/{audio}/segment?duration=.05').status_code==200
    assert client.get(f'/api/audio/{audio}/wav').status_code==200
    assert client.post('/api/exports',files={'file':('model.json',b'{}','application/json')},headers={'X-CSRF-Token':account['csrf_token']}).status_code==200
    stolen=TestClient(app,base_url='https://testserver');stolen.cookies.set('visitor_token',old_token)
    assert stolen.get('/api/me').status_code==401
    c=get_db()
    try:
        assert c.execute('SELECT claimed FROM visitor_sessions WHERE owner=?',(identity['id'],)).fetchone()[0]==1
        assert c.execute('SELECT owner FROM audio_references WHERE id=?',(audio,)).fetchone()[0]==account['id']
    finally:c.close()


def test_visitor_token_cannot_be_reused_as_account_token():
    client,_,headers=visitor();create_user('visitor')
    client.cookies.set('access_token',client.cookies.get('visitor_token'))
    assert client.get('/api/me').json()['guest']
    assert client.post('/api/exports',files={'file':('model.json',b'{}')},headers=headers).status_code==401


def test_expired_visitor_receives_new_isolated_session():
    client,identity,_=visitor()
    c=get_db()
    try:c.execute('UPDATE visitor_sessions SET expires=? WHERE owner=?',(time.time()-1,identity['id']));c.commit()
    finally:c.close()
    assert client.get('/api/me').status_code==401
    assert client.get('/mon-lab/').status_code==200
    assert client.get('/api/me').json()['id']!=identity['id']


def test_guest_queue_has_shared_limit_without_blocking_registered_capacity():
    first,_,headers=visitor();audio=first.post('/api/demo',headers=headers).json()['id']
    request={'audio_id':audio,'duration':.05,'max_partials':1}
    for index in range(2):assert first.post('/api/generate',json=request,headers={**headers,'Idempotency-Key':f'queued-{index}'}).status_code==202
    second,_,other_headers=visitor();other_audio=second.post('/api/demo',headers=other_headers).json()['id']
    assert second.post('/api/generate',json={**request,'audio_id':other_audio},headers={**other_headers,'Idempotency-Key':'third'}).status_code==429
    create_user('registered')
    account_headers={'X-API-Key':'registered-test-key','Idempotency-Key':'account-job'}
    client=TestClient(app,base_url='https://testserver')
    account_audio=client.post('/api/demo',headers=account_headers).json()['id']
    assert client.post('/api/generate',json={**request,'audio_id':account_audio},headers=account_headers).status_code==202


def test_large_json_is_rejected_before_decoding():
    client,_,headers=visitor()
    assert client.post('/api/generate',content=b'x'*2_100_001,headers={**headers,'Content-Type':'application/json'}).status_code==413


def test_chunked_large_json_is_also_bounded():
    client,_,headers=visitor()
    def chunks():
        for _ in range(4):yield b'x'*600_000
    assert client.post('/api/generate',content=chunks(),headers={**headers,'Content-Type':'application/json'}).status_code==413


def test_embedded_authentication_is_same_origin_and_returns_completion_page():
    client,_,_=visitor();create_user('embedded')
    page=client.get('/login?embed=1')
    assert page.headers['x-frame-options']=='SAMEORIGIN'
    assert "frame-ancestors 'self'" in page.headers['content-security-policy']
    assert 'action="/login?embed=1"' in page.text and 'auth-embedded' in page.text
    csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
    response=client.post('/login?embed=1',data={'username':'embedded','password':'test password','csrf':csrf},follow_redirects=False)
    assert response.headers['location']=='/auth/complete'
    assert 'Connexion réussie' in client.get('/auth/complete').text


def test_claim_does_not_fail_when_account_and_visitor_used_same_idempotency_key():
    client,_,headers=visitor();create_user('collision')
    guest_audio=client.post('/api/demo',headers=headers).json()['id']
    request={'audio_id':guest_audio,'duration':.05,'max_partials':1}
    guest_job=client.post('/api/generate',json=request,headers={**headers,'Idempotency-Key':'same-key'}).json()['id']
    account=TestClient(app,base_url='https://testserver')
    key_headers={'X-API-Key':'collision-test-key','Idempotency-Key':'same-key'}
    account_audio=account.post('/api/demo',headers=key_headers).json()['id']
    assert account.post('/api/generate',json={**request,'audio_id':account_audio},headers=key_headers).status_code==202
    page=client.get('/login?embed=1');csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
    assert client.post('/login?embed=1',data={'username':'collision','password':'test password','csrf':csrf},follow_redirects=False).status_code==303
    assert len(client.get('/api/jobs').json())==2
    assert client.get('/api/jobs/'+guest_job).status_code==200
