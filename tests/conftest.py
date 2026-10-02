import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json, time
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

PASSWORD='Test-only-password-12345'
INVITATION='Test-invitation-12345678'
HEADERS={'X-Downrange':'1'}

@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path,admin_password=PASSWORD,invite_code=INVITATION,worker_enabled=False)
@pytest.fixture
def app(settings):
    return create_app(settings)
@pytest.fixture
def client(app):
    with TestClient(app) as c:
        c.headers.update(HEADERS)
        yield c
@pytest.fixture
def admin(client):
    r=client.post('/api/login',json={'username':'admin','password':PASSWORD})
    assert r.status_code==200,r.text
    return client
@pytest.fixture
def launch():
    return {'id':'test-launch','name':'Synthetic TEST mission','net':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'status':'Go','status_name':'Go','time_precise':True,'precision':'Second','pad':{'latitude':37.8,'longitude':-75.5,'name':'Test pad','site':'Test'},'feed_active':True,'demo':False,'mission':'Synthetic fixture, not a real launch','provider':'Test','vehicle':'Test','orbit':'Test'}
@pytest.fixture
def loaded_launch(app,launch):
    app.state.store.execute('INSERT INTO launches VALUES(?,?,?)',(launch['id'],json.dumps(launch),time.time()))
    return launch
@pytest.fixture
def location():
    return dict(name='Test place',latitude=40.7,longitude=-73.35,elevation_m=10,min_elevation_deg=5,timezone='America/New_York',alerts=True)
