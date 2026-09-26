import base64
import pytest
from fastapi.testclient import TestClient
from app import config
from app.main import app
from app.services import access_service as access

@pytest.fixture
def hosted(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DB_PATH',tmp_path/'hosted.sqlite3')
    monkeypatch.setattr(config,'PUBLIC_DEPLOYMENT',True)
    monkeypatch.setattr(config,'APP_ACCESS_PASSWORD','test-only-password-12345')
    monkeypatch.setattr(config,'PUBLIC_ORIGIN','https://bolorder.example')
    access.attempts.clear()
    access.global_calls.clear()
    with TestClient(app,base_url='https://bolorder.example') as client:
        yield client

def auth():
    return {'Authorization':'Basic '+base64.b64encode(b'bolorder:test-only-password-12345').decode()}

def test_public_endpoints_require_login(hosted):
    for path in ['/','/api/bootstrap','/api/inventory','/api/overview','/docs']:
        assert hosted.get(path).status_code==401
    assert hosted.get('/healthz').status_code==200
    assert hosted.get('/api/bootstrap',headers=auth()).status_code==200
    assert hosted.post('/api/tts',json={'text':'test','language':'en-IN'}).status_code==401

def test_hosted_origin_and_headers(hosted):
    good={**auth(),'Origin':'https://bolorder.example'}
    assert hosted.post('/api/demo/reset',headers=good).status_code==200
    bad={**auth(),'Origin':'https://unrelated.example'}
    assert hosted.post('/api/demo/reset',headers=bad).status_code==403
    response=hosted.get('/',headers=auth())
    assert response.headers['x-frame-options']=='DENY'
    assert response.headers['permissions-policy']=='microphone=(self), camera=(), geolocation=()'

def test_hosted_invalid_credentials_and_limits(hosted):
    assert hosted.get('/',headers={'Authorization':'Basic invalid'}).status_code==401
    for _ in range(19):
        hosted.get('/')
    assert hosted.get('/').status_code==429
    for _ in range(15):
        assert access.allow_ai_call('test-visitor')
    assert not access.allow_ai_call('test-visitor')

def test_public_startup_requires_strong_shared_secret(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DB_PATH',tmp_path/'blocked.sqlite3')
    monkeypatch.setattr(config,'PUBLIC_DEPLOYMENT',True)
    monkeypatch.setattr(config,'APP_ACCESS_PASSWORD','short')
    with pytest.raises(RuntimeError,match='APP_ACCESS_PASSWORD'):
        with TestClient(app):
            pass
