import re
from fastapi.testclient import TestClient
from lab.app import app
from lab.auth import get_db,hash_password,create_access_token


def user(username='alice'):
    c=get_db()
    try:
        c.execute('INSERT INTO users(username,email,hashed_password,api_key) VALUES (?,?,?,?)',(username,username+'@example.invalid',hash_password('test password'),username+'-test-key'));c.commit()
    finally:c.close()


def session():
    app.dependency_overrides.clear();user();c=TestClient(app,base_url='https://testserver')
    page=c.get('/login');csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
    r=c.post('/login',data={'username':'alice','password':'test password','csrf':csrf},follow_redirects=False)
    assert r.status_code==303 and r.headers['location']=='/mon-lab/'
    token=c.get('/api/me').json()['csrf_token']
    return c,token


def test_existing_user_login_csrf_logout_invalidates_copied_cookie():
    c,csrf=session();copied=c.cookies.get('access_token')
    assert c.post('/api/demo').status_code==403
    assert c.post('/api/demo',headers={'X-CSRF-Token':csrf,'Origin':'https://evil.invalid'}).status_code==403
    assert c.post('/api/demo',headers={'X-CSRF-Token':csrf}).status_code==200
    assert c.post('/api/logout',json={},headers={'X-CSRF-Token':csrf}).status_code==200
    c.cookies.set('access_token',copied)
    assert c.get('/api/me').status_code==401
    assert c.get('/mon-lab/').status_code==200
    assert c.get('/api/me').json()['guest']


def test_api_key_is_user_scoped_and_not_a_browser_session():
    app.dependency_overrides.clear();user()
    c=TestClient(app,base_url='https://testserver')
    assert c.get('/api/me',headers={'X-API-Key':'alice-test-key'}).json()['username']=='alice'
    assert c.get('/api/me',headers={'X-API-Key':'bad'}).status_code==403
    assert c.get('/mon-lab/',headers={'X-API-Key':'alice-test-key'}).status_code==200
    assert c.get('/api/me').json()['guest']
    assert 'alice-test-key' not in c.get('/api/me',headers={'X-API-Key':'alice-test-key'}).text


def test_email_update_requires_password_and_session_protection():
    c,csrf=session();headers={'X-CSRF-Token':csrf}
    assert c.post('/api/account',json={'email':'new@example.invalid','current_password':'wrong'},headers=headers).status_code==403
    assert c.post('/api/account',json={'email':'bad','current_password':'test password'},headers=headers).status_code==422
    assert c.post('/api/account',json={'email':'new@example.invalid','current_password':'test password'},headers=headers).status_code==200
    assert c.get('/api/me').json()['email']=='new@example.invalid'


def test_login_error_accessible_no_password_echo_and_no_open_redirect():
    app.dependency_overrides.clear();c=TestClient(app,base_url='https://testserver')
    page=c.get('/login?next=https://evil.invalid');csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
    r=c.post('/login',data={'username':'missing','password':'never-echo-this','csrf':csrf})
    assert r.status_code==400 and 'role="alert"' in r.text and 'aria-invalid="true"' in r.text
    assert 'never-echo-this' not in r.text
    assert c.post('/login',data={'username':'missing','password':'any','csrf':'bad'}).status_code==403
