"""Regression tests using only temporary databases and synthetic data."""
import base64
import hashlib
import hmac
import json
import re
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
import jwt
from lab.app import app
from lab.auth import get_db,rate_limit,session_secret
from lab.media import wav_response
from test_auth import user,session


def form(client):
    page=client.get('/login')
    return re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)


def test_login_quota_survives_cookie_changes_and_never_checks_password_after_limit(monkeypatch):
    app.dependency_overrides.clear()
    client=TestClient(app,base_url='https://testserver')
    # Cheap password checker; this test is about admission, not bcrypt speed.
    calls=[]
    monkeypatch.setattr('lab.app.verify_password',lambda *args:calls.append(1) or False)
    monkeypatch.setattr('lab.auth.dummy_password_hash',lambda:'synthetic-dummy-hash')
    for _ in range(10):
        assert client.post('/login',data={'username':'missing','password':'incorrect','csrf':form(client)}).status_code==400
    limited=client.post('/login',data={'username':'missing','password':'incorrect','csrf':form(client)})
    assert limited.status_code==429 and int(limited.headers['retry-after'])>0
    assert limited.headers['cache-control']=='no-store' and len(calls)==10
    # New session and forged proxy header do not reset the shared quota.
    other=TestClient(app,base_url='https://testserver')
    assert other.post('/login',data={'username':'missing','password':'incorrect','csrf':form(other)},headers={'X-Forwarded-For':'192.0.2.10'}).status_code==429
    c=get_db()
    try:
        rows=c.execute('SELECT bucket FROM auth_rate_limits').fetchall()
        assert rows and all(re.fullmatch('[a-f0-9]{64}',r['bucket']) for r in rows)
    finally:c.close()


def test_rate_limit_is_atomic_and_expired_quota_recovers(monkeypatch):
    request=Request({'type':'http','client':('192.0.2.3',123),'headers':[]})
    def attempt(_):
        try:rate_limit(request,'parallel',limit=3);return True
        except HTTPException as e:assert e.status_code==429;return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt,range(12)))==3
    c=get_db()
    try:c.execute('UPDATE auth_rate_limits SET expires=0');c.commit()
    finally:c.close()
    assert attempt(0)


def test_registration_is_limited_without_creating_accounts():
    app.dependency_overrides.clear();client=TestClient(app,base_url='https://testserver')
    for _ in range(5):
        assert client.post('/register',data={'username':'x','email':'invalid','password':'unused','csrf':form(client)}).status_code==422
    assert client.post('/register',data={'username':'x','email':'invalid','password':'unused','csrf':form(client)}).status_code==429
    c=get_db()
    try:assert c.execute('SELECT count(*) FROM users').fetchone()[0]==0
    finally:c.close()


def test_guest_creation_is_bounded_but_existing_session_is_usable():
    app.dependency_overrides.clear();client=TestClient(app,base_url='https://testserver')
    assert client.get('/mon-lab/').status_code==200
    c=get_db()
    try:c.execute('UPDATE auth_rate_limits SET count=40');c.commit()
    finally:c.close()
    assert client.get('/mon-lab/').status_code==200
    other=TestClient(app,base_url='https://testserver')
    assert other.get('/mon-lab/').status_code==429


def test_jose_compatible_hs256_session_survives_library_change():
    app.dependency_overrides.clear();user()
    # Same standard compact-JWS format as the previous python-jose issuer.
    def encoded(data):return base64.urlsafe_b64encode(json.dumps(data,separators=(',',':')).encode()).rstrip(b'=')
    unsigned=encoded({'alg':'HS256','typ':'JWT'})+b'.'+encoded({'sub':'alice','exp':4102444800,'jti':'legacy-synthetic'})
    signature=base64.urlsafe_b64encode(hmac.new(session_secret().encode(),unsigned,hashlib.sha256).digest()).rstrip(b'=')
    client=TestClient(app,base_url='https://testserver');client.cookies.set('access_token',(unsigned+b'.'+signature).decode())
    assert client.get('/api/me').json()['username']=='alice'


