"""Source freshness and presentation separate from geometric model confidence."""
from __future__ import annotations
import hashlib
import json
import time
from .geometry import utc


def identity(launch: dict) -> str:
    # A payload/orbit change invalidates old research even if the launch UUID stays.
    fields = ('id', 'name', 'mission_name', 'vehicle', 'pad', 'orbit', 'mission_type', 'mission')
    return hashlib.sha256(json.dumps({k: launch.get(k) for k in fields}, sort_keys=True).encode()).hexdigest()


def schedule_compatible(acquired: dict, launch: dict) -> bool:
    old = acquired.get('schedule_net')
    if not old:
        return True  # Legacy data is also protected by identity and expiry checks.
    try:
        return abs((utc(old)-utc(launch['net'])).total_seconds()) <= 36*3600
    except (KeyError, ValueError, TypeError):
        return False


def usable(acquired: dict, launch: dict, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if acquired.get('identity') != identity(launch) or not schedule_compatible(acquired, launch):
        return {}
    result = dict(acquired)
    expiry = acquired.get('valid_until', 0)
    for field, clock in (('directions','directions_until'), ('tracks','tracks_until')):
        if now >= acquired.get(clock, expiry):
            result[field] = []
    if now >= expiry:
        result['profiles'] = []
    result['stale'] = now >= expiry
    return result


def needs_research(old: dict, launch: dict, now: float) -> bool:
    cadence = 3600 if utc(launch['net']).timestamp() < now+2*86400 else 21600
    return (old.get('identity') != identity(launch) or old.get('schedule_net') != launch['net']
            or now-old.get('checked', 0) >= cadence)


def quality(launch: dict, prediction: dict, track: dict | None = None, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    acquired = launch.get('acquisition') or {}
    directions = acquired.get('directions') or []
    history = acquired.get('profiles') or []
    if track:
        code = 'imported_track'
        label = 'Imported mission path' if track.get('kind') == 'mission-specific' else 'Imported estimate'
    elif acquired.get('tracks'):
        code, label = 'mission_simulation', 'Mission-specific simulation'
    elif directions and history:
        code, label = 'direction_history', 'Published direction + historical ascent'
    elif directions:
        code, label = 'direction_envelope', 'Published direction + generic ascent'
    elif prediction.get('low_information'):
        code, label = 'broad_envelope', 'Broad estimate — direction unconfirmed'
    elif prediction.get('points'):
        code, label = 'orbital_prior', 'Orbital or site assumption'
    else:
        code, label = 'unknown', 'Insufficient flight-path data'
    observed = [e['observed_at'] for e in acquired.get('evidence', [])
                if isinstance(e, dict) and isinstance(e.get('observed_at'), (int, float))]
    seen = launch.get('feed_seen')
    age = max(0, now-seen) if isinstance(seen, (int,float)) else None
    return {'code': code, 'label': label, 'schedule_age_s': age,
            'schedule_fresh': age is not None and age < 1800,
            'last_attempt': acquired.get('checked'),
            'oldest_evidence_at': min(observed) if observed else None,
            'source_checks': acquired.get('checks', []),
            'source_errors': acquired.get('errors', []),
            'stale': bool(acquired.get('stale')),
            'data_freshness_is_not_detection_probability': True}


def diagnostic_snapshot(store, settings, user: dict, version: str) -> dict:
    """Explicit support export. No coordinates, usernames, credentials or tokens."""
    feed = store.meta('feed', {})
    acquisition = store.meta('acquisition_status', {})
    source_states = {name: {'status': row.get('status'), 'checked': row.get('checked')}
                     for name, row in acquisition.get('sources', {}).items() if isinstance(row, dict)}
    return {'schema': 1, 'version': version, 'generated_at': time.time(),
            'configuration': {'https_configured': bool(settings.public_url),
                'sources_enabled': settings.sources_enabled, 'worker_enabled': settings.worker_enabled,
                'flightclub_configured': bool(settings.flightclub_key), 'demo_mode': settings.demo_mode},
            'feed': {k: feed.get(k) for k in ('last_success','last_complete','next_attempt','pages','returned','available','truncated','skipped')},
            'source_states': source_states,
            'workers': {'notifications': store.meta('worker_heartbeat'), 'schedule': store.meta('feed_worker_heartbeat')},
            'account_counts': {'locations': len(store.locations(user['id'])),
                'push_devices': len(store.rows('SELECT id FROM subscriptions WHERE user_id=?', (user['id'],)))},
            'privacy': 'No viewing coordinates, location names, usernames, hostname, passwords, cookies, push endpoints, API keys or private keys included.'}
