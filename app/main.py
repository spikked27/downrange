from __future__ import annotations
import asyncio, base64, hashlib, hmac, importlib.util, json, logging, secrets, sqlite3, time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import __version__
from .config import Settings
from .models import Credentials, PasswordChange, Location, Preferences, Trajectory, Scenario, PushSubscription
from .store import Store
from .security import Limiter, password_hash, verify_password, token_hash, validate_push_endpoint
from .geometry import predict, utc, illustrative_track
from .providers import Providers
from .notifications import Notifier
from .acquisition import Acquisition
from .viewing import plan as viewing_plan
from .upgrade import protect_existing_data, record_version

log=logging.getLogger("downrange")
STATIC=Path(__file__).parent/"static"

@lru_cache(maxsize=256)
def cached_prediction(launch_json,loc_json,track_json):
    launch, observer = json.loads(launch_json), json.loads(loc_json)
    prediction = predict(launch, observer, json.loads(track_json) if track_json else None)
    return {**prediction, 'viewing_plan': viewing_plan(launch, prediction, observer)}

def calculate(launch,loc,track):
    return cached_prediction(json.dumps(launch,sort_keys=True),json.dumps(loc,sort_keys=True),json.dumps(track,sort_keys=True) if track else "")

class BodyLimit:
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope["type"]!="http" or scope["method"] not in {"POST","PUT","PATCH"}:
            return await self.app(scope,receive,send)
        chunks=[]; size=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect": return
            chunk=message.get("body",b""); size+=len(chunk)
            if size>1024*1024:
                return await JSONResponse({"detail":"Request exceeds 1 MiB limit"},status_code=413)(scope,receive,send)
            chunks.append(chunk)
            if not message.get("more_body",False): break
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True; return {"type":"http.request","body":b"".join(chunks),"more_body":False}
            return await receive()
        return await self.app(scope,replay,send)


def seed_demo(store):
    now=datetime.now(timezone.utc)
    loc=Location(name="Demo viewing location",latitude=40.7,longitude=-73.35).model_dump()
    store.execute("INSERT OR IGNORE INTO locations VALUES(?,?,?)",("demo-location",1,json.dumps(loc)))
    for i,title in enumerate(["DEMO · Coastal research launch","DEMO · Distant orbital mission","DEMO · Night ascent scenario"]):
        launch={"id":f"demo-{i}","name":title,"net":(now+timedelta(hours=1+i*5)).isoformat(),
            "status":"Go","status_name":"SIMULATED","status_description":"Fictional UI test, not a real launch", "time_precise":True,"precision":"SIMULATED",
            "window_start":None,"window_end":None,"provider":"Fictional launch provider","vehicle":"Illustrative vehicle","mission":"Synthetic data to test the interface and geometry. Never used for real launch notifications.","orbit":"Illustrative low Earth orbit",
            "pad":{"name":"Demo pad","site":"Synthetic scenario","latitude":37.8 if i!=1 else 28.5,"longitude":-75.5 if i!=1 else -80.6},
            "provider_updated":None,"feed_active":True,"demo":True}
        store.execute("INSERT INTO launches VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,seen=excluded.seen",(launch["id"],json.dumps(launch),time.time()))
        if i!=1:
            track=illustrative_track(launch,40,"SYNTHETIC DEMO — not actual telemetry or a published trajectory")
            store.execute("INSERT OR REPLACE INTO tracks VALUES(?,?)",(launch["id"],json.dumps(track)))
    store.set_meta("feed",{"last_success":time.time(),"returned":3,"available":3,"truncated":False,"demo":True})


