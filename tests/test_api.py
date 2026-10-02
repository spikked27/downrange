import base64,json,time
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from app.main import create_app
from app.config import Settings
from app.security import password_hash,verify_password,validate_push_endpoint
from conftest import HEADERS,PASSWORD,INVITATION

def test_health_and_private_default(client):
    assert client.get('/healthz').status_code==200
    assert client.get('/api/locations').status_code==401
    assert client.get('/api/config').json()['version']=='0.3.0-alpha.2'

def test_csrf_headers_and_origin(client):
    creds={'username':'admin','password':PASSWORD}
    assert client.post('/api/login',json=creds,headers={'X-Downrange':'bad'}).status_code==403
    assert client.post('/api/login',json=creds,headers={'Origin':'https://attacker.example'}).status_code==403
    assert client.post('/api/login',json=creds).status_code==200

def test_cookie_and_password_hash(admin,app):
    assert admin.get('/api/me').json()['username']=='admin'
    stored=app.state.store.one('SELECT password FROM users WHERE id=1')['password']
    assert stored!=PASSWORD and verify_password(PASSWORD,stored)
    assert not verify_password('incorrect',stored)
    assert 'Cache-Control' in admin.get('/api/me').headers

def test_secure_cookie(tmp_path):
    app=create_app(Settings(data_dir=tmp_path,worker_enabled=False,public_url='https://launch.example.com',admin_password=PASSWORD))
    with TestClient(app,base_url='https://launch.example.com') as c:
        r=c.post('/api/login',json={'username':'admin','password':PASSWORD},headers=HEADERS)
        assert r.status_code==200 and 'Secure' in r.headers['set-cookie'] and 'HttpOnly' in r.headers['set-cookie']
        assert c.get('/api/me').status_code==200

def test_locations_crud(admin,location):
    r=admin.post('/api/locations',json=location); assert r.status_code==201,r.text
    lid=r.json()['id']
    r=admin.put(f'/api/locations/{lid}',json={**location,'name':'New name'}); assert r.status_code==200
    assert admin.get('/api/locations').json()[0]['name']=='New name'
    assert admin.delete(f'/api/locations/{lid}').status_code==200
    assert admin.get('/api/locations').json()==[]

def test_account_location_isolation_and_admin_auth(admin,app,location,loaded_launch):
    lid=admin.post('/api/locations',json=location).json()['id']
    with TestClient(app) as other:
        other.headers.update(HEADERS)
        r=other.post('/api/register',json={'username':'viewer','password':PASSWORD,'invite_code':INVITATION});assert r.status_code==201
        assert other.post('/api/login',json={'username':'viewer','password':PASSWORD}).status_code==200
        assert other.get('/api/locations').json()==[]
        assert other.put(f'/api/locations/{lid}',json=location).status_code==404
        assert other.get('/api/launches',params={'location_id':lid}).status_code==404
        assert other.get('/api/admin/status').status_code==403
        assert other.post(f'/api/admin/trajectories/{loaded_launch["id"]}/scenario',json={'heading_deg':40}).status_code==403

def test_registration_bad_invite(client):
    r=client.post('/api/register',json={'username':'viewer','password':PASSWORD,'invite_code':'bad'})
    assert r.status_code==403

def test_password_change_revokes_existing_sessions(admin):
    r=admin.post('/api/account/password',json={'current_password':PASSWORD,'new_password':'Updated-test-password-123'})
    assert r.status_code==200
    assert admin.get('/api/me').status_code==401
    assert admin.post('/api/login',json={'username':'admin','password':PASSWORD}).status_code==401
    assert admin.post('/api/login',json={'username':'admin','password':'Updated-test-password-123'}).status_code==200

def test_payload_limit(admin):
    r=admin.post('/api/locations',content='x'*(1024*1024+1),headers={'Content-Type':'application/json'})
    assert r.status_code==413

def test_forecast_and_scenario_import(admin,app,location,loaded_launch):
    lid=admin.post('/api/locations',json=location).json()['id']
    r=admin.get('/api/launches',params={'location_id':lid});assert r.status_code==200,r.text
    assert r.json()['launches'][0]['prediction']['mode']=='trajectory'
    assert r.json()['launches'][0]['prediction']['confidence']=='estimated'
    url=f'/api/admin/trajectories/{loaded_launch["id"]}'
    assert admin.post(url+'/scenario',json={'heading_deg':40}).status_code==200
    track=admin.get(url).json()
    assert track['kind']=='estimated'
    assert admin.put(url,json=track).status_code==200
    detail=admin.get(f'/api/launches/{loaded_launch["id"]}',params={'location_id':lid}).json()
    assert detail['prediction']['mode']=='trajectory' and detail['prediction']['points']
    assert admin.delete(url).status_code==200
    assert app.state.store.track(loaded_launch['id']) is None

@pytest.mark.parametrize('endpoint',['http://fcm.googleapis.com/x','https://localhost/x','https://127.0.0.1/x','https://fcm.googleapis.com.evil.example/x','https://evil@fcm.googleapis.com/x','https://fcm.googleapis.com:8888/x'])
def test_push_ssrf_endpoints_rejected(endpoint):
    with pytest.raises(ValueError): validate_push_endpoint(endpoint)

def test_browser_subscription_and_delete(admin):
    key=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    b64=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=').decode()
    r=admin.post('/api/push/subscribe',json={'endpoint':'https://fcm.googleapis.com/fcm/send/test-endpoint','keys':{'p256dh':b64(key),'auth':b64(b'a'*16)}})
    assert r.status_code==200,r.text
    assert admin.get('/api/push/status').json()['devices']==1
    sid=r.json()['id'];assert admin.delete(f'/api/push/subscriptions/{sid}').status_code==200
    assert admin.get('/api/push/status').json()['devices']==0

def test_invalid_curve_point_rejected(admin):
    b64=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=').decode()
    r=admin.post('/api/push/subscribe',json={'endpoint':'https://fcm.googleapis.com/fcm/send/test-endpoint','keys':{'p256dh':b64(b'\x04'+b'\x00'*64),'auth':b64(b'a'*16)}})
    assert r.status_code==422

def test_demo_and_live_storage_cannot_mix(settings):
    settings.demo_mode=True;create_app(settings)
    settings.demo_mode=False
    with pytest.raises(RuntimeError):create_app(settings)

def test_frontend_shell_and_no_api_cache(client):
    assert client.get('/').status_code==200
    assert client.get('/sw.js').headers['Service-Worker-Allowed']=='/'
    assert client.get('/manifest.webmanifest').json()['name']=='Downrange'
    assert client.get('/api/config').headers['cache-control']=='no-store'
