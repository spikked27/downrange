"""Geometric screening, NOT a calibrated probability-of-detection model.

WGS84 observer/target coordinates; approximate solar ephemeris; spherical Earth
shadow. No refraction, plume brightness/expansion, terrain, or light pollution.
See docs/MODEL.md for units, derivation, limitations, and references.
"""
from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from .models import Trajectory
from .horizon import viewing_limit

RAD = math.pi / 180
R = 6371.0088  # km, mean radius for surface distances
A = 6378.137
E2 = 6.69437999014e-3


def utc(value: str | datetime) -> datetime:
    d = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if d.tzinfo is None: raise ValueError("A timezone is required")
    return d.astimezone(timezone.utc)


def ecef(lat: float, lon: float, alt_km: float = 0) -> tuple[float, float, float]:
    p,l=lat*RAD,lon*RAD
    n=A/math.sqrt(1-E2*math.sin(p)**2)
    return ((n+alt_km)*math.cos(p)*math.cos(l), (n+alt_km)*math.cos(p)*math.sin(l),
            (n*(1-E2)+alt_km)*math.sin(p))


def look(observer: dict, target: tuple[float,float,float]) -> dict:
    p,l=observer["latitude"]*RAD,observer["longitude"]*RAD
    origin=ecef(observer["latitude"],observer["longitude"],observer.get("elevation_m",0)/1000)
    x,y,z=(v-o for v,o in zip(target,origin))
    east=-math.sin(l)*x+math.cos(l)*y
    north=-math.sin(p)*math.cos(l)*x-math.sin(p)*math.sin(l)*y+math.cos(p)*z
    up=math.cos(p)*math.cos(l)*x+math.cos(p)*math.sin(l)*y+math.sin(p)*z
    return {"azimuth": math.degrees(math.atan2(east,north))%360,
            "elevation": math.degrees(math.atan2(up,math.hypot(east,north))),
            "range_km": math.sqrt(x*x+y*y+z*z)}


def sun_vector(when: datetime) -> tuple[float,float,float]:
    # Low-order solar ephemeris in an Earth-fixed frame. UT≈TT is sufficient
    # for this alpha's minute-scale geometry; not for precision navigation.
    jd=utc(when).timestamp()/86400+2440587.5
    d=jd-2451545.0
    g=(357.529+0.98560028*d)*RAD
    lam=((280.459+0.98564736*d)+1.915*math.sin(g)+0.020*math.sin(2*g))*RAD
    eps=(23.439-0.00000036*d)*RAD
    ra=math.atan2(math.cos(eps)*math.sin(lam),math.cos(lam))
    dec=math.asin(math.sin(eps)*math.sin(lam))
    gmst=(280.46061837+360.98564736629*d)*RAD
    h=ra-gmst
    return math.cos(dec)*math.cos(h),math.cos(dec)*math.sin(h),math.sin(dec)


def solar_altitude(observer: dict, sun: tuple[float,float,float]) -> float:
    p,l=observer["latitude"]*RAD,observer["longitude"]*RAD
    up=(math.cos(p)*math.cos(l),math.cos(p)*math.sin(l),math.sin(p))
    return math.degrees(math.asin(max(-1,min(1,sum(a*b for a,b in zip(up,sun))))))


def is_sunlit(target: tuple[float,float,float], sun: tuple[float,float,float]) -> bool:
    dot=sum(a*b for a,b in zip(target,sun))
    # Parallel sunlight rays, conservative equatorial-radius spherical shadow.
    return dot >= 0 or sum(a*a for a in target)-dot*dot > A*A


def distance_km(lat1,lon1,lat2,lon2):
    p,q=(lat1*RAD,lat2*RAD); dp=q-p; dl=(lon2-lon1)*RAD
    a=math.sin(dp/2)**2+math.cos(p)*math.cos(q)*math.sin(dl/2)**2
    return R*2*math.asin(math.sqrt(max(0,min(1,a))))


