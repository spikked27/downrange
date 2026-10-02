"""Batched public-source acquisition with independent freshness and failures."""
from __future__ import annotations
import asyncio
import hashlib
import json
import time
from urllib.parse import urlsplit, urlencode
from .source_inputs import (CachedReader, SourceUnavailable, public_url, mission_matches,
    nextspaceflight_index, nextspaceflight_facts, jellyfish_facts, official_facts)
from .trajectory_sources import HISTORY_INDEX, history_candidates, historical_profile, flightclub_tracks
from .geometry import utc
from .evidence import identity, needs_research, usable

NSF = 'https://nextspaceflight.com/launches/'
JELLY = 'https://jellyfish.johnkrausphotos.com/api/v2/upcoming'


def select_evidence(evidence):
    rank = {'official-direction':0, 'published-direction':1, 'published-estimate':2}
    rows = sorted(evidence, key=lambda e: rank.get(e['kind'],9))
    if not rows: return [], []
    chosen, notes = [rows[0]], []
    for row in rows[1:]:
        delta = abs((row['heading_deg']-rows[0]['heading_deg']+180)%360-180)
        if delta > max(rows[0]['spread_deg'],row['spread_deg']):
            chosen.append(row)
            notes.append('Sources disagree on launch direction; alternative corridors retained.')
    return chosen, list(dict.fromkeys(notes))


