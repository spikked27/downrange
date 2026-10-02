import json
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from app import __version__
from app.main import create_app
from app.upgrade import protect_existing_data
from conftest import PASSWORD,HEADERS


def test_restart_keeps_password_session_preferences_locations_and_key(settings,location):
    app=create_app(settings)
    with TestClient(app) as client:
        client.headers.update(HEADERS)
        assert client.post('/api/login',json={'username':'admin','password':PASSWORD}).status_code==200
        cookie=client.cookies.get('downrange_session')
        saved=client.post('/api/locations',json=location).json()
        preferences=client.put('/api/preferences',json={'lead_minutes':[30],'include_estimates':True}).json()
    key=(settings.data_dir/'vapid-private.pem').read_bytes()
    app.state.store.set_meta('application_version','0.2.0-alpha.1')
    settings.admin_password='Different-bootstrap-not-a-reset'
    replacement=create_app(settings)
    with TestClient(replacement) as client:
        client.headers.update(HEADERS)
        client.cookies.set('downrange_session',cookie)
        assert client.get('/api/me').json()['username']=='admin'
        assert client.get('/api/locations').json()==[saved]
        assert client.get('/api/preferences').json()==preferences
        assert client.post('/api/login',json={'username':'admin','password':PASSWORD}).status_code==200
    assert (settings.data_dir/'vapid-private.pem').read_bytes()==key
    directory=settings.data_dir/'backups'/('before-'+__version__)
    assert (directory/'vapid-private.pem').read_bytes()==key
    with sqlite3.connect(directory/'downrange.sqlite3') as connection:
        assert json.loads(connection.execute("SELECT value FROM meta WHERE key='application_version'").fetchone()[0])=='0.2.0-alpha.1'
    assert (directory/'downrange.sqlite3').stat().st_mode & 0o777==0o600
    assert protect_existing_data(settings.data_dir) is None


def test_legacy_without_version_marker_is_snapshotted(app,settings):
    app.state.store.execute("DELETE FROM meta WHERE key='application_version'")
    directory=protect_existing_data(settings.data_dir)
    first=(directory/'downrange.sqlite3').read_bytes()
    app.state.store.set_meta('another','later change')
    assert protect_existing_data(settings.data_dir)==directory
    assert (directory/'downrange.sqlite3').read_bytes()==first
    assert json.loads((directory/'snapshot.json').read_text())['from']=='legacy'


def test_clear_origin_error_is_before_password_verification(client):
    result=client.post('/api/login',json={'username':'admin','password':'irrelevant-password'},headers={'Origin':'https://other.example'})
    assert result.status_code==403
    assert 'before password verification' in result.json()['detail']


def test_release_publishes_exact_smoke_tested_image():
    root=Path(__file__).resolve().parents[1]
    workflow=(root/'.github/workflows/build.yml').read_text()
    assert 'scripts/smoke-upgrade.sh' in workflow
    assert 'docker tag downrange-ci:test "$IMAGE:latest"' in workflow
    assert 'DOCKER_CONFIG="$CONFIG" docker pull' in workflow
    assert 'CURRENT_MAIN' in workflow
    assert 'docker push "$IMAGE:$VERSION"' in workflow
