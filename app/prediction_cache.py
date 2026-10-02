"""Bounded shared geometry cache; wall-clock freshness is checked outside it."""
from functools import lru_cache
import json
from .geometry import predict as calculate_geometry


@lru_cache(maxsize=128)
def _calculate(launch_json, observer_json, track_json):
    return calculate_geometry(json.loads(launch_json), json.loads(observer_json),
                              json.loads(track_json) if track_json else None)


def predict(launch, observer, track):
    # Schedule polling updates feed_seen without changing the physical model.
    stable = {k:v for k,v in launch.items() if k not in ('feed_seen','provider_updated')}
    return _calculate(json.dumps(stable, sort_keys=True), json.dumps(observer, sort_keys=True),
                      json.dumps(track, sort_keys=True) if track else '')