def create_app(settings=None):
    settings=settings or Settings()
    settings.data_dir.mkdir(parents=True,exist_ok=True)
    protect_existing_data(settings.data_dir)
    store=Store(settings.data_dir/"downrange.sqlite3")
    mode="demo" if settings.demo_mode else "live"
    previous=store.meta("installation_mode")
    if previous and previous!=mode:
        raise RuntimeError("Do not mix DEMO and LIVE appdata. Use a separate DATA_DIR.")
    store.set_meta("installation_mode",mode)
    if not store.one("SELECT id FROM users WHERE admin=1"):
        password=settings.admin_password or secrets.token_urlsafe(18)
        store.execute("INSERT INTO users(username,password,admin) VALUES(?,?,1)",("admin",password_hash(password)))
        if not settings.admin_password:
            log.warning("FIRST RUN: username admin; generated password %s . Save it now; change it in Account. It will not be printed again.",password)
    notifier=Notifier(store,settings)
    providers=Providers(store,settings)
    acquisition=Acquisition(store,settings)
    limiter=Limiter()
    dummy_hash=password_hash(secrets.token_urlsafe(20))
    if settings.demo_mode: seed_demo(store)
    record_version(store)

    async def loop():
        while True:
            try:
                await providers.refresh()
                await asyncio.to_thread(notifier.plan)
                await asyncio.to_thread(notifier.deliver)
                store.set_meta("worker_heartbeat",time.time())
            except asyncio.CancelledError: raise
            except Exception as exc: log.error("Worker iteration failed: %s",type(exc).__name__)
            await asyncio.sleep(30)
    source_wakeup = asyncio.Event()
    async def sources_loop():
        # Separate task: source network delays must not delay scheduled push.
        await asyncio.sleep(3)
        while True:
            try:
                await acquisition.refresh()
            except asyncio.CancelledError: raise
            except Exception as exc:
                log.error("Source acquisition failed: %s",type(exc).__name__)
                status = store.meta("acquisition_status",{})
                store.set_meta("acquisition_status",{**status,"running":False,"error":type(exc).__name__})
            try:
                await asyncio.wait_for(source_wakeup.wait(), timeout=300 if store.launches(hydrate=False) else 10)
            except asyncio.TimeoutError:
                pass
            source_wakeup.clear()
    @asynccontextmanager
    async def lifespan(app):
        lock_file=None
        if settings.worker_enabled:
            import fcntl
            lock_file=(settings.data_dir/"worker.lock").open("a")
            try: fcntl.flock(lock_file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                lock_file.close()
                raise RuntimeError("Another Downrange worker uses this appdata. Run one container / one worker.")
        task=asyncio.create_task(loop()) if settings.worker_enabled else None
        source_task=asyncio.create_task(sources_loop()) if settings.worker_enabled and settings.sources_enabled else None
        try: yield
        finally:
            if source_task:
                source_task.cancel()
                try: await source_task
                except asyncio.CancelledError: pass
            if task:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
            if lock_file: lock_file.close()
    app=FastAPI(title="Downrange",version=__version__,lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store; app.state.notifier=notifier; app.state.providers=providers; app.state.settings=settings; app.state.acquisition=acquisition
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def security(request,call_next):
        if request.url.path.startswith("/api/") and request.method not in {"GET","HEAD","OPTIONS"}:
            expected=settings.public_url or str(request.base_url).rstrip("/")
            origin=request.headers.get("origin")
            if request.headers.get("x-downrange")!="1" or (origin and origin!=expected):
                message = ("Request blocked before password verification. Open Downrange at its configured HTTPS public address, "
                           "or clear PUBLIC_URL for a direct LAN HTTP test. The scheme, hostname and port must match. "
                           "Reload the page after changing the container setting.")
                if request.headers.get("x-downrange")!="1":
                    message="Required browser request header is missing. Reload Downrange; check that the reverse proxy preserves X-Downrange."
                return JSONResponse({"detail":message,"code":"origin_mismatch"},status_code=403)
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["X-Frame-Options"]="DENY"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        if request.url.path.startswith("/api/"): response.headers["Cache-Control"]="no-store"
        return response

    def auth(request: Request):
        token=request.cookies.get("downrange_session","")
        if not token or len(token)>200: raise HTTPException(401,"Sign in to continue")
        row=store.one("SELECT u.id,u.username,u.admin,u.prefs FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?",(token_hash(token),time.time()))
        if not row: raise HTTPException(401,"Session expired; sign in again")
        return row
    def admin(user=Depends(auth)):
        if not user["admin"]: raise HTTPException(403,"Administrator access required")
        return user
    def location_for(loc_id,user_id):
        row=store.one("SELECT data FROM locations WHERE id=? AND user_id=?",(loc_id,user_id))
        if not row: raise HTTPException(404,"Location not found")
        return {"id":loc_id,**json.loads(row["data"])}
    def launch_for(launch_id):
        row=store.one("SELECT data FROM launches WHERE id=?",(launch_id,))
        if not row: raise HTTPException(404,"Launch not in the current cache")
        return store.hydrate(json.loads(row["data"]))

    @app.get("/healthz")
    def health(): return {"ok":True,"version":__version__}
    @app.get("/api/config")
    def config():
        return {"version":__version__,"registration_open":bool(settings.invite_code),"demo_mode":settings.demo_mode,
                "public_url":settings.public_url,"sources_enabled":settings.sources_enabled,"push_configured":bool(settings.push_subject),"push_library":bool(importlib.util.find_spec("pywebpush")),"vapid_public_key":notifier.public_key}
    @app.post("/api/login")
    def login(body: Credentials,response: Response,request: Request):
        address=request.client.host if request.client else "unknown"
        limiter.check("login-ip:"+address,20,300)
        limiter.check("login-user:"+body.username.lower(),12,300)
        user=store.one("SELECT * FROM users WHERE username=?",(body.username.lower(),))
        valid=verify_password(body.password,user["password"] if user else dummy_hash)
        if not user or not valid: raise HTTPException(401,"Incorrect username or password")
        token=secrets.token_urlsafe(32)
        store.execute("INSERT INTO sessions VALUES(?,?,?)",(token_hash(token),user["id"],time.time()+30*86400))
        response.set_cookie("downrange_session",token,httponly=True,samesite="strict",secure=bool(settings.public_url),max_age=30*86400,path="/")
        return {"username":user["username"],"admin":bool(user["admin"])}
    @app.post("/api/register",status_code=201)
    def register(body:Credentials,request:Request):
        limiter.check("register:"+(request.client.host if request.client else "unknown"),5,3600)
        if not settings.invite_code or not hmac.compare_digest(body.invite_code,settings.invite_code):
            raise HTTPException(403,"Registration requires the server's invitation code")
        if store.one("SELECT COUNT(*) AS n FROM users")["n"]>=100: raise HTTPException(409,"This alpha supports up to 100 accounts")
        try: store.execute("INSERT INTO users(username,password) VALUES(?,?)",(body.username.lower(),password_hash(body.password)))
        except sqlite3.IntegrityError: raise HTTPException(409,"Username unavailable")
        return {"ok":True}
    @app.post("/api/logout")
    def logout(request:Request,response:Response,user=Depends(auth)):
        store.execute("DELETE FROM sessions WHERE token=?",(token_hash(request.cookies.get("downrange_session","")),))
        response.delete_cookie("downrange_session",path="/")
        return {"ok":True}
    @app.get("/api/me")
    def me(user=Depends(auth)): return {"username":user["username"],"admin":bool(user["admin"])}
    @app.post("/api/account/password")
    def change_password(body:PasswordChange,response:Response,user=Depends(auth)):
        limiter.check(f'password:{user["id"]}',5,300)
        old=store.one("SELECT password FROM users WHERE id=?",(user["id"],))["password"]
        if not verify_password(body.current_password,old): raise HTTPException(403,"Current password incorrect")
        with store.connect() as c:
            c.execute("UPDATE users SET password=? WHERE id=?",(password_hash(body.new_password),user["id"]))
            c.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
        response.delete_cookie("downrange_session",path="/")
        return {"ok":True,"message":"Password changed. Sign in again on each device."}
    @app.get("/api/locations")
    def locations(user=Depends(auth)): return store.locations(user["id"])
    @app.post("/api/locations",status_code=201)
    def add_location(body:Location,user=Depends(auth)):
        if len(store.locations(user["id"]))>=10: raise HTTPException(409,"Maximum 10 locations per account")
        lid=str(uuid4()); store.execute("INSERT INTO locations VALUES(?,?,?)",(lid,user["id"],body.model_dump_json()))
        return {"id":lid,**body.model_dump()}
    @app.put("/api/locations/{loc_id}")
    def edit_location(loc_id:str,body:Location,user=Depends(auth)):
        location_for(loc_id,user["id"])
        store.execute("UPDATE locations SET data=? WHERE id=? AND user_id=?",(body.model_dump_json(),loc_id,user["id"]))
        store.execute("UPDATE deliveries SET status='cancelled' WHERE user_id=? AND location_id=? AND status='pending'",(user["id"],loc_id))
        return {"id":loc_id,**body.model_dump()}
    @app.delete("/api/locations/{loc_id}")
    def remove_location(loc_id:str,user=Depends(auth)):
        location_for(loc_id,user["id"])
        with store.connect() as c:
            c.execute("DELETE FROM locations WHERE id=? AND user_id=?",(loc_id,user["id"]))
            c.execute("UPDATE deliveries SET status='cancelled' WHERE user_id=? AND location_id=? AND status='pending'",(user["id"],loc_id))
        return {"ok":True}
    @app.get("/api/geocode")
    async def geocode(q:str=Query(min_length=2,max_length=100),user=Depends(auth)):
        limiter.check(f'geocode:{user["id"]}',20,60)
        try: return await providers.geocode(q)
        except Exception: raise HTTPException(502,"Location search unavailable; enter coordinates manually")
    @app.get("/api/launches")
    def launches(location_id:str,days:int=Query(default=14,ge=1,le=90),user=Depends(auth)):
        loc=location_for(location_id,user["id"]); now=time.time(); results=[]
        for launch in store.launches():
            if not now-600<=utc(launch["net"]).timestamp()<=now+days*86400: continue
            if not launch.get("feed_active"): continue
            pred=calculate(launch,loc,store.track(launch["id"]))
            results.append({**{k:v for k,v in launch.items() if k!="acquisition"},"prediction":{k:v for k,v in pred.items() if k!="points"}})
        feed=store.meta("feed",{})
        return {"launches":results,"feed":feed,"stale":time.time()-feed.get("last_success",0)>1800,"location":loc,
                "sources": {"enabled": settings.sources_enabled, **store.meta("acquisition_status",{})}}
    @app.get("/api/launches/{launch_id}")
    def launch_detail(launch_id:str,location_id:str,user=Depends(auth)):
        launch=launch_for(launch_id); loc=location_for(location_id,user["id"])
        return {**{k:v for k,v in launch.items() if k!="acquisition"},"prediction":calculate(launch,loc,store.track(launch_id)),"location":loc}
    @app.get("/api/weather")
    async def weather(launch_id:str,location_id:str,user=Depends(auth)):
        limiter.check(f'weather:{user["id"]}',30,60)
        launch=launch_for(launch_id); loc=location_for(location_id,user["id"])
        if launch.get("demo"): return {"available":False,"reason":"Weather is not fetched for synthetic demo launches"}
        prediction = await asyncio.to_thread(calculate, launch, loc, store.track(launch_id))
        peak = prediction['viewing_plan'].get('peak')
        target = peak['time'] if peak else launch['net']
        forecast = await providers.weather(loc, target)
        return {**forecast, 'target_time': target, 'target_basis': 'modeled viewing peak' if peak else 'nominal liftoff'}
    @app.get("/api/preferences")
    def preferences(user=Depends(auth)): return Preferences.model_validate_json(user["prefs"])
    @app.put("/api/preferences")
    def set_preferences(body:Preferences,user=Depends(auth)):
        store.execute("UPDATE users SET prefs=? WHERE id=?",(body.model_dump_json(),user["id"]))
        store.execute("UPDATE deliveries SET status='cancelled' WHERE user_id=? AND status='pending' AND kind!='test'",(user["id"],))
        return body
    @app.post("/api/push/subscribe")
    def subscribe(body:PushSubscription,user=Depends(auth)):
        try:
            validate_push_endpoint(body.endpoint)
            key=base64.urlsafe_b64decode(body.keys.p256dh+"="*((-len(body.keys.p256dh))%4))
            authkey=base64.urlsafe_b64decode(body.keys.auth+"="*((-len(body.keys.auth))%4))
            if len(key)!=65 or key[0]!=4 or len(authkey)!=16: raise ValueError("Invalid push encryption keys")
            from cryptography.hazmat.primitives.asymmetric import ec
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),key)
        except ValueError as exc: raise HTTPException(422,str(exc))
        sid=token_hash(body.endpoint)
        old=store.one("SELECT user_id FROM subscriptions WHERE id=?",(sid,))
        if old and old["user_id"]!=user["id"]: raise HTTPException(409,"This browser is subscribed to another account; unsubscribe there first")
        if not old and len(store.rows("SELECT id FROM subscriptions WHERE user_id=?",(user["id"],)))>=10: raise HTTPException(409,"Maximum 10 notification devices per account")
        store.execute("INSERT INTO subscriptions VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",(sid,user["id"],body.model_dump_json(exclude_none=True)))
        return {"ok":True,"id":sid}
    @app.delete("/api/push/subscriptions/{sid}")
    def unsubscribe(sid:str,user=Depends(auth)):
        store.execute("DELETE FROM subscriptions WHERE id=? AND user_id=?",(sid,user["id"]))
        store.execute("UPDATE deliveries SET status='cancelled' WHERE subscription_id=? AND user_id=? AND status='pending'",(sid,user["id"]))
        return {"ok":True}
    @app.get("/api/push/status")
    def push_status(user=Depends(auth)):
        return {"devices":len(store.rows("SELECT id FROM subscriptions WHERE user_id=?",(user["id"],))),
                "deliveries":store.rows("SELECT kind,status,error,payload,next_try FROM deliveries WHERE user_id=? ORDER BY next_try DESC LIMIT 20",(user["id"],)),
                "worker_heartbeat":store.meta("worker_heartbeat"),"configured":bool(settings.push_subject)}
    @app.post("/api/push/test")
    def push_test(user=Depends(auth)):
        limiter.check(f'push-test:{user["id"]}',3,300)
        if settings.demo_mode: raise HTTPException(409,"Real push delivery is disabled in demo mode")
        if not settings.push_subject: raise HTTPException(409,"Set PUBLIC_URL or a valid VAPID_SUBJECT in the container template")
        if not importlib.util.find_spec("pywebpush"): raise HTTPException(503,"Web push library is not installed")
        subs=store.rows("SELECT id FROM subscriptions WHERE user_id=?",(user["id"],))
        if not subs: raise HTTPException(409,"Enable notifications on this device first")
        now=time.time(); notifier.queue(user["id"],subs,f'test|{uuid4()}',None,None,None,"test",{"title":"Downrange test","body":"Your server can send notifications to this device. This is not a launch alert.","tag":"downrange-test","url":"/"},now,now+120)
        return {"queued":len(subs),"message":"Test queued; delivery status appears below. Queueing is not delivery confirmation."}
    @app.post("/api/admin/refresh")
    async def refresh(user=Depends(admin)): return await providers.refresh()
    @app.post("/api/admin/sources/refresh")
    async def refresh_sources(user=Depends(admin)):
        limiter.check(f'sources-refresh:{user["id"]}',3,300)
        if not settings.sources_enabled or not settings.worker_enabled or settings.demo_mode:
            raise HTTPException(409,"Automatic sources are disabled in this installation")
        source_wakeup.set()
        return {"queued":True,"message":"Source check requested; existing cache and upstream rate limits still apply."}
    @app.get("/api/admin/status")
    def status(user=Depends(admin)):
        return {"feed":store.meta("feed",{}),"worker_heartbeat":store.meta("worker_heartbeat"),"accounts":store.one("SELECT COUNT(*) AS n FROM users")["n"],
                "tracks":store.one("SELECT COUNT(*) AS n FROM tracks")["n"],"demo_mode":settings.demo_mode,"acquisition":store.meta("acquisition_status",{}),"flightclub_configured":bool(settings.flightclub_key)}
    @app.get("/api/admin/trajectories/{launch_id}")
    def get_track(launch_id:str,user=Depends(admin)):
        launch_for(launch_id); return store.track(launch_id)
    @app.put("/api/admin/trajectories/{launch_id}")
    def set_track(launch_id:str,body:Trajectory,user=Depends(admin)):
        launch_for(launch_id)
        store.execute("INSERT OR REPLACE INTO tracks VALUES(?,?)",(launch_id,body.model_dump_json()))
        store.execute("UPDATE deliveries SET status='cancelled' WHERE launch_id=? AND status='pending' AND kind='reminder'",(launch_id,))
        return {"ok":True}
    @app.post("/api/admin/trajectories/{launch_id}/scenario")
    def scenario(launch_id:str,body:Scenario,user=Depends(admin)):
        try: track=illustrative_track(launch_for(launch_id),body.heading_deg,body.source)
        except ValueError as exc: raise HTTPException(422,str(exc))
        store.execute("INSERT OR REPLACE INTO tracks VALUES(?,?)",(launch_id,json.dumps(track)))
        store.execute("UPDATE deliveries SET status='cancelled' WHERE launch_id=? AND status='pending' AND kind='reminder'",(launch_id,))
        return {"ok":True,"trajectory":track}
    @app.delete("/api/admin/trajectories/{launch_id}")
    def delete_track(launch_id:str,user=Depends(admin)):
        store.execute("DELETE FROM tracks WHERE launch_id=?",(launch_id,))
        store.execute("UPDATE deliveries SET status='cancelled' WHERE launch_id=? AND status='pending' AND kind='reminder'",(launch_id,))
        return {"ok":True}
    @app.get("/")
    def index(): return FileResponse(STATIC/"index.html",headers={"Cache-Control":"no-cache"})
    @app.get("/sw.js")
    def sw(): return FileResponse(STATIC/"sw.js",media_type="application/javascript",headers={"Cache-Control":"no-cache","Service-Worker-Allowed":"/"})
    @app.get("/manifest.webmanifest")
    def manifest(): return FileResponse(STATIC/"manifest.webmanifest",media_type="application/manifest+json")
    app.mount("/static",StaticFiles(directory=STATIC),name="static")
    return app