class Acquisition:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        self.reader = CachedReader(store)
        self.lock = asyncio.Lock()

    async def read(self, url, ttl=3600, **kwargs):
        body = await self.reader.get(url, ttl, **kwargs)
        record = self.store.meta(self.reader.key(url), {})
        # Actual cache fill time, never this research attempt's time.
        return body, {'observed_at': record.get('fetched'),
                      'content_digest': hashlib.sha256(body.encode()).hexdigest()[:16]}

    async def refresh(self):
        if self.settings.demo_mode or not self.settings.sources_enabled:
            return {'disabled': True}
        async with self.lock:
            now = time.time()
            launches = [l for l in self.store.launches(hydrate=False)
                        if l.get('feed_active') and not l.get('demo')
                        and now-3600 <= utc(l['net']).timestamp() <= now+90*86400]
            status = {'checked': now, 'sources': {}, 'resolved': 0, 'attempted': 0, 'running': True,
                      'scheduled_records': len(launches), 'errors': 0}
            self.store.set_meta('acquisition_status', status)
            try:
                if not launches: return status
                async def document(name, url, default, parser, ttl=3600, robots=True):
                    try:
                        body, metadata = await self.read(url, ttl, robots=robots)
                        parsed = parser(body)
                        if not isinstance(parsed,type(default)):
                            raise ValueError('Unexpected document schema')
                        status['sources'][name] = {'status':'available','checked':metadata['observed_at']}
                        return parsed, metadata
                    except Exception as exc:
                        status['sources'][name] = {'status':'unavailable','reason':type(exc).__name__,'checked':now}
                        return default, {}
                index, _ = await document('Next Spaceflight', NSF, [], nextspaceflight_index)
                jelly, jelly_meta = await document('Jellyfish heading metadata', JELLY, {}, json.loads)
                catalog, _ = await document('Historical webcast profiles', HISTORY_INDEX, [], json.loads, 86400, False)
                status['sources']['Flight Club'] = {'status':'configured' if self.settings.flightclub_key else 'not configured'}
                launches.sort(key=lambda l: utc(l['net']).timestamp())
                for launch in launches:
                    old = self.store.meta('acquired:'+launch['id'], {})
                    if not needs_research(old, launch, now): continue
                    if status['attempted'] >= 12: break
                    status['attempted'] += 1
                    try:
                        result = await self.research(launch, old, index, jelly, jelly_meta, catalog, now)
                    except Exception as exc:
                        # One malformed mission must not stop research for every other launch.
                        status['errors'] += 1
                        retained = usable(old, launch, now)
                        result = {**retained, 'identity':identity(launch),'schedule_net':launch['net'],
                                  'checked':now,'errors':['Research failed: '+type(exc).__name__],
                                  'valid_until':retained.get('valid_until',now),
                                  'checks':[{'source':'Research worker','status':'error'}]}
                    old_model = {k:old.get(k) for k in ('directions','profiles','tracks')}
                    new_model = {k:result.get(k) for k in ('directions','profiles','tracks')}
                    if old_model != new_model:
                        self.store.execute("UPDATE deliveries SET status='cancelled' WHERE launch_id=? AND status='pending' AND kind='reminder'", (launch['id'],))
                    self.store.set_meta('acquired:'+launch['id'], result)
                    if result.get('directions') or result.get('tracks'): status['resolved'] += 1
                    self.store.set_meta('acquisition_status', status)
                return status
            finally:
                status['running'] = False
                status['completed'] = time.time()
                self.store.set_meta('acquisition_status', status)

    async def research(self, launch, old, index, jelly, jelly_meta, catalog, now):
        cadence = 3600 if utc(launch['net']).timestamp() < now+2*86400 else 21600
        evidence, errors, checks, links = [], [], [], list(launch.get('info_urls') or [])
        candidates = [r['url'] for r in index if mission_matches(launch,r['name'])]
        # Remember an exact match even after a mission drops off the index page.
        if not candidates and old.get('identity') == identity(launch):
            candidates = [e['url'] for e in old.get('evidence',[]) if e.get('source')=='Next Spaceflight']
        candidates = list(dict.fromkeys(candidates))
        if len(candidates)==1:
            try:
                body, metadata = await self.read(candidates[0], cadence)
                row = nextspaceflight_facts(body, launch, candidates[0])
                links += row.pop('links',[])
                evidence.append({**row, **metadata})
                checks.append({'source':'Next Spaceflight','status':'matched','observed_at':metadata['observed_at']})
            except Exception as exc:
                errors.append('Next Spaceflight: '+type(exc).__name__)
                checks.append({'source':'Next Spaceflight','status':'unavailable_or_unmatched'})
        else:
            checks.append({'source':'Next Spaceflight','status':'ambiguous' if candidates else 'no_match'})
        try:
            row = jellyfish_facts(jelly, launch) if jelly else None
            if row: evidence.append({**row, **jelly_meta})
            checks.append({'source':'Space Jellyfish Predictor','status':'matched' if row else 'no_match'})
        except (ValueError, TypeError, KeyError):
            checks.append({'source':'Space Jellyfish Predictor','status':'invalid_record'})
        official_links = []
        for url in dict.fromkeys(links):
            try:
                public_url(url)
                if urlsplit(url).hostname not in {'nextspaceflight.com','jellyfish.johnkrausphotos.com','raw.githubusercontent.com','api.flightclub.io'}:
                    official_links.append(url)
            except (ValueError,TypeError): continue
        for url in official_links[:2]:
            try:
                body, metadata = await self.read(url, cadence)
                row = official_facts(body, launch, url)
                if row: evidence.append({**row, **metadata})
                checks.append({'source':urlsplit(url).hostname,'status':'matched' if row else 'no_explicit_direction'})
            except Exception as exc:
                errors.append('Linked official source: '+type(exc).__name__)
        profiles = []
        for analogue in history_candidates(catalog,launch):
            try:
                urls = analogue['JSON']
                data, _ = await self.read(urls['analysed'], 7*86400, robots=False)
                events, _ = await self.read(urls['events'], 7*86400, robots=False)
                profile = historical_profile(json.loads(data),json.loads(events),analogue['mission_name'],urls['analysed'])
                profiles.append(profile)
                checks.append({'source':'Historical ascent: '+analogue['mission_name'],'status':'analogue_loaded'})
            except Exception as exc:
                errors.append('Historical ascent: '+type(exc).__name__)
        tracks, tracks_until = [], now
        if self.settings.flightclub_key:
            try:
                url = 'https://api.flightclub.io/v3/simulation?'+urlencode({'launchLibraryId':launch['id'],'includeData':'true','granularity':5})
                body, metadata = await self.read(url,cadence,headers={'X-Api-Key':self.settings.flightclub_key},robots=False,max_bytes=16_000_000)
                tracks = flightclub_tracks(json.loads(body),launch['id'])
                tracks_until = (metadata['observed_at'] or now)+3*cadence
                checks.append({'source':'Flight Club','status':'mission_matched','observed_at':metadata['observed_at']})
            except Exception as exc:
                errors.append('Flight Club: '+type(exc).__name__)
                checks.append({'source':'Flight Club','status':'unavailable_or_unmatched'})
        else:
            checks.append({'source':'Flight Club','status':'not_configured'})
        selected, notes = select_evidence(evidence)
        for row in evidence:
            if row.get('source_net') and abs((utc(row['source_net'])-utc(launch['net'])).total_seconds()) > 300:
                notes.append(row['source']+' time differs from the schedule; it did not override liftoff.')
        times = [e['observed_at'] for e in selected if e.get('observed_at') is not None]
        directions_until = min(times)+86400 if times else now
        retained = usable(old, launch, now)
        # Restore components independently; never extend their original expiry.
        if not selected and errors and retained.get('directions'):
            selected, evidence = retained['directions'], retained.get('evidence',[])
            directions_until = retained.get('directions_until',retained.get('valid_until',now))
            notes.append('Last known direction retained after a source failure; expiry unchanged.')
        if not tracks and self.settings.flightclub_key and retained.get('tracks'):
            tracks = retained['tracks']
            tracks_until = retained.get('tracks_until',retained.get('valid_until',now))
        if not profiles and errors: profiles = retained.get('profiles',[])
        return {'identity':identity(launch),'schedule_net':launch['net'],'checked':now,
                'valid_until':max(directions_until,tracks_until,now+86400 if profiles else now),
                'directions_until':directions_until,'tracks_until':tracks_until,
                'directions':selected,'evidence':evidence,'profiles':profiles,'tracks':tracks,
                'notes':list(dict.fromkeys(notes)),'errors':errors,'checks':checks}
