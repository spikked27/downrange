"""Observer instructions derived from the plotted path, not a new flight model.

The ensemble window union is kept separately. Never pair a direction from one
scenario with an appearance time from another, or count a coasting high point
as the best observable part of the flight. Times are samples, not guarantees.
"""
from __future__ import annotations
from datetime import timedelta
from .geometry import utc, compass


def plan(launch: dict, prediction: dict, observer: dict) -> dict:
    net = utc(launch['net'])
    points = prediction.get('points') or []
    result = {'basis': 'plotted scenario' if prediction.get('automatic') else 'supplied path',
              'status': 'no_path', 'first': None, 'peak': None, 'last': None,
              'windows': [], 'ordinary_windows': [], 'jellyfish_windows': [],
              'scenario_windows': [], 'viewing_duration_s': 0,
              'min_elevation_deg': observer.get('min_elevation_deg', 5),
              'nominal_liftoff': launch['net'], 'time_precise': bool(launch.get('time_precise')),
              'time_basis': 'Relative to reported nominal liftoff; not live telemetry.'}

    def event(p):
        return {'t_s': p['t_s'], 'time': (net+timedelta(seconds=p['t_s'])).isoformat(),
                'azimuth': p['azimuth'], 'direction': compass(p['azimuth']),
                'elevation': p['elevation'], 'range_km': p['range_km']}

    def runs(predicate):
        output, group = [], []
        for p in points:
            if group and p['t_s']-group[-1]['t_s'] > 120:
                output.append(group); group = []
            if predicate(p): group.append(p)
            elif group: output.append(group); group = []
        if group: output.append(group)
        return output

    def window(group):
        return {'start_s': group[0]['t_s'], 'end_s': group[-1]['t_s'],
                'start': event(group[0])['time'], 'end': event(group[-1])['time'],
                'first': event(group[0]), 'peak': event(max(group, key=lambda p:p['elevation'])),
                'last': event(group[-1])}

    for field in ('ordinary', 'jellyfish'):
        result[field+'_windows'] = [window(g) for g in runs(lambda p:bool(p.get(field)))]
    groups = runs(lambda p:bool(p.get('ordinary') or p.get('jellyfish')))
    result['windows'] = [window(g) for g in groups]
    # Union windows are evidence of alternatives, not the single charted path.
    rows = sorted(prediction.get('ordinary_windows', [])+prediction.get('jellyfish_windows', []),
                  key=lambda w:utc(w['start']))
    union = []
    for row in rows:
        start = (utc(row['start'])-net).total_seconds()
        end = (utc(row['end'])-net).total_seconds()
        if union and start <= union[-1]['end_s']: union[-1]['end_s'] = max(end, union[-1]['end_s'])
        else: union.append({'start_s': start, 'end_s': end})
    result['scenario_windows'] = union
    if groups:
        visible = [p for g in groups for p in g]
        result.update(status='opportunity', first=event(visible[0]),
                      peak=event(max(visible, key=lambda p:p['elevation'])), last=event(visible[-1]),
                      viewing_duration_s=sum(g[-1]['t_s']-g[0]['t_s'] for g in groups))
    elif points:
        result['status'] = ('daylight_unassessed' if any(p.get('above') and p.get('sun_altitude',-90)>=0 for p in points)
                            else 'no_modeled_signal' if any(p.get('above') for p in points) else 'below_horizon')
    if points:
        result['track_start_s'] = points[0]['t_s']; result['track_end_s'] = points[-1]['t_s']
    return result
