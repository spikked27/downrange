from __future__ import annotations
import asyncio, json, math, time, hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
import httpx
from .geometry import utc

LL2_URL="https://ll.thespacedevs.com/2.3.0/launches/upcoming/"
HEADERS={"User-Agent":"Downrange/0.3.0 (+self-hosted launch-visibility research)","Accept":"application/json"}

def coordinate(value,low,high):
    try:
        v=float(value)
        return v if math.isfinite(v) and low<=v<=high else None
    except (TypeError,ValueError): return None

def normalize(raw):
    net=utc(raw["net"]).isoformat()
    pad=raw.get("pad") or {}; site=pad.get("location") or {}
    precision=raw.get("net_precision") or {}
    precision_name=str(precision.get("name","")).lower()
    precise=precision_name in {"second","minute","exact","seconds","minutes"}
    status=raw.get("status") or {}
    mission=raw.get("mission") or {}
    config=(raw.get("rocket") or {}).get("configuration") or {}
    links=[]
    for entry in list(mission.get("info_urls") or [])+list(raw.get("info_urls") or []):
        url=entry.get("url") if isinstance(entry,dict) else entry
        if isinstance(url,str) and url.startswith("https://"):links.append(url)
    return {"id":str(raw["id"]),"name":str(raw.get("name","Unnamed launch"))[:300],"net":net,
            "status":str(status.get("abbrev",status.get("name","Unknown"))),"status_name":status.get("name","Unknown"),
            "status_description":str(status.get("description",""))[:1000],
            "time_precise":precise,"precision":precision.get("name","Unspecified"),
            "window_start":raw.get("window_start"),"window_end":raw.get("window_end"),
            "provider":(raw.get("launch_service_provider") or {}).get("name","Unknown provider"),
            "vehicle":config.get("full_name",config.get("name","Unknown vehicle")),
            "mission":str(mission.get("description","") or "")[:3000],
            "mission_name":str(mission.get("name") or raw.get("name","").split("|")[-1]).strip()[:300],
            "mission_type":str(mission.get("type","") or ""),"info_urls":links[:15],
            "suborbital":bool("suborbital" in str((mission.get("orbit") or {}).get("name","")).lower()),
            "orbit":(mission.get("orbit") or {}).get("name","Unknown orbit"),
            "pad":{"name":pad.get("name","Unknown pad"),"site":site.get("name",""),
                   "latitude":coordinate(pad.get("latitude"),-90,90),
                   "longitude":coordinate(pad.get("longitude"),-180,180)},
            "provider_updated":raw.get("last_updated"),"feed_active":True,"demo":False}

