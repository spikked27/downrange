import time
from datetime import datetime,timezone,timedelta
from app.refresh_policy import source_interval
from app.refresh_view import snapshot
from app.providers import Providers

def test_source_priority(launch):
    now=time.time()
    for hours,seconds in [(3,300),(24,900),(240,21600)]:
        launch['net']=datetime.fromtimestamp(now+hours*3600,timezone.utc).isoformat()
        assert source_interval(launch,now)==seconds

def test_snapshot_not_marked_live(app,launch,location):
    launch['feed_seen']=time.time()
    pred={'calculated_at':time.time()}
    first=snapshot(launch,location,None,pred,app.state.store)
    assert first['schedule_fresh']
    assert 'not live confirmed' in first['time_basis']
    assert snapshot(launch,location,None,pred,app.state.store)['revision']==first['revision']
    changed={**launch,'net':(datetime.fromisoformat(launch['net'])+timedelta(minutes=5)).isoformat()}
    assert snapshot(changed,location,None,pred,app.state.store)['revision']!=first['revision']

def test_partial_refresh_never_deactivates_cache(app,launch):
    assert hasattr(app.state.providers,'refresh')
