import asyncio
import json
import time
from datetime import timedelta
from pathlib import Path
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.horizon import viewing_limit, validate_profile
from app.evidence import identity, usable, needs_research, quality, diagnostic_snapshot
from app.geometry import predict, utc
from app.models import Location
from app.acquisition import Acquisition
from app.main import create_app
from app.trajectory_sources import history_candidates


@pytest.mark.parametrize('az,expected',[(0,5),(180,45),(157.5,22.5),(202.5,22.5),(360,5),(-180,45)])
def test_obstruction_interpolation(az,expected):
    observer={'min_elevation_deg':5,'horizon_profile':[0,0,0,0,45,0,0,0]}
    assert viewing_limit(observer,az)==pytest.approx(expected)


def test_obstruction_north_seam():
    observer={'min_elevation_deg':0,'horizon_profile':[20,0,0,0,0,0,0,40]}
    assert viewing_limit(observer,337.5)==30
    assert viewing_limit(observer,-22.5)==30


@pytest.mark.parametrize('profile',[[0]*7,[0]*9,[float('nan')]*8,[float('inf')]*8,[-1]*8,[86]*8])
def test_invalid_obstructions(profile):
    with pytest.raises(ValueError):validate_profile(profile)


def test_location_profile_model_validation(location):
    assert Location(**location).horizon_profile==[]
    with pytest.raises(ValidationError):Location(**location,horizon_profile=[1,2])
    assert Location(**location,horizon_profile=[10]*8).horizon_profile==[10]*8


def test_obstructions_change_visibility_not_launch_path(launch):
    launch['net']='2026-03-20T00:00:00Z'
    observer={'latitude':0,'longitude':0,'min_elevation_deg':5}
    track={'kind':'estimated','source':'Unit-test geometry only','points':[
        {'t_s':t,'latitude':-2,'longitude':0,'altitude_km':100,'powered':True,'plume':False} for t in (0,60)]}
    unblocked=predict(launch,observer,track)
    blocked=predict(launch,{**observer,'horizon_profile':[0,0,0,0,85,0,0,0]},track)
    assert unblocked['ordinary_windows'] and not blocked['ordinary_windows']
    assert blocked['points'][0]['horizon_limit_deg']==85
    assert unblocked['points'][0]['azimuth']==blocked['points'][0]['azimuth']


def test_evidence_invalidated_by_orbit_change(launch):
    assert identity(launch)!=identity({**launch,'orbit':'Polar Orbit'})
    assert identity(launch)==identity({**launch,'feed_seen':time.time()})


def test_source_component_expiries_are_independent(launch):
    now=time.time()
    acquired={'identity':identity(launch),'valid_until':now+100,'directions_until':now-1,'tracks_until':now+50,
              'directions':[{'heading_deg':45}],'tracks':[{'source':'test'}],'profiles':[]}
    result=usable(acquired,launch,now)
    assert result['directions']==[] and result['tracks']
    assert acquired['directions'],'Do not mutate cached provenance'


def test_large_launch_delay_requires_new_source_match(launch):
    now=time.time()
    old={'identity':identity(launch),'schedule_net':launch['net'],'valid_until':now+999999}
    changed={**launch,'net':(utc(launch['net'])+timedelta(days=3)).isoformat()}
    assert usable(old,changed,now)=={}
    assert needs_research(old,changed,now)


def test_even_small_schedule_change_requests_recheck(launch):
    now=time.time()
    old={'identity':identity(launch),'schedule_net':launch['net'],'checked':now}
    assert not needs_research(old,launch,now)
    changed={**launch,'net':(utc(launch['net'])+timedelta(minutes=5)).isoformat()}
    assert needs_research(old,changed,now)


def test_expired_sources_keep_diagnostics_not_trajectories(launch):
    now=time.time();old={'identity':identity(launch),'valid_until':now-1,'tracks':[{}],
                        'directions':[{}],'profiles':[{}],'errors':['upstream unavailable']}
    result=usable(old,launch,now)
    assert result['stale'] and result['errors']
    assert not result['tracks'] and not result['directions'] and not result['profiles']


def test_quality_does_not_call_attempt_time_fresh_evidence(launch):
    launch['acquisition']={'checked':1000,'evidence':[{'observed_at':100}],'directions':[{}],'profiles':[{}]}
    result=quality(launch,{'points':[]},now=1100)
    assert result['last_attempt']==1000 and result['oldest_evidence_at']==100
    assert result['code']=='direction_history'
    assert result['schedule_fresh'] is False