class Providers:
    def __init__(self,store,settings):
        self.store=store; self.settings=settings; self.refresh_lock=asyncio.Lock(); self.weather_lock=asyncio.Lock()
    async def refresh(self):
        if self.settings.demo_mode: return self.store.meta("feed",{})
        async with self.refresh_lock:
            now=time.time(); meta=self.store.meta("feed",{})
            if now < meta.get("next_attempt",0): return meta
            meta.update(last_attempt=now,next_attempt=now+self.settings.poll_seconds)
            self.store.set_meta("feed",meta)
            headers=dict(HEADERS)
            if self.settings.ll2_key: headers["Authorization"]="Token "+self.settings.ll2_key
            launches=[];skipped=0;pages=0;next_url=LL2_URL;complete=False;data={}
            requests_at=[t for t in self.store.meta("ll2_requests",[]) if now-t<3600]
            try:
                async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
                    visited=set()
                    while next_url:
                        if len(requests_at)>=14:
                            meta["next_attempt"]=max(meta["next_attempt"],requests_at[0]+3601)
                            raise ValueError("Local launch-provider quota budget reached")
                        p=urlsplit(next_url)
                        if p.scheme!="https" or p.hostname!="ll.thespacedevs.com" or p.port not in (None,443) or p.username or p.password or p.path!="/2.3.0/launches/upcoming/" or next_url in visited:
                            raise ValueError("Invalid launch pagination URL")
                        visited.add(next_url)
                        requests_at.append(time.time());self.store.set_meta("ll2_requests",requests_at)
                        params={"mode":"normal","limit":100,"ordering":"net","format":"json",
                                "net__gte":datetime.fromtimestamp(now-86400,timezone.utc).isoformat(),
                                "net__lte":datetime.fromtimestamp(now+90*86400,timezone.utc).isoformat()} if pages==0 else None
                        r=await client.get(next_url,params=params,headers=headers)
                        if r.status_code==429:
                            retry=r.headers.get("retry-after","");wait=int(retry) if retry.isdigit() else 3600
                            meta["next_attempt"]=now+max(self.settings.poll_seconds,min(wait,86400))
                        r.raise_for_status();data=r.json()
                        if not isinstance(data,dict) or not isinstance(data.get("results"),list):raise ValueError("Invalid launch feed format")
                        page_launches=[]
                        for item in data["results"]:
                            try:page_launches.append(normalize(item))
                            except (KeyError,ValueError,TypeError):skipped+=1
                        if data["results"] and not page_launches:raise ValueError("No launch records could be parsed")
                        for launch in page_launches:launch["feed_seen"]=now
                        launches.extend(page_launches);pages+=1;next_url=data.get("next")
                        if pages>=10 and next_url:raise ValueError("Snapshot exceeds this cycle budget; coverage marked partial")
                    complete=True
            except Exception as exc:
                meta["error"]=f"Launch feed incomplete/unavailable ({type(exc).__name__}); cached data retained."
            # Partial responses may add fresh records but cannot deactivate missing records.
            if complete or launches:
                with self.store.connect() as c:
                    if complete:
                        for row in c.execute("SELECT id,data FROM launches").fetchall():
                            old=json.loads(row["data"]);old["feed_active"]=False
                            c.execute("UPDATE launches SET data=? WHERE id=?",(json.dumps(old),row["id"]))
                    for launch in launches:
                        c.execute("INSERT INTO launches VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,seen=excluded.seen",
                                  (launch["id"],json.dumps(launch),now))
                    c.execute("DELETE FROM launches WHERE seen<?",(now-7*86400,))
                meta.update(last_success=now,returned=len(launches),available=data.get("count"),
                            pages=pages,truncated=not complete,skipped=skipped,coverage_days=90)
                if complete:meta.update(error=None,last_complete=now)
                meta["next_attempt"]=max(meta["next_attempt"],now+max(self.settings.poll_seconds,pages*300))
            self.store.set_meta("feed",meta)
            return meta
    async def geocode(self,q):
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            r=await client.get("https://geocoding-api.open-meteo.com/v1/search",params={"name":q,"count":8,"language":"en","format":"json"},headers=HEADERS)
            r.raise_for_status(); results=r.json().get("results",[])
        return [{"name":p["name"],"region":", ".join(str(p[k]) for k in ("admin1","country") if p.get(k)),
                 "latitude":p["latitude"],"longitude":p["longitude"],"elevation_m":p.get("elevation",0),"timezone":p.get("timezone","UTC")} for p in results]
    async def weather(self,loc,net):
        target=utc(net).timestamp(); now=time.time()
        if target < now-3600 or target>now+15*86400:
            return {"available":False,"reason":"Outside the forecast range"}
        key="weather:"+hashlib.sha256(f'{loc["latitude"]:.3f},{loc["longitude"]:.3f}'.encode()).hexdigest()
        async with self.weather_lock:
            cached=self.store.meta(key,{})
            if now-cached.get("fetched",0)>3600 and now-cached.get("attempted",0)>300:
                cached["attempted"]=now
                try:
                    async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
                        r=await client.get("https://api.open-meteo.com/v1/forecast",headers=HEADERS,params={
                            "latitude":round(loc["latitude"],3),"longitude":round(loc["longitude"],3),
                            "hourly":"cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,visibility",
                            "forecast_days":16,"timezone":"UTC","timeformat":"unixtime"})
                        r.raise_for_status(); data=r.json()
                    cached.update(fetched=now,data=data.get("hourly",{}),error=None)
                except Exception as exc: cached["error"]=f"Forecast unavailable ({type(exc).__name__})"
                self.store.set_meta(key,cached)
        h=cached.get("data",{}); times=h.get("time",[])
        if not times: return {"available":False,"reason":cached.get("error","No weather data")}
        i=min(range(len(times)),key=lambda n:abs(times[n]-target))
        if abs(times[i]-target)>3600: return {"available":False,"reason":"No matching forecast hour"}
        result={"available":True,"fetched":cached["fetched"],"stale":now-cached["fetched"]>7200,
                "forecast_time":times[i],"scope":"Observer's forecast grid cell, NOT the full line of sight",
                "source":"Open-Meteo","error":cached.get("error")}
        for k in ("cloud_cover","cloud_cover_low","cloud_cover_mid","cloud_cover_high","visibility"):
            v=h.get(k,[]); result[k]=v[i] if i<len(v) else None
        return result
