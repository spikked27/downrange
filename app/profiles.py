"""Provider-neutral, evidence-ranked trajectory estimates.

Exact imported/sourced paths override these priors. Historical ascent shapes
are not historical *geographic* tracks of the current mission. Generic paths
are deliberately marked low-information, never silently branded as telemetry.
"""
from __future__ import annotations
import math,re
from .models import Trajectory
from .source_inputs import numeric

MODEL_VERSION='global-evidence-1'

def corridor(launch):
    pad=launch.get('pad') or {};lat=pad.get('latitude');lon=pad.get('longitude')
    if lat is None or lon is None or launch.get('demo'):return None
    facts=(launch.get('acquisition') or {}).get('directions') or []
    if facts:
        headings=[]
        for fact in facts:
            h=fact['heading_deg'];spread=fact.get('spread_deg',12)
            headings.extend([(h-spread)%360,h%360,(h+spread)%360])
        return list(dict.fromkeys(headings)), 'Published mission direction with angular uncertainty'
    text=' '.join(str(launch.get(k,'')) for k in ('orbit','mission','mission_name','name')).lower()
    # Inclination restricts the orbital plane, not the exact ascent guidance.
    m=re.search(r'(\d{1,3}(?:\.\d+)?)\s*(?:degrees?|°)[ -]*(?:inclination|inclined)',text)
    inclination=numeric(m[1],0,180) if m else None
    if 'international space station' in text:inclination=51.6
    if 'sun-synchronous' in text or 'sun synchronous' in text:inclination=97.5
    if 'polar orbit' in text:inclination=90
    if inclination is not None and abs(lat)<89.9:
        value=math.cos(math.radians(inclination))/math.cos(math.radians(lat))
        if abs(value)<=1:
            az=math.degrees(math.asin(value))%360
            directions=[az,(180-az)%360]
            # These site choices are priors, not restrictions on all future launches.
            if 28<=lat<=29 and -81<=lon<=-80 and 'international space station' in text:directions=[az]
            elif 34<=lat<=35.5 and -121<=lon<=-120:directions=[(180-az)%360]
            elif -40<lat<-38 and 177<lon<179:directions=[(180-az)%360]
            elif lat>65 and 10<lon<25:directions=[az]
            return [(a+d)%360 for a in directions for d in (-10,0,10)], f'Orbital-plane prior: {inclination:g}° inclination; rotation and doglegs uncertain'
    # No provider gate. Site departure sectors are explicitly broad, not a flight plan.
    if 28<=lat<=29 and -81<=lon<=-80:
        if 'transfer orbit' in text or 'geostationary' in text:return [75,90,105], 'Florida eastbound transfer-orbit prior'
        return [35,55,75,95,115,145,175,195], 'Florida wide departure-sector prior; mission direction unknown'
    if 34<=lat<=35.5 and -121<=lon<=-120:return [140,160,180,200,220], 'Vandenberg wide southern-sector prior; mission direction unknown'
    if 37<lat<39 and -77<lon<-75:return [45,75,105,135,165], 'Wallops broad oceanward prior; mission direction unknown'
    return list(range(0,360,30)), 'Global all-direction sensitivity screen; no mission departure information'

def generic_samples(launch):
    """Engineering envelope, not a named-vehicle performance specification."""
    text=' '.join(str(launch.get(k,'')) for k in ('vehicle','orbit','mission_type')).lower()
    sub=launch.get('suborbital') is True or 'suborbital' in text or 'new shepard' in text
    if sub:
        samples=[(0,0,0,True),(60,15,0,True),(120,65,1,True),(160,85,3,False),
                 (220,105,5,False),(300,70,8,False),(400,0,10,False)]
        return samples,'Generic suborbital envelope; apogee and downrange are unknown'
    # Separate heavy/slow and general timing envelopes, rather than Falcon 9 reuse.
    slow=any(v in text for v in ('electron','atlas','vulcan','ariane','h3','pslv','gslv','long march','new glenn'))
    heavy='falcon heavy' in text
    duration=900 if slow else 600 if heavy else 650
    meco=240 if slow or heavy else 180
    samples=[]
    for t,h,d in [(0,0,0),(60,8,3),(120,35,35),(meco,85,160),
                  (meco+12,95,190),(duration*.60,160,550),
                  (duration*.80,220,1200),(duration,280,2300)]:
        samples.append((float(t),h,d,t<meco or meco+12<=t<duration))
    samples.sort(key=lambda p:p[0])
    return samples,'Generic orbital ascent envelope; no vehicle-specific measured performance'

