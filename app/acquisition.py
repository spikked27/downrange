"""Separate, cached data acquisition loop. Prediction and push never fetch here."""
from __future__ import annotations
import asyncio, hashlib, json, time
from urllib.parse import urlsplit, urlencode
from .source_inputs import (CachedReader,SourceUnavailable,public_url,mission_matches,
    nextspaceflight_index,nextspaceflight_facts,jellyfish_facts,official_facts)
from .trajectory_sources import HISTORY_INDEX,history_candidates,historical_profile,flightclub_tracks
from .geometry import utc

NSF='https://nextspaceflight.com/launches/'
JELLY='https://jellyfish.johnkrausphotos.com/api/v2/upcoming'

def identity(launch):
    return hashlib.sha256(json.dumps({k:launch.get(k) for k in ('id','name','mission_name','vehicle','pad')},sort_keys=True).encode()).hexdigest()

def select_evidence(evidence):
    """Keep conflicting directions as alternatives, not an average through land."""
    rank={'official-direction':0,'published-direction':1,'published-estimate':2}
    evidence=sorted(evidence,key=lambda e:rank.get(e['kind'],9))
    if not evidence:return [],[]
    notes=[];best=evidence[0];chosen=[best]
    for row in evidence[1:]:
        delta=abs((row['heading_deg']-best['heading_deg']+180)%360-180)
        if delta>max(best['spread_deg'],row['spread_deg']):
            notes.append('Sources disagree on launch direction; alternative corridors retained.')
            chosen.append(row)
    return chosen,list(dict.fromkeys(notes))

class Acquisition:
    def __init__(self,store,settings):
        self.store=store;self.settings=settings;self.reader=CachedReader(store);self.lock=asyncio.Lock()
    async def refresh(self):
        if self.settings.demo_mode or not self.settings.sources_enabled:return {'disabled':True}
        async with self.lock:
            now=time.time();status={'checked':now,'sources':{},'resolved':0,'attempted':0}
            async def document(name,url,ttl=3600,robots=True):
                try:
                    body=await self.reader.get(url,ttl,robots=robots)
                    status['sources'][name]={'status':'available','checked':now}
                    return body
                except Exception as exc:
                    status['sources'][name]={'status':'unavailable','reason':str(exc)[:150] if isinstance(exc,SourceUnavailable) else type(exc).__name__,'checked':now}
                    return None
            index_text=await document('Next Spaceflight',NSF)
            index=nextspaceflight_index(index_text) if index_text else []
            jelly_text=await document('Jellyfish heading metadata',JELLY)
            history_text=await document('Historical webcast profiles',HISTORY_INDEX,86400,False)
            def obj(text,default):
                try:return json.loads(text) if text else default
                except ValueError:return default
            jelly=obj(jelly_text,{});catalog=obj(history_text,[])
            if not isinstance(jelly,dict):jelly={}
            if not isinstance(catalog,list):catalog=[]
            launches=[l for l in self.store.launches(hydrate=False) if l.get('feed_active') and not l.get('demo')
                      and now-86400<=utc(l['net']).timestamp()<=now+90*86400]
            # Imminent first; work across later missions on subsequent cycles.
            launches.sort(key=lambda l:(utc(l['net']).timestamp()<now-3600,utc(l['net']).timestamp()))
            for launch in launches:
                old=self.store.meta('acquired:'+launch['id'],{})
                fingerprint=identity(launch)
                cadence=3600 if utc(launch['net']).timestamp()<now+2*86400 else 6*3600
                if old.get('identity')==fingerprint and now-old.get('checked',0)<cadence:continue
                if status['attempted']>=12:break
                status['attempted']+=1;evidence=[];errors=[];links=list(launch.get('info_urls') or [])
                candidates=[r for r in index if mission_matches(launch,r['name'])]
                if len(candidates)==1:
                    try:
                        row=nextspaceflight_facts(await self.reader.get(candidates[0]['url'],cadence),launch,candidates[0]['url'])
                        evidence.append(row);links+=row.pop('links',[])
                    except Exception as exc:errors.append('Next Spaceflight: '+str(exc)[:140])
                if jelly:
                    try:
                        row=jellyfish_facts(jelly,launch)
                        if row:evidence.append(row)
                    except (ValueError,TypeError):errors.append('Jellyfish metadata could not be matched')
                # Only exact linked mission pages on vetted agency/operator domains.
                official_links=[]
                for url in dict.fromkeys(links):
                    try:
                        public_url(url)
                        host=urlsplit(url).hostname
                        if host not in {'nextspaceflight.com','jellyfish.johnkrausphotos.com','raw.githubusercontent.com','api.flightclub.io'}:
                            official_links.append(url)
                    except (ValueError,TypeError):continue
                for url in official_links[:2]:
                    try:
                        row=official_facts(await self.reader.get(url,cadence),launch,url)
                        if row:evidence.append(row)
                    except Exception as exc:errors.append('Linked official source: '+type(exc).__name__)
                profiles=[]
                if isinstance(catalog,list):
                    for analogue in history_candidates(catalog,launch):
                        try:
                            urls=analogue['JSON']
                            data=obj(await self.reader.get(urls['analysed'],7*86400,robots=False),{})
                            events=obj(await self.reader.get(urls['events'],7*86400,robots=False),{})
                            profiles.append(historical_profile(data,events,analogue['mission_name'],urls['analysed']))
                        except Exception as exc:errors.append('Historical profile: '+type(exc).__name__)
                tracks=[]
                if self.settings.flightclub_key:
                    try:
                        url='https://api.flightclub.io/v3/simulation?'+urlencode({'launchLibraryId':launch['id'],'includeData':'true','granularity':5})
                        payload=obj(await self.reader.get(url,cadence,headers={'X-Api-Key':self.settings.flightclub_key},robots=False,max_bytes=16_000_000),{})
                        tracks=flightclub_tracks(payload,launch['id'])
                        status['sources']['Flight Club']={'status':'available'}
                    except Exception as exc:
                        errors.append('Flight Club: '+type(exc).__name__)
                        status['sources']['Flight Club']={'status':'unavailable','reason':type(exc).__name__}
                else:status['sources']['Flight Club']={'status':'not configured','reason':'Optional licensed API key required'}
                selected,notes=select_evidence(evidence)
                for row in evidence:
                    if row.get('source_net') and abs((utc(row['source_net'])-utc(launch['net'])).total_seconds())>300:
                        notes.append(row['source']+' time differs from Launch Library; it did not override the schedule.')
                result={'identity':fingerprint,'checked':now,'valid_until':now+max(3*cadence,86400),
                        'directions':selected,'evidence':evidence,'profiles':profiles,'tracks':tracks,
                        'notes':list(dict.fromkeys(notes)),'errors':errors}
                # Reuse validated evidence after transient failure, never make it fresh.
                if old.get('identity')==fingerprint and not evidence and not tracks and errors and old.get('valid_until',0)>now:
                    for key in ('directions','evidence','profiles','tracks','valid_until'):
                        result[key]=old.get(key,[])
                    result['notes'].append('Last known source evidence retained after source failure; expiry unchanged.')
                prior_model={k:old.get(k) for k in ('directions','profiles','tracks')}
                new_model={k:result.get(k) for k in ('directions','profiles','tracks')}
                if prior_model!=new_model:
                    self.store.execute("UPDATE deliveries SET status='cancelled' WHERE launch_id=? AND status='pending' AND kind='reminder'",(launch['id'],))
                self.store.set_meta('acquired:'+launch['id'],result)
                if selected or tracks:status['resolved']+=1
            self.store.set_meta('acquisition_status',status)
            return status
