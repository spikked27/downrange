# Observer geometry and evidence — alpha 1

Coordinates use WGS84 geodetic position converted to Earth-fixed Cartesian coordinates, then observer east/north/up coordinates. Track height is kilometers above the ellipsoid; observer elevation is meters; track time is seconds after nominal liftoff. Short-arc longitude interpolation handles the dateline. Powered and plume states apply until the next sample. Sampling at up to five-second intervals is not a five-second forecast-accuracy claim.

## Visibility conditions and local skyline

Powered-night opportunity requires an active modeled burn above the selected viewing limit, with the Sun below the observer's horizon. Jellyfish opportunity additionally requires a plume-bearing sunlit segment and an observer Sun no higher than minus four degrees. That contrast threshold is heuristic, not a universal visibility boundary. Refraction, penumbra, atmospheric extinction, real plume shape/evolution and brightness are not modeled. Daylight remains unassessed rather than impossible.

The effective viewing limit is the maximum of the global minimum elevation and a circular linear interpolation of the user's optional eight obstruction angles: N, NE, E, SE, S, SW, W, NW. Angles are above a level horizon in true directions. They are not terrain elevations or geographic heights. Empty profiles preserve the previous flat-horizon behavior. The same per-point limit controls ordinary/plume intervals, the observer marker state, the timeline and notification eligibility.

The observer view is a perspective rendering of the modeled angular path. It preserves projection geometry and shares its flight clock with the elapsed-time chart. The marker is enlarged for legibility; apparent plume size and brightness are not predicted. The line is a trajectory guide, not a physically persistent exhaust trail. No camera image, star field, downloaded terrain or automatic local skyline is implied.

## Model sources

Imported tracks take priority over acquired mission simulations, published directions plus historical/engineering ascent shapes, and lower-confidence orbital/site priors. Historical traces do not become current mission telemetry when rotated onto a new corridor. Generic profiles remain engineering envelopes, not measured vehicle specifications. Scenario counts describe sensitivity, never probabilities.

The plotted path's first, highest luminous elevation and last viewing events remain separate from the union across alternative scenarios. A nonluminous high point is not the viewing peak. Separate booster and upper-stage trajectories are not concatenated. Missing phases, later burns, atypical suborbital events and launches absent from upstream schedules can remain unassessed.

## Weather and validation

Open-Meteo observer-grid conditions are requested around the modeled viewing peak where available. They do not describe the entire low-angle viewing ray and do not filter notifications in this alpha. Field validation against sourced real sightings remains necessary; successful code/browser tests establish implementation behavior, not skywatching detection rates.

References: WGS84 https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84 ; approximate solar coordinates https://aa.usno.navy.mil/faq/sun_approx . Source acquisition details and boundaries are in SOURCES.md. These references do not certify the hand-chosen generic ascent envelopes.
