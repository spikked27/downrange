"""A revision changes only when model input/status changes, not on each poll."""
import hashlib,json,time
from .geometry import utc

def snapshot(launch,observer,track,prediction,store,now=None):
    now=time.time() if now is None else now
    acq=launch.get('acquisition') or {}
    model={'launch':{k:launch.get(k) for k in ('id','net','pad','mission','orbit','vehicle','time_precise')},
           'observer':observer,'track':track,'directions':acq.get('directions',[]) if not track else [],
           'profiles':acq.get('profiles',[]) if not track else [],
           'simulations':acq.get('tracks',[]) if not track else []}
    revision=hashlib.sha256(json.dumps([model,launch.get('status'),launch.get('feed_active'),
        launch.get('schedule_verification_pending')],sort_keys=True,default=str).encode()).hexdigest()
    feed=store.meta('feed',{})
    actual=[e.get('observed_at') for e in acq.get('evidence',[]) if isinstance(e,dict) and isinstance(e.get('observed_at'),(int,float))]
    seen=launch.get('feed_seen')
    return {'revision':revision,'response_at':now,
            'schedule_fetched_at':seen,'schedule_fresh':bool(isinstance(seen,(int,float)) and 0<=now-seen<1800),
            'schedule_next_check':feed.get('next_attempt'),
            'prediction_calculated_at':prediction.get('calculated_at'),
            'source_fetched_at':min(actual) if actual else None,
            'source_last_attempt':acq.get('checked'),
            'source_next_check':acq.get('checked',0)+300 if acq.get('checked') else None,
            'verification_pending':bool(launch.get('schedule_verification_pending')),
            'nominal_liftoff':launch['net'],
            'time_basis':'Nominal, not live confirmed liftoff'}