def test_redacted_diagnostics(admin,app,location):
    location={**location,'name':'private place','latitude':12.345678,'longitude':87.654321}
    admin.post('/api/locations',json=location)
    result=admin.get('/api/diagnostics')
    assert result.status_code==200
    data=result.json();blob=json.dumps(data)
    assert '12.345678' not in blob and '87.654321' not in blob and 'private place' not in blob
    assert 'vapid_public_key' not in blob
    assert data['account_counts']['locations']==1
    assert admin.get('/api/diagnostics').headers['cache-control']=='no-store'


def test_diagnostics_require_login(client):
    assert client.get('/api/diagnostics').status_code==401


def test_password_whitespace_preserved(settings):
    settings.admin_password='  keep-spaces-in-this-password  '
    application=create_app(settings)
    with TestClient(application) as client:
        result=client.post('/api/login',json={'username':'admin','password':settings.admin_password},headers={'X-Downrange':'1'})
        assert result.status_code==200


def test_cancelled_unsent_reminder_can_be_replanned(app):
    n=app.state.notifier;s=app.state.store;now=time.time();subs=[{'id':'test-device'}]
    args=(1,subs,'same-event','launch','location','net','reminder')
    n.queue(*args,{'title':'old'},now,now+120)
    s.execute("UPDATE deliveries SET status='cancelled'")
    n.queue(*args,{'title':'updated'},now+1,now+121)
    row=s.one('SELECT * FROM deliveries')
    assert row['status']=='pending' and json.loads(row['payload'])['title']=='updated'
    s.execute("UPDATE deliveries SET status='sent'")
    n.queue(*args,{'title':'must-not-replay'},now+2,now+122)
    row=s.one('SELECT * FROM deliveries')
    assert row['status']=='sent' and json.loads(row['payload'])['title']=='updated'


def test_generic_engine_not_used_for_all_mission_classes(launch):
    catalog=[{'mission_name':name,'analysed_stage':2} for name in ('DM-1','Orbcomm OG2','SES-9','Thaicom 8','SpaceX CRS-8')]
    l={**launch,'vehicle':'Falcon 9','orbit':'Geostationary Transfer Orbit'}
    assert {p['mission_name'] for p in history_candidates(catalog,l)}=={'SES-9','Thaicom 8'}
    l['orbit']='International Space Station'
    assert {p['mission_name'] for p in history_candidates(catalog,l)}=={'DM-1','SpaceX CRS-8'}
    l['vehicle']='Ariane 6'
    assert history_candidates(catalog,l)==[]


def test_one_failed_mission_does_not_abort_acquisition(app,loaded_launch,monkeypatch):
    s=app.state.store;second={**loaded_launch,'id':'second-mission'}
    s.execute('INSERT INTO launches VALUES(?,?,?)',(second['id'],json.dumps(second),time.time()))
    async def read(url,*args,**kwargs):
        body='[]' if 'Laucnhes' in url else '{}' if '/api/' in url else '<html></html>'
        return body,{'observed_at':time.time()}
    attempted=[]
    async def research(launch,*args):
        attempted.append(launch['id'])
        if launch['id']==loaded_launch['id']:raise ValueError('synthetic malformed record')
        return {'identity':identity(launch),'checked':time.time(),'valid_until':0}
    a=app.state.acquisition
    monkeypatch.setattr(a,'read',read);monkeypatch.setattr(a,'research',research)
    result=asyncio.run(a.refresh())
    assert len(attempted)==2 and result['errors']==1 and not result['running']
    assert not s.meta('acquisition_status')['running']


def test_no_schedule_does_not_poll_every_source(app,monkeypatch):
    async def forbidden(*args,**kwargs):raise AssertionError('No launches to research')
    monkeypatch.setattr(app.state.acquisition,'read',forbidden)
    result=asyncio.run(app.state.acquisition.refresh())
    assert result['attempted']==0 and not result['running']


def test_shared_prediction_cache_ignores_feed_poll_timestamp(launch,location):
    from app.prediction_cache import predict as cached,_calculate
    _calculate.cache_clear()
    cached(launch,location,None)
    cached({**launch,'feed_seen':time.time()},location,None)
    assert _calculate.cache_info().hits==1


def test_new_static_asset_and_html_version_are_coherent(client):
    from app import __version__
    html=client.get('/').text
    assert '/static/v1-ui.js?v='+__version__ in html
    assert client.get('/static/v1-ui.js').headers['cache-control']=='no-cache'


def test_worker_split_present():
    source=(Path(__file__).resolve().parents[1]/'app/main.py').read_text()
    notification_loop=source.split('    async def loop():')[1].split('    async def feed_loop():')[0]
    assert 'providers.refresh' not in notification_loop
    assert 'notifier.deliver' in notification_loop
