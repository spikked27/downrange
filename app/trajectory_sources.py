"""Historical ascent priors and documented Flight Club simulation conversion."""
from __future__ import annotations
import math
from .models import Trajectory
from .source_inputs import numeric, SourceUnavailable

HISTORY_INDEX='https://raw.githubusercontent.com/shahar603/Telemetry-Data/master/Laucnhes.json'
HISTORY_ATTRIBUTION='shahar603 / Telemetry-Data (SpaceX webcast extraction)'

def vehicle_family(vehicle):
    v=vehicle.casefold()
    if 'falcon heavy' in v:return 'falcon-heavy'
    if 'falcon 9' in v:return 'falcon-9'
    return None

def history_candidates(catalog,launch):
    family=vehicle_family(launch.get('vehicle',''))
    if family is None:return []
    # Explicitly documented analogues; never identify an unrelated launcher as Falcon.
    text=' '.join(str(launch.get(k,'')) for k in ('orbit','mission','mission_name')).lower()
    if family=='falcon-heavy': targets=['Falcon Heavy Demo 1']
    elif 'transfer' in text or 'geostationary' in text: targets=['SES-9','Thaicom 8']
    elif 'international space station' in text or 'crew' in text or 'crs' in text: targets=['DM-1','SpaceX CRS-8']
    else: targets=['Orbcomm OG2','DM-1']
    rows=[]
    for entry in catalog:
        if not isinstance(entry,dict) or entry.get('analysed_stage')!=2 or entry.get('mission_name') not in targets:
            continue
        row={**entry,'JSON':dict(entry.get('JSON') or {})}
        # Verified against this archive directory on 2026-10-02: the catalogue
        # points at nonexistent analysed2.json; the actual file is analysed.json.
        # Correct only this exact known link, not arbitrary source paths.
        old='https://raw.githubusercontent.com/shahar603/Telemetry-Data/master/SpaceX%20CRS-8/JSON/analysed2.json'
        if row['mission_name']=='SpaceX CRS-8' and row['JSON'].get('analysed')==old:
            row['JSON']['analysed']=old.replace('/analysed2.json','/analysed.json')
            row['catalog_note']='Known CRS-8 catalogue link corrected to the verified archive file.'
        rows.append(row)
    return sorted(rows,key=lambda r:targets.index(r['mission_name']))[:2]

def historical_profile(data,events,name,url):
    times=data.get('time',[]);alt=data.get('altitude',[]);down=data.get('downrange_distance',[])
    if not (10<=len(times)<=10000 and len(times)==len(alt)==len(down)):
        raise SourceUnavailable('Historical arrays are missing or unequal')
    meco=numeric(events.get('meco'),1,1800);ses=numeric(events.get('ses1'),1,1800);seco=numeric(events.get('seco1'),1,3600)
    if meco is None or ses is None or seco is None or not meco<ses<seco:
        raise SourceUnavailable('Historical stage timings unavailable')
    points=[];last=-1
    for t,h,d in zip(times,alt,down):
        t=numeric(t,0,3600);h=numeric(h,-0.1,2000);d=numeric(d,-0.1,20000)
        if t is None or h is None or d is None or t<=last:raise SourceUnavailable('Invalid historical profile')
        last=t
        if t<=seco and (t%10<0.001 or any(abs(t-e)<0.001 for e in (meco,ses,seco))):
            points.append([t,max(0,h),max(0,d),bool(t<meco or ses<=t<seco)])
    if not points or points[-1][0]<seco-1:raise SourceUnavailable('Historical profile ends before first cutoff')
    return {'name':name,'source':HISTORY_ATTRIBUTION,'url':url,'samples':points,
            'note':'Historical altitude (km), derived downrange (km), and event times (s). '
                   'Rotating this profile onto a new corridor is an estimate, not that mission’s actual path.'}

