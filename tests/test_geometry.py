import math
from datetime import datetime,timezone
import pytest
from pydantic import ValidationError
from app.geometry import ecef,look,sun_vector,solar_altitude,is_sunlit,destination,distance_km,sample_track,intervals,predict,screen,illustrative_track,utc
from app.models import Trajectory,Location,Preferences

def test_wgs84_equatorial_position():
    assert ecef(0,0)==pytest.approx((6378.137,0,0))
def test_zenith_and_east():
    obs={'latitude':0,'longitude':0}
    assert look(obs,ecef(0,0,200))['elevation']==pytest.approx(90)
    assert look(obs,ecef(0,2,200))['azimuth']==pytest.approx(90)
def test_distant_same_altitude_below_horizon():
    assert look({'latitude':0,'longitude':0},ecef(0,10))['elevation']<0

def test_sun_at_march_equinox():
    v=sun_vector(datetime(2026,3,20,12,tzinfo=timezone.utc))
    assert sum(x*x for x in v)==pytest.approx(1)
    assert solar_altitude({'latitude':0,'longitude':0},v)>85
    assert solar_altitude({'latitude':0,'longitude':180},v)<-85

def test_shadow_geometry():
    s=(1,0,0)
    assert is_sunlit((6500,0,0),s)
    assert not is_sunlit((-6500,0,0),s)
    assert is_sunlit((-1000,6500,0),s)

def test_destination_roundtrip():
    lat,lon=destination(40,-73,50,250)
    assert distance_km(40,-73,lat,lon)==pytest.approx(250)

def test_dateline_interpolation():
    pts=[dict(t_s=0,latitude=0,longitude=179,altitude_km=100,powered=True,plume=True),dict(t_s=10,latitude=0,longitude=-179,altitude_km=110,powered=False,plume=False)]
    samples=list(sample_track({'points':pts}))
    assert abs(samples[1]['longitude'])==180
    assert samples[1]['powered'] is True and samples[-1]['powered'] is False

def test_multiple_intervals_remain_separate():
    ps=[{'t_s':i*5,'on':on} for i,on in enumerate([False,True,True,False,False,True,True])]
    out=intervals(ps,'on',utc('2026-03-20T00:00:00Z'))
    assert len(out)==2
    assert out[0]['start'].endswith('00:00:05+00:00')
    assert out[1]['start'].endswith('00:00:25+00:00')

def fixed_track(longitude):
    return Trajectory(source='Synthetic geometry unit test',kind='mission-specific',points=[dict(t_s=t,latitude=0,longitude=longitude,altitude_km=400,powered=True,plume=True) for t in (0,60)]).model_dump()

def test_ordinary_night_without_sunlit_plume(launch):
    launch['net']='2026-03-20T00:00:00Z'
    p=predict(launch,{'latitude':0,'longitude':0,'min_elevation_deg':5},fixed_track(0))
    assert p['ordinary_windows'] and not p['jellyfish_windows']
    assert p['max_elevation_deg']==90

def test_sunlit_plume_above_twilight_observer(launch):
    launch['net']='2026-03-20T12:00:00Z'
    obs={'latitude':0,'longitude':98,'min_elevation_deg':5}
    p=predict(launch,obs,fixed_track(98))
    assert p['jellyfish_windows'] and p['ordinary_windows']

def test_daylight_is_not_claimed_visible(launch):
    launch['net']='2026-03-20T12:00:00Z'
    p=predict(launch,{'latitude':0,'longitude':0},fixed_track(0))
    assert p['candidate'] and not p['ordinary_windows'] and not p['jellyfish_windows']
    assert 'no modeled' in p['ordinary']

def test_no_trajectory_means_unknown_not_fabricated(launch,location):
    p=screen(launch,location)
    assert p['mode']=='screening' and p['confidence']=='unknown'
    assert p['candidate'] and p['direction'] is None and p['first_visible'] is None

def test_missing_pad_never_defaults_to_zero(launch,location):
    launch['pad']={}
    p=screen(launch,location)
    assert not p['candidate'] and 'unavailable' in p['warnings'][0]

def test_scenario_explicit_estimated(launch):
    p=illustrative_track(launch,40,'User-generated WHAT IF test')
    assert p['kind']=='estimated' and 'WHAT-IF ONLY' in p['notes']
    assert len(p['points'])==10

@pytest.mark.parametrize('field,value',[('latitude',91),('longitude',-181),('latitude',float('nan')),('min_elevation_deg',-1),('timezone','Not/AZone')])
def test_location_validation(location,field,value):
    with pytest.raises(ValidationError): Location(**{**location,field:value})

@pytest.mark.parametrize('times',[[1,1],[10,0],[0,121]])
def test_invalid_track_timing(times):
    with pytest.raises(ValidationError):
        Trajectory(source='Synthetic test',points=[dict(t_s=t,latitude=0,longitude=0,altitude_km=100) for t in times])

def test_preferences_require_quiet_pair():
    with pytest.raises(ValidationError): Preferences(quiet_start=23)
    assert Preferences(lead_minutes=[15,60,15]).lead_minutes==[60,15]

def test_naive_timestamp_rejected():
    with pytest.raises(ValueError): utc('2026-01-01T00:00:00')
