"""Bounded source refresh intervals; no live-flight timing claims."""
from __future__ import annotations
import time
from .geometry import utc


def source_interval(launch: dict, now: float | None = None) -> int:
    now = time.time() if now is None else now
    remaining = utc(launch['net']).timestamp() - now
    if -3600 <= remaining <= 6 * 3600:
        return 300
    if -86400 <= remaining <= 48 * 3600:
        return 900
    return 21600
