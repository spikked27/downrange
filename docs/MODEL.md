# Prediction model and uncertainty

Downrange separates **line-of-sight geometry** from **detectability**, which this alpha does not calibrate.

## Coordinate and time model

Observers and supplied targets are converted from geodetic latitude/longitude and WGS84 ellipsoid height into Earth-fixed Cartesian coordinates. A local east/north/up transform yields true azimuth, elevation, and slant range. Observer heights are entered in meters; trajectory heights are kilometers. Points are interpolated at up to five-second spacing, with short-arc longitude interpolation across the dateline. Powered/plume flags hold until the next point. Imported times are seconds after the provider's nominal liftoff, not telemetry timestamps.

An approximate solar ephemeris determines observer solar altitude and Earth-fixed Sun direction. Parallel sunlight and an equatorial-radius spherical Earth approximate shadowing. Refraction, penumbra, atmospheric extinction, terrain, light pollution, and plume expansion/drift are absent. Accuracy near threshold boundaries is limited; five-second samples are not five-second predictive accuracy.

## Separate opportunities

Powered-night screening requires powered flight above the saved minimum elevation and observer Sun altitude below zero. Jellyfish screening requires a flagged plume segment above that horizon, illuminated by the Sun, with observer Sun at or below minus four degrees. Minus four degrees is a heuristic contrast threshold, not a universal visibility limit. Daylight and unmodeled events remain unassessed rather than impossible.

## Automatic scenarios: corridors-1

Only Falcon 9 launches from coordinate boxes around Florida launchpads and Vandenberg are eligible. Mission labels select an assumed corridor: ISS destination from Florida uses a northeast direction based on 51.6-degree inclination; GTO from Florida uses eastbound scenarios; polar/SSO missions use southern directions. These are assumptions, ignoring Earth rotation, doglegs and operational constraints, not published mission guidance.

Starlink cases use deliberately wide multiple-direction sets. Group numbers are not converted into presumed orbital inclinations. Hand-chosen generic ascent samples are perturbed by three altitude/time scale combinations; all remain **estimated**. There is no measured Falcon 9 ascent database behind these profiles. Other vehicles/sites/unknown mission families receive no automatic track.

Results are an optimistic union of scenario windows: a single positive scenario suffices to flag a candidate. False positives and false negatives are expected. Counts show model sensitivity, never probabilities. The chart draws one favorable scenario; its path need not be flown. Imported administrator tracks override these scenarios and retain their supplied provenance label.

Without any track, a permissive envelope screens up to 3000 km downrange and 400 km altitude in any direction. This is only a search filter. Being outside does not rule out other mission phases, later burns, or higher-altitude events.

## Data and operational limits

The schedule worker caches up to 100 upcoming LL2 records with a minimum ten-minute poll interval. Feed gaps, provider errors and unprecise times are surfaced. A launch needs a precise time, allowed status, fresh data, and permitted location/preferences before a reminder can be queued. This is not live launch control.

Weather samples the observer grid cell, not the viewing ray. Cloud forecasts remain separate and do not gate notifications. No automated import of Flight Club or other mission-specific trajectory feeds is implemented. Historical sighting validation and calibrated false-positive rates remain future work.

## References

- WGS84: https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84
- Approximate solar coordinates: https://aa.usno.navy.mil/faq/sun_approx
- LL2: https://thespacedevs.com/llapi
- ISS orbit background: https://www.nasa.gov/international-space-station/space-station-facts-and-figures/
- Original inspiration: https://jellyfish.johnkrausphotos.com/

No reference supplies the hand-chosen ascent scenarios: those are explicitly our unvalidated engineering assumptions.