def destination(lat,lon,bearing,km):
    p,l,b=lat*RAD,lon*RAD,bearing*RAD; d=km/R
    p2=math.asin(math.sin(p)*math.cos(d)+math.cos(p)*math.sin(d)*math.cos(b))
    l2=l+math.atan2(math.sin(b)*math.sin(d)*math.cos(p),math.cos(d)-math.sin(p)*math.sin(p2))
    return math.degrees(p2),((math.degrees(l2)+180)%360)-180


def compass(az):
    return ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][int((az+11.25)//22.5)%16]


def sample_track(track: dict, step: int=5):
    # State of each point applies until the next point. Dateline uses short arc.
    pts=track["points"]
    for a,b in zip(pts,pts[1:]):
        count=max(1,math.ceil((b["t_s"]-a["t_s"])/step))
        for i in range(count):
            f=i/count
            dl=(b["longitude"]-a["longitude"]+180)%360-180
            yield {"t_s":a["t_s"]+f*(b["t_s"]-a["t_s"]),
                   "latitude":a["latitude"]+f*(b["latitude"]-a["latitude"]),
                   "longitude":(a["longitude"]+f*dl+180)%360-180,
                   "altitude_km":a["altitude_km"]+f*(b["altitude_km"]-a["altitude_km"]),
                   "powered":a["powered"],"plume":a["plume"]}
    yield pts[-1]


def intervals(points: list[dict], field: str, net: datetime) -> list[dict]:
    out=[]; start=None; previous=None
    for p in points:
        if p[field] and start is None: start=p["t_s"]
        if not p[field] and start is not None:
            out.append({"start":(net+timedelta(seconds=start)).isoformat(),
                        "end":(net+timedelta(seconds=previous)).isoformat()}); start=None
        previous=p["t_s"]
    if start is not None:
        out.append({"start":(net+timedelta(seconds=start)).isoformat(),
                    "end":(net+timedelta(seconds=previous)).isoformat()})
    return out


def predict(launch: dict, observer: dict, track: dict | None) -> dict:
    if track is None:
        from .profiles import automatic_tracks, combine
        imported = (launch.get("acquisition") or {}).get("tracks") or []
        scenarios = imported or automatic_tracks(launch)
        if scenarios:
            return combine([predict(launch, observer, item) for item in scenarios], launch, sourced=bool(imported))
        return screen(launch,observer)
    net=utc(launch["net"]); out=[]
    for p in sample_track(track):
        when=net+timedelta(seconds=p["t_s"])
        xyz=ecef(p["latitude"],p["longitude"],p["altitude_km"])
        s=sun_vector(when); a=look(observer,xyz); sa=solar_altitude(observer,s)
        limit=viewing_limit(observer,a["azimuth"])
        above=a["elevation"]>=limit
        sunlit=is_sunlit(xyz,s)
        out.append({**p,**a,"sun_altitude":sa,"sunlit":sunlit,"above":above,"horizon_limit_deg":limit,
                    "ordinary":above and p["powered"] and sa<0,
                    "jellyfish":above and p["plume"] and sunlit and sa<=-4})
    visible=[p for p in out if p["above"]]
    ordinary=intervals(out,"ordinary",net); jelly=intervals(out,"jellyfish",net)
    all_intervals=intervals(out,"above",net)
    best=max(visible,key=lambda p:p["elevation"]) if visible else None
    target=sorted(ordinary+jelly,key=lambda w:w["start"]) or all_intervals
    warnings=["Geometric opportunity, not a brightness or naked-eye visibility guarantee.",
              "No terrain, atmospheric refraction, plume evolution, or light-pollution model.",
              "Timing follows the reported nominal liftoff, not a confirmed launch."]
    if track["kind"]=="estimated": warnings.insert(0,"EXPERIMENTAL: illustrative/estimated flight path, not confirmed mission trajectory.")
    if not launch.get("time_precise",False): warnings.insert(0,"Liftoff time is not precise; sky geometry is provisional and alerts are suppressed.")
    return {"mode":"trajectory","candidate":bool(visible),"confidence":track["kind"],
            "ordinary":"possible" if ordinary else ("no modeled powered-night interval" if visible else "below horizon in supplied track"),
            "jellyfish":"favorable geometry" if jelly else "not supported by supplied track",
            "max_elevation_deg":round(best["elevation"],1) if best else None,
            "direction":compass(best["azimuth"]) if best else None,
            "best_time":(net+timedelta(seconds=best["t_s"])).isoformat() if best else None,
            "first_visible":target[0]["start"] if target else None,
            "ordinary_windows":ordinary,"jellyfish_windows":jelly,"geometric_windows":all_intervals,
            "source":track["source"],"source_url":track.get("source_url",""),"notes":track.get("notes",""),
            "warnings":warnings,"points":[{k:round(v,4) if isinstance(v,float) else v for k,v in p.items()} for p in out]}


def screen(launch: dict, observer: dict) -> dict:
    """Deliberately permissive heading-agnostic envelope; NEVER a prediction.

    Assumed first-ascent search envelope: any direction, 0–3000 km downrange,
    up to 400 km altitude. These are screening settings, not vehicle telemetry.
    Outside the envelope means unknown/outside scope, NOT invisible.
    """
    pad=launch.get("pad") or {}
    result={"mode":"screening","candidate":False,"confidence":"unknown",
            "ordinary":"trajectory needed","jellyfish":"trajectory needed",
            "max_elevation_deg":None,"direction":None,"best_time":None,"first_visible":None,
            "ordinary_windows":[],"jellyfish_windows":[],"geometric_windows":[],"points":[],
            "source":"Broad ascent search envelope; no actual flight path", "source_url":"",
            "warnings":["No mission trajectory: this is a candidate search, not a visible-launch forecast.",
                        "Envelope assumes up to 3000 km downrange and 400 km altitude in any direction; actual flight may go away from you.",
                        "Outside this screen does not rule out later-stage burns or higher-altitude events."]}
    if pad.get("latitude") is None or pad.get("longitude") is None:
        result["warnings"].insert(0,"Launchpad coordinates unavailable."); return result
    d=distance_km(observer["latitude"],observer["longitude"],pad["latitude"],pad["longitude"])
    closest=max(0,d-3000)/R
    upper=math.degrees(math.atan2((R+400)*math.cos(closest)-R,(R+400)*math.sin(closest)))
    result.update(candidate=upper>=observer.get("min_elevation_deg",5),pad_distance_km=round(d),
                  sun_altitude_at_net=round(solar_altitude(observer,sun_vector(utc(launch["net"]))),1))
    return result


def illustrative_track(launch: dict, heading: float, source: str) -> dict:
    """User-requested what-if scenario. Never silently assigned to real missions."""
    pad=launch.get("pad") or {}
    if pad.get("latitude") is None or pad.get("longitude") is None: raise ValueError("Launchpad coordinates unavailable")
    # Hand-chosen smooth ascent for exercising geometry, NOT a Falcon 9 model.
    samples=[(0,0,0),(60,10,5),(120,40,45),(180,85,150),(240,120,350),
             (300,160,620),(360,190,950),(420,215,1350),(480,230,1800),(540,240,2300)]
    points=[]
    for t,h,d in samples:
        lat,lon=destination(pad["latitude"],pad["longitude"],heading,d)
        points.append(dict(t_s=t,latitude=lat,longitude=lon,altitude_km=h,powered=t<540,plume=t>60))
    return Trajectory(source=source,kind="estimated",notes=f"WHAT-IF ONLY. Initial true heading {heading:g}°. Hand-chosen generic ascent; no vehicle-specific validation.",points=points).model_dump()
