"""CI only: create/check isolated appdata through the running app's HTTP API."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request
import urllib.error

ROOT='http://127.0.0.1:8097'
state_file=Path('/data/ci-upgrade-fixture.json')

def api(path,method='GET',body=None,cookie=''):
    request=urllib.request.Request(ROOT+'/api'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json','X-Downrange':'1','Cookie':cookie,'Origin':ROOT},method=method)
    with urllib.request.urlopen(request,timeout=30) as response:
        return json.loads(response.read()),response.headers.get('set-cookie','').split(';')[0]

def b64(data):return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

if sys.argv[1]=='seed':
    credentials={'username':'admin','password':os.environ['ADMIN_PASSWORD']}
    _,cookie=api('/login','POST',credentials)
    loc,_=api('/locations','POST',{'name':'Upgrade continuity fixture','latitude':40.7,'longitude':-73.35,
        'elevation_m':10,'min_elevation_deg':8,'timezone':'America/New_York','alerts':True},cookie)
    prefs,_=api('/preferences','PUT',{'enabled':True,'lead_minutes':[60,15],'include_candidates':False,
        'include_estimates':True,'jellyfish_only':False,'schedule_changes':True,'quiet_start':23,'quiet_end':6},cookie)
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    raw=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    api('/push/subscribe','POST',{'endpoint':'https://fcm.googleapis.com/fcm/send/ci-isolated-never-delivered',
        'keys':{'p256dh':b64(raw),'auth':b64(b'x'*16)}},cookie)
    state={'credentials':credentials,'cookie':cookie,'location':loc,'preferences':prefs,
        'vapid':hashlib.sha256(Path('/data/vapid-private.pem').read_bytes()).hexdigest()}
    state_file.write_text(json.dumps(state));state_file.chmod(0o600)
    print('Seeded isolated old-image account, session, location, preferences and subscription.')
else:
    state=json.loads(state_file.read_text());cookie=state['cookie']
    me,_=api('/me',cookie=cookie);assert me['username']=='admin','Existing login session was not retained'
    api('/login','POST',state['credentials'])
    locations,_=api('/locations',cookie=cookie);assert locations==[state['location']]
    prefs,_=api('/preferences',cookie=cookie);assert prefs==state['preferences']
    status,_=api('/push/status',cookie=cookie);assert status['devices']==1
    assert hashlib.sha256(Path('/data/vapid-private.pem').read_bytes()).hexdigest()==state['vapid']
    config,_=api('/config');assert config['version']==os.environ['EXPECTED_VERSION']
    assert config.get('sources_enabled') is False
    snapshots=list(Path('/data/backups').glob('before-*/snapshot.json'))
    assert snapshots,'Pre-upgrade consistent snapshot was not created'
    snapshot=snapshots[-1].parent
    assert (snapshot/'downrange.sqlite3').exists() and (snapshot/'vapid-private.pem').exists()
    print('PASS: old password, login session, saved location, preferences, push subscription and VAPID key survived replacement.')
    print('PASS: automatic pre-upgrade snapshot exists. No real push was sent.')