@pytest.mark.parametrize('token',[
    'not-a-jwt','x'*4097,
    jwt.encode({'sub':'alice','exp':4102444800},key='',algorithm='none'),
    jwt.encode({'sub':'alice','exp':4102444800},key='wrong-test-secret-with-enough-length',algorithm='HS256'),
])
def test_invalid_tokens_never_authenticate(token):
    app.dependency_overrides.clear();user();client=TestClient(app,base_url='https://testserver')
    client.cookies.set('access_token',token)
    assert client.get('/api/me').status_code==401


def test_signed_token_without_expiry_is_rejected():
    app.dependency_overrides.clear();user();client=TestClient(app,base_url='https://testserver')
    client.cookies.set('access_token',jwt.encode({'sub':'alice'},session_secret(),algorithm='HS256'))
    assert client.get('/api/me').status_code==401


@pytest.mark.parametrize('origin',['http://testserver','null','https://[broken','https://testserver/path','https://testserver?query'])
def test_malformed_and_downgraded_origin_fail_closed(origin):
    client,csrf=session()
    response=client.post('/api/demo',headers={'X-CSRF-Token':csrf,'Origin':origin})
    assert response.status_code==403


def test_validation_errors_do_not_echo_password_or_nonfinite_input():
    client=TestClient(app)
    response=client.post('/api/account',json={'email':{'private':'private-test-value'},'current_password':{'secret':'private-test-value'}})
    assert response.status_code==422 and 'private-test-value' not in response.text and 'input' not in response.text
    response=client.post('/api/analyze',content='{"audio_id":"synthetic","start":NaN}',headers={'Content-Type':'application/json'})
    assert response.status_code==422 and 'NaN' not in response.text


def test_browser_headers_cover_html_errors_assets_and_https_only_hsts():
    client=TestClient(app,base_url='https://testserver')
    for path in ['/login','/mon-lab/','/auth.js','/does-not-exist']:
        response=client.get(path)
        assert response.headers['x-content-type-options']=='nosniff'
        assert response.headers['referrer-policy']=='same-origin'
        assert "object-src 'none'" in response.headers['content-security-policy']
        assert 'includeSubDomains' not in response.headers['strict-transport-security']
    assert 'strict-transport-security' not in TestClient(app).get('/login').headers


def test_oversized_byte_range_never_raises_or_allocates_a_large_integer():
    response=wav_response(b'RIFF-synthetic','bytes='+'9'*5000+'-')
    assert response.status_code==200 and response.body==b'RIFF-synthetic'


def test_nonascii_csrf_is_rejected_without_a_server_error():
    app.dependency_overrides.clear();client=TestClient(app,base_url='https://testserver')
    form(client)
    assert client.post('/login',data={'username':'unused','password':'unused','csrf':'é'*64}).status_code==403


def test_early_request_rejection_keeps_browser_protections():
    response=TestClient(app,base_url='https://testserver').post('/login',content=b'x'*2_100_001)
    assert response.status_code==413
    assert response.headers['x-content-type-options']=='nosniff'
    assert 'strict-transport-security' in response.headers


def test_unknown_username_still_verifies_a_password(monkeypatch):
    app.dependency_overrides.clear();client=TestClient(app,base_url='https://testserver');calls=[]
    monkeypatch.setattr('lab.auth.dummy_password_hash',lambda:'dummy-test-hash')
    monkeypatch.setattr('lab.app.verify_password',lambda password,hashed:calls.append(hashed) or False)
    assert client.post('/login',data={'username':'missing','password':'wrong','csrf':form(client)}).status_code==400
    assert calls==['dummy-test-hash']


def test_exported_active_document_is_sandboxed_and_attached():
    client=TestClient(app)
    response=client.post('/api/exports',files={'file':('synthetic.html',b'<script>test</script>','text/html')})
    exported=client.get(response.json()['url'])
    assert exported.status_code==200 and 'attachment' in exported.headers['content-disposition']
    assert 'sandbox' in exported.headers['content-security-policy']


def test_startup_tightens_database_permissions_without_resetting_users():
    from lab.auth import init_db,database_path
    user();database_path().chmod(0o644)
    init_db();init_db()
    assert database_path().stat().st_mode&0o777==0o600
    c=get_db()
    try:assert c.execute('SELECT username FROM users').fetchone()[0]=='alice'
    finally:c.close()
