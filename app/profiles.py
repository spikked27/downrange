"""Experimental scenario families, not flight telemetry or sighting probabilities.

Only named site/vehicle families are screened automatically. Directions, heights,
and flight times are assumptions; several scenarios expose their sensitivity.
A mission-specific administrator import ALWAYS takes priority over these models.
See docs/MODEL.md. This module deliberately does not infer Starlink inclination
from a group number, nor call an unknown launch invisible.
"""
from __future__ import annotations
import math
from .models import Trajectory

MODEL_VERSION = "corridors-1"


def corridor(launch: dict) -> tuple[list[float], str] | None:
    pad = launch.get("pad") or {}
    lat, lon = pad.get("latitude"), pad.get("longitude")
    if lat is None or lon is None or launch.get("demo"):
        return None
    vehicle = launch.get("vehicle", "").lower()
    # Do not apply Falcon 9 burn timing to another vehicle family.
    if "falcon 9" not in vehicle:
        return None
    name = launch.get("name", "").lower()
    orbit = launch.get("orbit", "").lower()
    description = launch.get("mission", "").lower()
    florida = 28.0 <= lat <= 29.0 and -81.0 <= lon <= -80.0
    vandenberg = 34.0 <= lat <= 35.5 and -121.0 <= lon <= -120.0
    if not (florida or vandenberg):
        return None
    iss = ("international space station" in orbit or orbit.strip() == "iss"
           or "international space station" in description)
    sso = "sun-synchronous" in orbit or "sun synchronous" in orbit or orbit.strip() == "sso"
    polar = "polar" in orbit or orbit.strip() == "po"
    gto = "geostationary transfer" in orbit or "geosynchronous transfer" in orbit or orbit.strip() == "gto"
    if iss and florida:
        # Orbital-plane geometry ignoring rotation/doglegs: sin(A)=cos(i)/cos(phi).
        angle = math.degrees(math.asin(math.cos(math.radians(51.6)) / math.cos(math.radians(lat))))
        return [angle - 7, angle, angle + 7], "ISS destination: assumed northeast ascent; 51.6-degree target inclination"
    if sso or polar:
        center = 190.0 if sso else 180.0
        return [center - 12, center, center + 12], "Polar/SSO destination: assumed southern corridor; doglegs not modeled"
    if gto and florida:
        return [80.0, 90.0, 100.0], "GTO destination: assumed eastbound initial ascent; later burns not modeled"
    if "starlink" in name:
        if florida:
            return [40.0, 65.0, 90.0, 115.0, 145.0, 180.0, 195.0], "Starlink from Florida: WIDE direction-unknown scenario set, not a mission corridor"
        return [140.0, 160.0, 180.0, 200.0], "Starlink from Vandenberg: WIDE direction-unknown scenario set, not a mission corridor"
    return None


def automatic_tracks(launch: dict) -> list[dict]:
    selection = corridor(launch)
    if selection is None:
        return []
    from .geometry import destination
    headings, reason = selection
    pad = launch["pad"]
    # Engineering screening assumptions, NOT measured altitude/downrange data.
    # Explicit stage-transition gap; powered states apply until the next sample.
    samples = [(0, 0, 0, True), (60, 10, 5, True), (120, 40, 45, True),
               (155, 65, 95, False), (165, 72, 115, True), (180, 85, 150, True),
               (240, 120, 350, True), (300, 160, 620, True), (360, 190, 950, True),
               (420, 215, 1350, True), (480, 230, 1800, True), (540, 240, 2300, False)]
    tracks = []
    for heading in headings:
        for altitude_scale, time_scale in [(0.8, 0.9), (1.0, 1.0), (1.2, 1.1)]:
            points = []
            for t, altitude, downrange, powered in samples:
                latitude, longitude = destination(pad["latitude"], pad["longitude"], heading, downrange)
                points.append(dict(t_s=round(t*time_scale, 2), latitude=latitude, longitude=longitude,
                                   altitude_km=altitude*altitude_scale, powered=powered,
                                   plume=(t >= 60 and powered)))
            notes = (f"{reason}. Initial true heading {heading:.1f} deg; altitude scale {altitude_scale}; "
                     f"time scale {time_scale}. Assumed generic ascent, not reconstructed flight data. "
                     "No plume persistence after cutoff. Scenario counts are NOT probabilities.")
            tracks.append(Trajectory(source=f"Downrange {MODEL_VERSION}: experimental scenario", kind="estimated",
                                     notes=notes, points=points).model_dump())
    return tracks


def combine(predictions: list[dict], launch: dict) -> dict:
    """Conservative language around an optimistic union of possible scenarios."""
    best = max(predictions, key=lambda p: (bool(p["ordinary_windows"] or p["jellyfish_windows"]),
                                          p.get("max_elevation_deg") or -90))
    result = dict(best)
    ordinary = sorted([w for p in predictions for w in p["ordinary_windows"]], key=lambda w: w["start"])
    jelly = sorted([w for p in predictions for w in p["jellyfish_windows"]], key=lambda w: w["start"])
    geometric = sorted([w for p in predictions for w in p["geometric_windows"]], key=lambda w: w["start"])
    def merge(rows):
        merged = []
        for row in rows:
            if merged and row["start"] <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], row["end"])
            else:
                merged.append(dict(row))
        return merged
    elevations = [p["max_elevation_deg"] for p in predictions if p["max_elevation_deg"] is not None]
    windows = sorted(ordinary+jelly, key=lambda w: w["start"])
    directions = sorted({p["direction"] for p in predictions if p["direction"]})
    reason = corridor(launch)[1]
    result.update(automatic=True, model_version=MODEL_VERSION,
                  candidate=any(p["candidate"] for p in predictions), confidence="estimated",
                  ordinary="possible in assumed scenarios" if ordinary else "not found in assumed scenarios",
                  jellyfish="possible sunlit-plume geometry" if jelly else "not found in assumed scenarios",
                  ordinary_windows=merge(ordinary), jellyfish_windows=merge(jelly), geometric_windows=merge(geometric),
                  first_visible=windows[0]["start"] if windows else None,
                  direction=" / ".join(directions) if directions else None,
                  best_time=None, source="Downrange experimental corridor scenarios", source_url="",
                  notes=reason, elevation_range_deg=[min(elevations), max(elevations)] if elevations else None,
                  scenario_counts={"total":len(predictions), "above":sum(p["candidate"] for p in predictions),
                                   "ordinary":sum(bool(p["ordinary_windows"]) for p in predictions),
                                   "jellyfish":sum(bool(p["jellyfish_windows"]) for p in predictions)},
                  warnings=["AUTOMATIC ESTIMATE: assumed flight paths, not a mission-specific prediction.",
                            "An optimistic union: one modeled scenario is enough to appear as a candidate. False positives are expected.",
                            "Viewing intervals span alternative scenarios; the launch may not follow ANY of them.",
                            "The chart shows ONE favorable scenario, not a confirmed path. Directions and elevations can change substantially.",
                            "Scenario counts are sensitivity checks, NOT percentages or probabilities.",
                            *[w for w in best["warnings"] if not w.startswith("EXPERIMENTAL:")]])
    return result
