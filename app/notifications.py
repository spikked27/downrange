from __future__ import annotations
import base64, hashlib, json, os, time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from .geometry import utc
from .prediction_cache import predict
from .models import Preferences
from .security import validate_push_endpoint


def ensure_vapid(data_dir):
    path=data_dir/"vapid-private.pem"
    if not path.exists():
        key=ec.generate_private_key(ec.SECP256R1())
        content=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as f: f.write(content)
    path.chmod(0o600)
    key=serialization.load_pem_private_key(path.read_bytes(),password=None)
    raw=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    return path,base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def quiet(now,loc,prefs):
    start,end=prefs.quiet_start,prefs.quiet_end
    if start is None or start==end: return False
    hour=datetime.fromtimestamp(now,timezone.utc).astimezone(ZoneInfo(loc["timezone"])).hour
    return start<=hour<end if start<end else hour>=start or hour<end


def eligible(launch,loc,pred,prefs,now=None):
    now=time.time() if now is None else now
    if (launch.get("feed_seen") is not None and now-launch["feed_seen"]>1800) or not launch.get("feed_active") or launch.get("demo") or not launch.get("time_precise") or not loc.get("alerts"): return False
    if launch.get("status","").lower() not in {"go","tbc"}: return False
    if not pred["candidate"]: return False
    if pred.get("low_information") and not prefs.include_candidates: return False
    if pred["mode"]=="screening": return prefs.include_candidates and not prefs.jellyfish_only
    if pred["confidence"]=="estimated" and not prefs.include_estimates: return False
    return bool(pred["jellyfish_windows"]) if prefs.jellyfish_only else bool(pred["ordinary_windows"] or pred["jellyfish_windows"])

