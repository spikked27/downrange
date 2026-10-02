# Geometry and estimates: global-evidence-1

Positions use WGS84 geodetic coordinates transformed to Earth-fixed Cartesian coordinates and observer east/north/up coordinates. Track altitude is kilometers above the ellipsoid, observer elevation is meters, and trajectory time is seconds after nominal liftoff. Short-arc longitude interpolation handles the dateline; powered/plume flags apply until the next point. Geometry samples at up to five-second spacing, which is not a five-second forecast-accuracy claim.

Powered-night geometry requires an active modeled burn above the observer's horizon cutoff and the Sun below the observer's horizon. Jellyfish geometry requires a plume-bearing segment above that cutoff, sunlight at altitude, and an observer Sun no higher than minus four degrees. That contrast threshold is heuristic. The approximate solar ephemeris and equatorial-radius spherical shadow omit refraction, penumbra, extinction and plume evolution. Daylight detectability is unassessed rather than impossible.

All launch providers with pad coordinates enter the estimator. An imported track takes precedence, followed by usable mission-specific simulations, then public mission directions combined with historical or engineering ascent estimates. Inferred orbital-plane and launch-site sectors are lower-confidence priors. No hardcoded vehicle whitelist blocks unknown providers.

Direction and altitude/time variations form alternative paths. Their union can flag a candidate based on one favorable alternative. Counts are sensitivity checks, not probabilities; the plotted path need not be flown. Historical altitude/downrange traces remain analogues when rotated onto a new corridor. Generic profiles are explicitly broad engineering envelopes, not measured performance specifications. Separate simulated booster/upper-stage trajectories are not concatenated.

Fallback coverage is incomplete for later burns, unusual suborbital flights, plume persistence, daylight brightness and events absent from upstream schedules. Negative results do not establish invisibility. Clouds cover the observer's forecast grid cell, not the full viewing ray; weather does not gate notifications yet.

References: WGS84 https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84 ; solar coordinates https://aa.usno.navy.mil/faq/sun_approx ; source integration details in SOURCES.md. No reference supplies the generic hand-chosen envelopes as a validated vehicle trajectory.
