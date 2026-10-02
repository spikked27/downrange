import asyncio,json,time
from datetime import datetime,timezone
import httpx,pytest
from app.providers import normalize,Providers


def raw_launch(id='raw'):
    return {'id':id,'name':'Test only','net':'2026-12-01T12:00:00Z','net_precision':{'name':'Second'},'status':{'abbrev':'Go','name':'Go'},'pad':{'latitude':'28.5','longitude':'-80.5','location':{'name':'Test'}},'mission':None,'rocket':None}

def test_normalize_optional_fields():
    data=normalize(raw_launch())
    assert data['pad']['latitude']==28.5 and data['time_precise']
    assert data['mission']=='' and data['vehicle']=='Unknown vehicle'

def test_precision_unknown_suppresses_alerts():
    data=raw_launch();data['net_precision']={'name':'Quarter'}
    assert not normalize(data)['time_precise']
    data['net_precision']=None
    assert not normalize(data)['time_precise']

def test_invalid_pad_not_zero():
    data=raw_launch();data['pad']['latitude']='NaN';data['pad']['longitude']=999
    assert normalize(data)['pad']['latitude'] is None
    assert normalize(data)['pad']['longitude'] is None


def mock_client(monkeypatch,handler):
    real=httpx.AsyncClient
    monkeypatch.setattr('app.providers.httpx.AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))

def test_feed_cache_and_quota(app,monkeypatch):
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'results':[raw_launch()],'count':1,'next':None})
    mock_client(monkeypatch,handler)
    asyncio.run(app.state.providers.refresh());asyncio.run(app.state.providers.refresh())
    assert len(calls)==1
    assert len(app.state.store.launches())==1
    assert app.state.store.meta('feed')['last_success']>0


def test_429_retains_cache_and_backs_off(app,loaded_launch,monkeypatch):
    mock_client(monkeypatch,lambda req:httpx.Response(429,headers={'Retry-After':'7200'}))
    result=asyncio.run(app.state.providers.refresh())
    assert result['next_attempt']-result['last_attempt']==7200
    assert result['error'] and app.state.store.launches()[0]['id']==loaded_launch['id']


def test_disappeared_launch_inactive(app,loaded_launch,monkeypatch):
    mock_client(monkeypatch,lambda req:httpx.Response(200,json={'results':[raw_launch()],'count':1,'next':None}))
    asyncio.run(app.state.providers.refresh())
    old=next(l for l in app.state.store.launches() if l['id']==loaded_launch['id'])
    assert old['feed_active'] is False


def test_bad_feed_retains_cache(app,loaded_launch,monkeypatch):
    mock_client(monkeypatch,lambda req:httpx.Response(200,json={'results':[{'bad':'record'}]}))
    result=asyncio.run(app.state.providers.refresh())
    assert result['error'] and app.state.store.launches()[0]['feed_active']


def test_weather_cache_does_not_turn_null_into_clear(app,location,monkeypatch):
    calls=[];now=time.time()
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'hourly':{'time':[now+3600],'cloud_cover':[None],'visibility':[None]}})
    mock_client(monkeypatch,handler)
    net=datetime.fromtimestamp(now+3600,timezone.utc).isoformat()
    w=asyncio.run(app.state.providers.weather(location,net))
    assert w['available'] and w['cloud_cover'] is None and w['visibility'] is None
    asyncio.run(app.state.providers.weather(location,net))
    assert len(calls)==1


def test_weather_out_of_range_does_not_fetch(app,location,monkeypatch):
    def handler(req):raise AssertionError('must not call remote API')
    mock_client(monkeypatch,handler)
    assert not asyncio.run(app.state.providers.weather(location,'2100-01-01T00:00:00Z'))['available']


def test_geo_results_include_timezone(app,monkeypatch):
    mock_client(monkeypatch,lambda req:httpx.Response(200,json={'results':[{'name':'Somewhere','latitude':1,'longitude':2,'admin1':'Test','country':'Test','timezone':'UTC','elevation':100}]}))
    data=asyncio.run(app.state.providers.geocode('Somewhere'))
    assert data[0]['timezone']=='UTC' and data[0]['elevation_m']==100
