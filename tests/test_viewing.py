from datetime import datetime, timezone, timedelta
import json
import pytest
from app.viewing import plan
from app.geometry import illustrative_track


def point(t, elevation=10, ordinary=True, jellyfish=False, **extra):
    return dict(t_s=t, elevation=elevation, azimuth=180+t/10, range_km=500,
                ordinary=ordinary, jellyfish=jellyfish, above=elevation>=5,
                sun_altitude=-25, **extra)


def prediction(points, **extra):
    return dict(points=points, ordinary_windows=[], jellyfish_windows=[], **extra)


def test_later_coasting_peak_is_not_viewing_peak(launch, location):
    result=plan(launch,prediction([point(0,-5,False),point(60,10),point(120,20),point(180,80,False)]),location)
    assert result['first']['t_s']==60
    assert result['peak']['t_s']==120 and result['peak']['elevation']==20
    assert result['last']['t_s']==120
    assert result['viewing_duration_s']==60


def test_cutoff_gap_is_not_a_viewing_window(launch, location):
    result=plan(launch,prediction([point(0,-5,False),point(60),point(120),point(180,20,False),point(240),point(300)]),location)
    assert [(w['start_s'],w['end_s']) for w in result['windows']]==[(60,120),(240,300)]
    assert result['viewing_duration_s']==120


def test_plume_only_intervals_are_preserved(launch, location):
    result=plan(launch,prediction([point(0,10,False,True),point(60,20,False,True),point(120,30,False,False)]),location)
    assert not result['ordinary_windows'] and len(result['jellyfish_windows'])==1
    assert result['last']['t_s']==60


def test_same_scenario_times_and_directions_not_ensemble_union(launch, location):
    pred=prediction([point(300),point(360)],automatic=True)
    net=datetime.fromisoformat(launch['net'])
    pred['ordinary_windows']=[dict(start=(net+timedelta(seconds=180)).isoformat(),end=(net+timedelta(seconds=500)).isoformat())]
    result=plan(launch,pred,location)
    assert result['first']['t_s']==300
    assert result['scenario_windows']==[dict(start_s=180,end_s=500)]
    assert result['basis']=='plotted scenario'


def test_times_normalize_timezone_and_cross_midnight(launch, location):
    launch['net']='2026-10-01T23:58:00-04:00'
    result=plan(launch,prediction([point(180),point(240)]),location)
    assert result['first']['time']=='2026-10-02T04:01:00+00:00'


@pytest.mark.parametrize('points,status',[
    ([], 'no_path'),
    ([{**point(0,10,False),'sun_altitude':30}], 'daylight_unassessed'),
    ([point(0,10,False)], 'no_modeled_signal'),
    ([point(0,-5,False)], 'below_horizon'),
])
def test_absent_visibility_is_not_zero_time(launch,location,points,status):
    result=plan(launch,prediction(points),location)
    assert result['status']==status and result['first'] is None and result['peak'] is None


def test_zero_elapsed_time_is_valid(launch, location):
    result=plan(launch,prediction([point(0),point(10)]),location)
    assert result['first']['t_s']==0


def test_track_discontinuities_stay_separate(launch, location):
    result=plan(launch,prediction([point(0),point(10),point(300),point(310)]),location)
    assert len(result['windows'])==2


def test_provisional_clock_is_flagged(launch, location):
    launch['time_precise']=False
    assert not plan(launch,prediction([point(60)]),location)['time_precise']


def test_api_exposes_source_progress_without_raw_tracks(admin,app,loaded_launch,location):
    lid=admin.post('/api/locations',json=location).json()['id']
    app.state.store.set_meta('acquisition_status',{'running':True,'checked':1,'sources':{'test':{'status':'available'}}})
    data=admin.get('/api/launches',params={'location_id':lid}).json()
    assert data['sources']['running'] is True
    assert 'viewing_plan' in data['launches'][0]['prediction']
    assert 'points' not in data['launches'][0]['prediction']
    assert 'acquisition' not in data['launches'][0]


def test_weather_targets_viewing_peak_not_launch(admin,app,loaded_launch,location,monkeypatch):
    launch=loaded_launch
    when=datetime.now(timezone.utc).replace(hour=3,minute=54,second=0,microsecond=0)+timedelta(days=1)
    launch['net']=when.isoformat()
    app.state.store.execute('UPDATE launches SET data=? WHERE id=?',(json.dumps(launch),launch['id']))
    track=illustrative_track(launch,45,'Synthetic weather-time regression fixture')
    app.state.store.execute('INSERT INTO tracks VALUES(?,?)',(launch['id'],json.dumps(track)))
    lid=admin.post('/api/locations',json=location).json()['id']
    detail=admin.get('/api/launches/'+launch['id'],params={'location_id':lid}).json()
    peak=detail['prediction']['viewing_plan']['peak']
    assert peak is not None
    calls=[]
    async def weather(loc,net):
        calls.append(net);return {'available':False,'reason':'Offline test'}
    monkeypatch.setattr(app.state.providers,'weather',weather)
    response=admin.get('/api/weather',params={'location_id':lid,'launch_id':launch['id']})
    assert response.status_code==200
    assert calls==[peak['time']]
    assert response.json()['target_basis']=='modeled viewing peak'


def test_source_check_rejects_disabled_worker(admin):
    assert admin.post('/api/admin/sources/refresh').status_code==409
