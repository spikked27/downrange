import json,asyncio,time
import httpx,pytest
from app.source_inputs import (CachedReader,public_url,SourceUnavailable,nextspaceflight_index,
    nextspaceflight_facts,jellyfish_facts,official_facts,mission_name)
from app.acquisition import select_evidence,identity
from app.trajectory_sources import from_ecef_m,flightclub_tracks,historical_profile
from app.geometry import ecef,predict
from app.profiles import automatic_tracks

@pytest.fixture
def mission(launch):
    return {**launch,'name':'Falcon Heavy | NROL-97','mission_name':'NROL-97',
            'vehicle':'Falcon Heavy','net':'2026-10-02T03:54:00+00:00',
            'pad':{'latitude':28.608,'longitude':-80.604}}

def page_for(name='NROL-97',net='2026-10-02T03:54:00Z',heading=45):
    payload=json.dumps({'name':name,'net':net,'heading':heading})
    return f'<h1>{name}</h1><p>Launching</p><p>Northeast</p><script>self.__next_f.push([1,{json.dumps(payload)}])</script>'

def test_nextspaceflight_decodes_actual_nextjs_shape(mission):
    row=nextspaceflight_facts(page_for(),mission,'https://nextspaceflight.com/launches/details/7826/')
    assert row['heading_deg']==45 and row['kind']=='published-direction'

def test_zero_heading_is_not_missing(mission):
    assert nextspaceflight_facts(page_for(heading=0),mission,'https://nextspaceflight.com/launches/details/1/')['heading_deg']==0

@pytest.mark.parametrize('kwargs',[{'name':'NROL-98'},{'net':'2025-10-02T03:54:00Z'}])
def test_page_identity_mismatch_rejected(mission,kwargs):
    with pytest.raises(SourceUnavailable):nextspaceflight_facts(page_for(**kwargs),mission,'https://nextspaceflight.com/launches/details/1/')

def test_no_date_rejects_even_valid_heading(mission):
    with pytest.raises(SourceUnavailable):nextspaceflight_facts('<h1>NROL-97</h1><p>Launching Northeast</p>',mission,'https://nextspaceflight.com/launches/details/1/')

def test_index_does_not_include_countdown_in_name():
    rows=nextspaceflight_index('<a href="/launches/details/7826/"><div>20 minutes</div><h3>NROL-97<!-- --> <svg></svg></h3></a>')
    assert rows==[{'name':'NROL-97','url':'https://nextspaceflight.com/launches/details/7826/'}]

def test_mission_numbers_preserved():
    assert mission_name('Falcon 9 | Starlink Group 6-51')==mission_name('Starlink 6-51')
    assert mission_name('Starlink 6-51')!=mission_name('Starlink 6-52')

def test_jellyfish_is_heading_only_schedule_not_overwritten(mission):
    data={'upcoming':[{'mission':'NROL-97','pad_lat':28.608,'pad_lng':-80.604,'trajectory_heading_deg':40.7,
                       'launch_time_utc':'2026-10-01T23:53:00Z','prediction_available':False}]}
    row=jellyfish_facts(data,mission)
    assert row['heading_deg']==40.7 and not row['prediction_supported_by_source']
    assert mission['net']=='2026-10-02T03:54:00+00:00'
    data['upcoming'][0]['manual_test']=True
    assert jellyfish_facts(data,mission) is None

def test_conflicting_directions_kept_not_averaged():
    rows=[{'kind':'published-direction','heading_deg':45,'spread_deg':12},
          {'kind':'published-estimate','heading_deg':190,'spread_deg':12}]
    chosen,notes=select_evidence(rows)
    assert len(chosen)==2 and notes
    chosen,notes=select_evidence([rows[0],{**rows[1],'heading_deg':40.7}])
    assert len(chosen)==1 and not notes

def test_official_context_required(mission):
    assert official_facts('<p>Other mission launches northeast</p>',mission,'https://www.nasa.gov/mission/') is None
    row=official_facts('<h1>NROL-97</h1><p>Launch azimuth: 40.7 degrees</p>',mission,'https://www.nasa.gov/mission/')
    assert row['heading_deg']==40.7

@pytest.mark.parametrize('url',['http://nextspaceflight.com/','https://localhost/','https://127.0.0.1/',
    'https://user@nextspaceflight.com/','https://nextspaceflight.com:8443/',
    'https://nextspaceflight.com.evil.test/','https://raw.githubusercontent.com/unknown/malware/main/file'])
def test_source_url_boundaries(url):
    with pytest.raises(SourceUnavailable):public_url(url)