def from_ecef_m(x,y,z):
    """ITRF/ECEF meters to WGS84 geodetic latitude/longitude/height-km."""
    a=6378137.0;e2=6.69437999014e-3;b=a*math.sqrt(1-e2)
    if not all(math.isfinite(v) for v in (x,y,z)):raise SourceUnavailable('Nonfinite simulation coordinate')
    p=math.hypot(x,y)
    if p<1e-8:return (90 if z>=0 else -90),0,(abs(z)-b)/1000
    lon=math.atan2(y,x);lat=math.atan2(z,p*(1-e2))
    for _ in range(12):
        n=a/math.sqrt(1-e2*math.sin(lat)**2)
        lat2=math.atan2(z+e2*n*math.sin(lat),p)
        if abs(lat2-lat)<1e-12:lat=lat2;break
        lat=lat2
    n=a/math.sqrt(1-e2*math.sin(lat)**2)
    h=p/math.cos(lat)-n
    return math.degrees(lat),math.degrees(lon),h/1000

def flightclub_tracks(payload,launch_id):
    """Full v3 schema: t seconds after T0, x_NI meters in ITRF, ts newtons.

    Stages and discontinuous sections remain separate. No synthetic connections
    between a returning booster and upper stage; no undocumented lite-unit guess.
    """
    sims=payload if isinstance(payload,list) else [payload]
    valid=[s for s in sims if isinstance(s,dict) and (s.get('mission') or {}).get('launchLibraryId')==launch_id
           and not s.get('expired') and not (s.get('data') or {}).get('errors')]
    if not valid:raise SourceUnavailable('No unexpired simulation with exact launch identity')
    sim=max(valid,key=lambda s:str(s.get('createdAt','')))
    tracks=[]
    for stage in (sim.get('data') or {}).get('stageTrajectories',[])[:8]:
        rows=stage.get('telemetry',[])
        if len(rows)>100000:raise SourceUnavailable('Simulation stage too large')
        segment=[];last=None
        def finish():
            if len(segment)<2:return
            selected=[segment[0]]
            for i,p in enumerate(segment[1:-1],1):
                if p['t_s']-selected[-1]['t_s']>=5 or p['powered']!=segment[i-1]['powered'] or p['powered']!=segment[i+1]['powered']:
                    selected.append(p)
            if selected[-1]!=segment[-1]:selected.append(segment[-1])
            tracks.append(Trajectory(source='Flight Club mission-specific simulation',
                source_url='https://flightclub.io/result/3d?llId='+launch_id,kind='mission-specific',
                notes=f'Simulation {sim.get("id", "unknown")}; stage {stage.get("stageNumber")}. '
                      'Simulated, not measured telemetry. Separate stage/continuous segment. First hour only.',
                points=selected).model_dump())
        for row in rows:
            t=numeric(row.get('t'),-120,3600)
            if t is None or t<0:continue
            frames=row.get('frames') or []
            if len(frames)<2 or not any(s in str(frames[1]).upper() for s in ('ITRF','ECEF')):
                raise SourceUnavailable('Simulation frame is not verified Earth-fixed')
            xyz=row.get('x_NI')
            if not isinstance(xyz,list) or len(xyz)!=3:raise SourceUnavailable('Simulation position missing')
            lat,lon,alt=from_ecef_m(*map(float,xyz))
            if not -0.05<=alt<=2000:
                if segment:finish();segment=[]
                last=None;continue
            thrust=numeric(row.get('ts'),0,1e10)
            if thrust is None:raise SourceUnavailable('Simulation thrust state missing')
            if last is not None and t<=last:raise SourceUnavailable('Simulation times are not monotonic')
            if last is not None and t-last>120:finish();segment=[]
            segment.append(dict(t_s=t,latitude=lat,longitude=lon,altitude_km=max(0,alt),
                                powered=thrust>0,plume=thrust>0 and alt>=25))
            last=t
        finish()
    if not tracks:raise SourceUnavailable('No usable simulation segments')
    if len(tracks)>24:raise SourceUnavailable('Too many simulation segments')
    return tracks