class Notifier:
    def __init__(self,store,settings):
        self.store=store; self.settings=settings
        self.private_key,self.public_key=ensure_vapid(settings.data_dir)
    def queue(self,user_id,subs,event,launch_id,loc_id,net,kind,payload,now,expires):
        for sub in subs:
            key=hashlib.sha256(f'{event}|{sub["id"]}'.encode()).hexdigest()
            self.store.execute("INSERT INTO deliveries(key,user_id,subscription_id,launch_id,location_id,net,kind,payload,next_try,expires) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET status='pending',payload=excluded.payload,next_try=excluded.next_try,expires=excluded.expires,error=NULL WHERE deliveries.status IN ('cancelled','expired') AND deliveries.attempts<3",
                               (key,user_id,sub["id"],launch_id,loc_id,net,kind,json.dumps(payload),now,expires))
    def plan(self,now=None):
        now=time.time() if now is None else now
        launches={x["id"]:x for x in self.store.launches()}
        # Outbox items never survive an obsolete schedule, disabled preference,
        # changed location, or loss of current eligibility.
        self.store.execute("UPDATE deliveries SET status='expired' WHERE status='pending' AND expires<=?",(now,))
        self.store.execute("DELETE FROM sessions WHERE expires<?",(now,))
        self.store.execute("DELETE FROM deliveries WHERE expires<?",(now-30*86400,))
        feed=self.store.meta("feed",{})
        fresh=not self.settings.demo_mode and 0<=now-feed.get("last_success",0)<1800
        for user in self.store.rows("SELECT id,prefs FROM users"):
            prefs=Preferences.model_validate_json(user["prefs"])
            subs=self.store.rows("SELECT id,data FROM subscriptions WHERE user_id=?",(user["id"],))
            locations={x["id"]:x for x in self.store.locations(user["id"])}
            cache={}
            def current(lid,locid):
                key=(lid,locid)
                if key not in cache:
                    launch=launches.get(lid); loc=locations.get(locid)
                    cache[key]=predict(launch,loc,self.store.track(lid)) if launch and loc else None
                return cache[key]
            for item in self.store.rows("SELECT * FROM deliveries WHERE user_id=? AND status='pending' AND kind!='test'",(user["id"],)):
                launch=launches.get(item["launch_id"]); loc=locations.get(item["location_id"])
                pred=current(item["launch_id"],item["location_id"])
                valid=(prefs.enabled and fresh and launch and loc and loc["alerts"] and launch["net"]==item["net"] and not quiet(now,loc,prefs))
                if item["kind"]=="reminder": valid=valid and eligible(launch,loc,pred,prefs,now)
                elif item["kind"]=="change": valid=valid and prefs.schedule_changes
                if not valid: self.store.execute("UPDATE deliveries SET status='cancelled' WHERE key=?",(item["key"],))
            if not prefs.enabled or not fresh or not subs: continue
            for loc in locations.values():
                if not loc["alerts"] or quiet(now,loc,prefs): continue
                for launch in launches.values():
                    net=utc(launch["net"]).timestamp()
                    if prefs.schedule_changes:
                        sent=self.store.one("SELECT net FROM deliveries WHERE user_id=? AND launch_id=? AND location_id=? AND kind='reminder' AND status='sent' ORDER BY next_try DESC LIMIT 1",(user["id"],launch["id"],loc["id"]))
                        changed=sent and (sent["net"]!=launch["net"] or launch["status"].lower() not in {"go","tbc"} or not launch.get("feed_active"))
                        if changed:
                            state=f'{launch["net"]}|{launch["status"]}|{launch.get("feed_active")}'
                            when=utc(launch["net"]).astimezone(ZoneInfo(loc["timezone"])).strftime("%b %d %H:%M %Z")
                            body=f'{launch["name"]}: latest schedule {when}; status {launch["status_name"]}. Previous viewing reminder is obsolete. Recheck forecast.'
                            self.queue(user["id"],subs,f'change|{launch["id"]}|{loc["id"]}|{state}',launch["id"],loc["id"],launch["net"],"change",{"title":"Launch schedule changed","body":body[:800],"tag":f'change-{launch["id"]}',"url":"/"},now,now+600)
                    if net<now-600 or net>now+2*86400: continue
                    pred=current(launch["id"],loc["id"])
                    if not eligible(launch,loc,pred,prefs,now): continue
                    windows=pred["jellyfish_windows"] if prefs.jellyfish_only else sorted(pred["ordinary_windows"]+pred["jellyfish_windows"],key=lambda w:w["start"])
                    first=utc(windows[0]["start"]).timestamp() if windows else net
                    leads=[lead for lead in prefs.lead_minutes if 0<=now-(first-lead*60)<120 and first>now]
                    if not leads: continue
                    lead=min(leads)
                    if pred["mode"]=="screening":
                        title="Uncertain launch candidate"
                        body=f'{loc["name"]}: {launch["name"]}. Liftoff is scheduled in ~{round((net-now)/60)} min. NO trajectory: visibility and viewing direction are unknown.'
                    else:
                        title=("Experimental viewing estimate" if pred["confidence"]=="estimated" else "Possible launch viewing window")
                        body=f'{loc["name"]}: {launch["name"]}. Modeled opportunity in ~{round((first-now)/60)} min. Modeled peak up to {pred["max_elevation_deg"]}° {pred["direction"]}. Jellyfish: {pred["jellyfish"]}. Not a visibility guarantee.'
                    event=f'reminder|{launch["id"]}|{launch["net"]}|{loc["id"]}|{lead}'
                    self.queue(user["id"],subs,event,launch["id"],loc["id"],launch["net"],"reminder",{"title":title,"body":body[:800],"tag":event,"url":"/?"+urlencode({"launch":launch["id"],"location":loc["id"]})},now,min(now+120,first))
    def send_one(self,subscription,payload,ttl):
        from pywebpush import webpush
        validate_push_endpoint(subscription["endpoint"])
        import requests
        class NoRedirectSession(requests.Session):
            def request(self,*args,**kwargs):
                kwargs["allow_redirects"]=False
                return super().request(*args,**kwargs)
        with NoRedirectSession() as session:
            response=webpush(subscription_info=subscription,data=json.dumps(payload),
                vapid_private_key=str(self.private_key),vapid_claims={"sub":self.settings.push_subject},
                ttl=ttl,timeout=10,requests_session=session)
        if not 200<=response.status_code<300: raise RuntimeError(f"Push HTTP {response.status_code}")
    def deliver(self,now=None,sender=None):
        now=time.time() if now is None else now
        if self.settings.demo_mode: return
        if not sender and not self.settings.push_subject: return
        sender=sender or self.send_one
        for item in self.store.rows("SELECT * FROM deliveries WHERE status='pending' AND next_try<=? AND expires>? ORDER BY next_try LIMIT 20",(now,now)):
            sub=self.store.one("SELECT data FROM subscriptions WHERE id=? AND user_id=?",(item["subscription_id"],item["user_id"]))
            if not sub:
                self.store.execute("UPDATE deliveries SET status='cancelled' WHERE key=?",(item["key"],)); continue
            current = self.store.one("SELECT status FROM deliveries WHERE key=?", (item["key"],))
            if not current or current["status"] != "pending": continue
            try:
                sender(json.loads(sub["data"]),json.loads(item["payload"]),max(1,int(item["expires"]-now)))
                self.store.execute("UPDATE deliveries SET status='sent',error=NULL,next_try=? WHERE key=?",(now,item["key"]))
            except Exception as exc:
                response=getattr(exc,"response",None)
                status=getattr(response,"status_code",None)
                if status in (404,410):
                    self.store.execute("DELETE FROM subscriptions WHERE id=?",(item["subscription_id"],))
                attempts=item["attempts"]+1
                state="failed" if status in (400,401,403,404,410) or attempts>=3 else "pending"
                self.store.execute("UPDATE deliveries SET attempts=?,status=?,next_try=?,error=? WHERE key=?",(attempts,state,now+30*attempts,f'Push failure: {type(exc).__name__}'+(f' HTTP {status}' if status else ''),item["key"]))