def mock_http(monkeypatch,handler):
    real=httpx.AsyncClient
    monkeypatch.setattr('app.source_inputs.httpx.AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    async def fast_sleep(_):pass
    monkeypatch.setattr('app.source_inputs.asyncio.sleep',fast_sleep)

def test_robots_disallow_prevents_page_fetch(app,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(200,text='User-agent: *\nDisallow: /launches/')
    mock_http(monkeypatch,handler)
    with pytest.raises(SourceUnavailable):asyncio.run(CachedReader(app.state.store).get('https://nextspaceflight.com/launches/'))
    assert calls==['/robots.txt']

def test_robots_404_allows_and_cache_survives_new_reader(app,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(404 if req.url.path=='/robots.txt' else 200,text='page')
    mock_http(monkeypatch,handler)
    assert asyncio.run(CachedReader(app.state.store).get('https://nextspaceflight.com/launches/'))=='page'
    assert asyncio.run(CachedReader(app.state.store).get('https://nextspaceflight.com/launches/'))=='page'
    assert len(calls)==2

def test_source_redirect_not_followed(app,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(str(req.url));return httpx.Response(302,headers={'Location':'http://127.0.0.1/private'})
    mock_http(monkeypatch,handler)
    with pytest.raises(SourceUnavailable):asyncio.run(CachedReader(app.state.store).get('https://nextspaceflight.com/launches/',robots=False))
    assert len(calls)==1

def test_source_size_limit(app,monkeypatch):
    mock_http(monkeypatch,lambda req:httpx.Response(200,content=b'x'*110))
    with pytest.raises(SourceUnavailable):asyncio.run(CachedReader(app.state.store).get('https://nextspaceflight.com/launches/',robots=False,max_bytes=100))

def test_source_rate_limit_and_error_redaction(app,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req);return httpx.Response(429,headers={'Retry-After':'3600'})
    mock_http(monkeypatch,handler);r=CachedReader(app.state.store)
    for _ in range(2):
        with pytest.raises(SourceUnavailable):asyncio.run(r.get('https://nextspaceflight.com/launches/',robots=False))
    assert len(calls)==1

def test_ecef_meters_roundtrip():
    xyz=[v*1000 for v in ecef(40,-73,200)]
    assert from_ecef_m(*xyz)==pytest.approx((40,-73,200),abs=1e-7)

def simulation(launch_id):
    def point(t,h):return {'t':t,'x_NI':[v*1000 for v in ecef(28,-80,h)],'frames':['EME2000','ITRF','ENU'],'ts':100}
    return {'id':'sim_fixture','mission':{'launchLibraryId':launch_id},'data':{'stageTrajectories':[
        {'stageNumber':1,'telemetry':[point(0,0),point(10,1)]},
        {'stageNumber':2,'telemetry':[point(200,100),point(210,110)]}]}}

def test_flightclub_units_exact_identity_and_separate_stages(mission):
    tracks=flightclub_tracks(simulation(mission['id']),mission['id'])
    assert len(tracks)==2
    assert tracks[1]['points'][0]['altitude_km']==pytest.approx(100)
    assert tracks[1]['points'][0]['t_s']==200
    assert all(t['kind']=='mission-specific' for t in tracks)
    with pytest.raises(SourceUnavailable):flightclub_tracks(simulation('wrong'),mission['id'])

def test_flightclub_rejects_undefined_frame(mission):
    data=simulation(mission['id']);data['data']['stageTrajectories'][0]['telemetry'][0]['frames']=['EME2000','unknown']
    with pytest.raises(SourceUnavailable):flightclub_tracks(data,mission['id'])

def test_history_data_units_and_event_gap():
    ts=list(range(0,301));data={'time':ts,'altitude':[t/3 for t in ts],'downrange_distance':[t for t in ts]}
    profile=historical_profile(data,{'meco':150,'ses1':160,'seco1':300},'Test historical launch','https://example.test/data')
    assert [p for p in profile['samples'] if p[0]==150][0][3] is False
    assert profile['samples'][-1]==[300,100,300,False]

@pytest.mark.parametrize('vehicle,lat,lon',[('Falcon Heavy',28.6,-80.6),('Electron',-39.2,177.9),
    ('Vulcan',28.5,-80.5),('Ariane 6',5.2,-52.8),('H3',30.4,130.9),
    ('PSLV',13.7,80.2),('Long March 3B',28.2,102),('Soyuz',45.9,63.3),
    ('New Glenn',28.5,-80.5),('Spectrum',69.1,15.6),('Unknown vehicle',1,2),('New Shepard',31.4,-104.8)])
def test_all_vehicle_families_evaluated_without_falcon_gate(mission,vehicle,lat,lon):
    mission.update(vehicle=vehicle,pad={'latitude':lat,'longitude':lon})
    tracks=automatic_tracks(mission)
    assert tracks and all(t['kind']=='estimated' for t in tracks)
    assert all('Falcon 9' not in t['source'] for t in tracks)

def test_acquired_track_hydration_has_identity_and_expiry(app,mission):
    app.state.store.set_meta('acquired:'+mission['id'],{'identity':identity(mission),'valid_until':time.time()+10,'directions':[{'heading_deg':40.7,'spread_deg':10}]})
    assert 'acquisition' in app.state.store.hydrate(mission)
    assert 'acquisition' not in app.state.store.hydrate({**mission,'vehicle':'wrong vehicle'})

def test_manual_track_still_overrides_simulation_and_priors(mission,location):
    track=flightclub_tracks(simulation(mission['id']),mission['id'])[0]
    mission['acquisition']={'tracks':[track]}
    pred=predict(mission,location,track)
    assert not pred.get('automatic')
