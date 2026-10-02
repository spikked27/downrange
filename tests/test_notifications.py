import json,time
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import pytest
from app.models import Preferences
from app.notifications import quiet,eligible,ensure_vapid
from app.geometry import screen

@pytest.fixture
def context(app,loaded_launch,location):
    now=float(int(time.time()))
    loaded_launch['net']=datetime.fromtimestamp(now+15*60,timezone.utc).isoformat()
    store=app.state.store
    store.execute('UPDATE launches SET data=? WHERE id=?',(json.dumps(loaded_launch),loaded_launch['id']))
    store.execute('INSERT INTO locations VALUES(?,?,?)',('loc',1,json.dumps(location)))
    store.execute('INSERT INTO subscriptions VALUES(?,?,?)',('subscription',1,json.dumps({'endpoint':'https://fcm.googleapis.com/fcm/send/unit-test','keys':{'p256dh':'synthetic-not-used-for-encryption','auth':'synthetic'}})))
    store.execute('UPDATE users SET prefs=? WHERE id=1',(Preferences(enabled=True,include_candidates=True,lead_minutes=[15]).model_dump_json(),))
    store.set_meta('feed',{'last_success':now})
    return store,app.state.notifier,loaded_launch,location,now

def test_due_reminder_deduplicates_and_delivers(context):
    store,n,l,loc,now=context
    n.plan(now);n.plan(now+10)
    assert len(store.rows('SELECT * FROM deliveries'))==1
    sent=[];n.deliver(now,sender=lambda sub,payload,ttl:sent.append((payload,ttl)))
    assert len(sent)==1 and 'Uncertain' in sent[0][0]['title']
    assert 0<sent[0][1]<=120
    n.plan(now+20);n.deliver(now+20,sender=lambda *args:sent.append(args))
    assert len(sent)==1

@pytest.mark.parametrize('change',['stale','imprecise','hold','disabled','no_candidates','loc_disabled'])
def test_ineligible_never_queues(context,change):
    store,n,l,loc,now=context
    if change=='stale': store.set_meta('feed',{'last_success':now-1801})
    if change=='imprecise':l['time_precise']=False
    if change=='hold':l['status']='Hold'
    if change=='disabled':store.execute("UPDATE users SET prefs='{}' WHERE id=1")
    if change=='no_candidates':store.execute('UPDATE users SET prefs=? WHERE id=1',(Preferences(enabled=True).model_dump_json(),))
    if change=='loc_disabled':loc['alerts']=False;store.execute('UPDATE locations SET data=? WHERE id=?',(json.dumps(loc),'loc'))
    store.execute('UPDATE launches SET data=? WHERE id=?',(json.dumps(l),l['id']))
    n.plan(now)
    assert store.rows('SELECT * FROM deliveries')==[]

def test_delayed_launch_cancels_pending(context):
    store,n,l,loc,now=context;n.plan(now)
    l['net']=datetime.fromtimestamp(now+7200,timezone.utc).isoformat()
    store.execute('UPDATE launches SET data=? WHERE id=?',(json.dumps(l),l['id']))
    n.plan(now+1)
    assert store.one('SELECT status FROM deliveries')['status']=='cancelled'

def test_delay_after_delivered_reminder_sends_change_once(context):
    store,n,l,loc,now=context;n.plan(now);n.deliver(now,sender=lambda *args:None)
    l['net']=datetime.fromtimestamp(now+7200,timezone.utc).isoformat()
    store.execute('UPDATE launches SET data=? WHERE id=?',(json.dumps(l),l['id']))
    n.plan(now+1);n.plan(now+2)
    assert len(store.rows("SELECT * FROM deliveries WHERE kind='change'"))==1
    store.set_meta('feed',{'last_success':now-2000});n.plan(now+3)
    assert store.one("SELECT status FROM deliveries WHERE kind='change'")['status']=='cancelled'

def test_stale_cancels_already_queued_reminder(context):
    store,n,l,loc,now=context;n.plan(now)
    store.set_meta('feed',{'last_success':now-2000});n.plan(now+1)
    assert store.one('SELECT status FROM deliveries')['status']=='cancelled'

def test_expired_message_not_delivered(context):
    store,n,l,loc,now=context;n.plan(now);n.plan(now+121)
    sent=[];n.deliver(now+121,sender=lambda *args:sent.append(args))
    assert not sent
    assert store.one('SELECT status FROM deliveries')['status']=='expired'

def test_push_failure_retry_and_redaction(context):
    store,n,l,loc,now=context;n.plan(now)
    def broken(*args):raise RuntimeError('secret endpoint should not be persisted')
    n.deliver(now,sender=broken)
    row=store.one('SELECT * FROM deliveries')
    assert row['attempts']==1 and row['status']=='pending' and 'secret' not in row['error']
    n.deliver(now+31,sender=lambda *args:None)
    assert store.one('SELECT status FROM deliveries')['status']=='sent'

def test_gone_push_endpoint_removed(context):
    store,n,l,loc,now=context;n.plan(now)
    class Gone(Exception):response=SimpleNamespace(status_code=410)
    def gone(*args):raise Gone()
    n.deliver(now,sender=gone)
    assert not store.rows('SELECT * FROM subscriptions')
    assert store.one('SELECT status FROM deliveries')['status']=='failed'

def test_quiet_hours_cross_midnight_in_location_timezone(location):
    prefs=Preferences(quiet_start=23,quiet_end=6)
    night=datetime(2026,10,2,4,0,tzinfo=timezone.utc).timestamp()
    morning=datetime(2026,10,2,12,0,tzinfo=timezone.utc).timestamp()
    assert quiet(night,location,prefs)
    assert not quiet(morning,location,prefs)

def test_estimated_trajectory_requires_opt_in(launch,location):
    pred={'candidate':True,'mode':'trajectory','confidence':'estimated','ordinary_windows':[{'start':'x'}],'jellyfish_windows':[]}
    assert not eligible(launch,location,pred,Preferences(enabled=True))
    assert eligible(launch,location,pred,Preferences(enabled=True,include_estimates=True))
    assert not eligible(launch,location,pred,Preferences(enabled=True,include_estimates=True,jellyfish_only=True))

def test_vapid_survives_restart_with_private_permissions(settings):
    path,pub=ensure_vapid(settings.data_dir)
    path2,pub2=ensure_vapid(settings.data_dir)
    assert pub==pub2 and path==path2
    assert path.stat().st_mode&0o777==0o600

def test_schedule_change_preference_cancels_retry(context):
    store,n,l,loc,now=context
    subs=store.rows('SELECT id FROM subscriptions')
    n.queue(1,subs,'change-test',l['id'],'loc',l['net'],'change',{},now,now+600)
    store.execute('UPDATE users SET prefs=? WHERE id=1',(Preferences(enabled=True,schedule_changes=False).model_dump_json(),))
    n.plan(now)
    assert store.one("SELECT status FROM deliveries WHERE kind='change'")['status']=='cancelled'
