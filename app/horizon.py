"""User-entered obstruction profile, not inferred terrain or a measured skyline."""
from __future__ import annotations
import math


def viewing_limit(observer: dict, azimuth: float) -> float:
    """Interpolate N, NE, E, SE, S, SW, W, NW circularly; keep global floor."""
    floor = float(observer.get('min_elevation_deg', 5))
    profile = observer.get('horizon_profile') or []
    if len(profile) != 8:
        return floor
    position = (azimuth % 360) / 45
    index = int(math.floor(position))
    fraction = position-index
    return max(floor, profile[index]*(1-fraction)+profile[(index+1) % 8]*fraction)


def validate_profile(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) != 8 or any(not math.isfinite(v) or not 0 <= v <= 85 for v in values):
        raise ValueError('Use eight obstruction angles from 0 to 85 degrees: N, NE, E, SE, S, SW, W, NW')
    return list(values)