def automatic_tracks(launch):
    selection=corridor(launch)
    if selection is None:return []
    from .geometry import destination
    headings,reason=selection;pad=launch['pad'];acq=launch.get('acquisition') or {}
    history=acq.get('profiles') or []
    sources=[(h['samples'],h['name'],h['url']) for h in history[:2]]
    if not sources:
        samples,label=generic_samples(launch);sources=[(samples,label,'')]
    tracks=[]
    # Stronger variation when no historical vehicle prior exists.
    variations=[(.85,.9),(1,1),(1.2,1.12)] if history else [(.65,.8),(1,1),(1.8,1.25)]
    for samples,label,url in sources:
        for heading in headings:
            for altitude_scale,time_scale in variations:
                points=[]
                for t,alt,distance,powered in samples:
                    latitude,longitude=destination(pad['latitude'],pad['longitude'],heading,distance)
                    point=dict(t_s=round(t*time_scale,3),latitude=latitude,longitude=longitude,
                               altitude_km=round(alt*altitude_scale,6),powered=bool(powered),plume=bool(powered and alt>=25))
                    # Interpolate gaps in the *envelope*, retaining phase boundaries.
                    if points and point['t_s']-points[-1]['t_s']>100:
                        a=points[-1];n=math.ceil((point['t_s']-a['t_s'])/100)
                        for i in range(1,n):
                            f=i/n;dl=(point['longitude']-a['longitude']+180)%360-180
                            points.append(dict(t_s=a['t_s']+f*(point['t_s']-a['t_s']),latitude=a['latitude']+f*(point['latitude']-a['latitude']),
                                longitude=(a['longitude']+f*dl+180)%360-180,altitude_km=a['altitude_km']+f*(point['altitude_km']-a['altitude_km']),
                                powered=a['powered'],plume=a['plume']))
                    points.append(point)
                notes=f'{reason}. Heading {heading:.1f}°. Ascent: {label}. Altitude/time factors {altitude_scale}/{time_scale}. '
                notes+='Historical analogue, not current mission telemetry. ' if history else 'Low-information engineering envelope. '
                notes+='Scenario counts are NOT probabilities; later burns require a sourced path.'
                track=Trajectory(source=f'Downrange {MODEL_VERSION}: '+('historical analogue' if history else 'generic envelope'),
                                 source_url=url,kind='estimated',notes=notes[:2000],points=points).model_dump()
                tracks.append(track)
    return tracks

def merge_windows(rows):
    merged=[]
    for row in sorted(rows,key=lambda r:r['start']):
        if merged and row['start']<=merged[-1]['end']:merged[-1]['end']=max(merged[-1]['end'],row['end'])
        else:merged.append(dict(row))
    return merged

def combine(predictions,launch,*,sourced=False):
    best=max(predictions,key=lambda p:(bool(p['ordinary_windows'] or p['jellyfish_windows']),p.get('max_elevation_deg') if p.get('max_elevation_deg') is not None else -90))
    result=dict(best);acq=launch.get('acquisition') or {};selection=corridor(launch)
    ordinary=merge_windows([w for p in predictions for w in p['ordinary_windows']])
    jelly=merge_windows([w for p in predictions for w in p['jellyfish_windows']])
    geometric=merge_windows([w for p in predictions for w in p['geometric_windows']])
    elevations=[p['max_elevation_deg'] for p in predictions if p['max_elevation_deg'] is not None]
    windows=sorted(ordinary+jelly,key=lambda w:w['start'])
    directions=sorted({p['direction'] for p in predictions if p['direction']})
    has_direction=bool(acq.get('directions'));has_history=bool(acq.get('profiles'))
    level='mission-simulation' if sourced else 'published-direction/history' if has_direction and has_history else 'published-direction/envelope' if has_direction else 'orbit/site-prior'
    low_information=not sourced and not has_direction and not (selection and 'Orbital-plane' in selection[1])
    result.update(automatic=True,model_version=MODEL_VERSION,candidate=any(p['candidate'] for p in predictions),
        confidence='mission-specific' if sourced else 'estimated',evidence_level=level,low_information=low_information,
        ordinary='possible powered-flight geometry' if ordinary else 'not found in modeled paths',
        jellyfish='possible sunlit-plume geometry' if jelly else 'not found in modeled paths',
        ordinary_windows=ordinary,jellyfish_windows=jelly,geometric_windows=geometric,
        first_visible=windows[0]['start'] if windows else None,direction=' / '.join(directions) if directions else None,
        best_time=best['best_time'] if sourced else None,
        source='Flight Club mission-specific simulation' if sourced else 'Published facts + historical/engineering estimates',
        source_url=best.get('source_url',''),notes='Separate sourced stage paths' if sourced else (selection[1] if selection else 'No corridor'),
        elevation_range_deg=[min(elevations),max(elevations)] if elevations else None,
        scenario_counts={'total':len(predictions),'above':sum(p['candidate'] for p in predictions),
                         'ordinary':sum(bool(p['ordinary_windows']) for p in predictions),'jellyfish':sum(bool(p['jellyfish_windows']) for p in predictions)},
        source_evidence=acq.get('evidence',[]),source_checked=acq.get('checked'),source_notes=acq.get('notes',[]),
        historical_analogues=[{'name':p['name'],'url':p['url']} for p in acq.get('profiles',[])],
        warnings=(["Mission-specific simulation, not an actual-flight measurement. Separate stages are not concatenated."] if sourced else [
            'AUTOMATIC ESTIMATE: time-varying ascent inferred from available facts; not confirmed mission guidance.',
            'A positive scenario is a viewing opportunity to investigate, not a detection probability.',
            'Alternative paths are combined; the chart shows one favorable path, not all alternatives.',
            'Later burns, plume persistence and daylight detectability need better mission data.'])+
            (['Departure direction is low-information. Broad-candidate opt-in is required for alerts.'] if low_information else [])+
            acq.get('notes',[])+[w for w in best['warnings'] if not w.startswith('EXPERIMENTAL:')])
    return result
