# 1.0.0-alpha.1 — consolidated alpha milestone

## Candidate verification

Candidate workflow [37033813433](https://github.com/spikked27/downrange/actions/runs/37033813433) passed 184 Python tests, timeline/observer/v1 JavaScript assertions, actual HTTP desktop and phone browser tests, Docker startup checks and upgrade from the actual published 0.3.2-alpha.1 image. Tests used synthetic data and isolated volumes, never the user's appdata or real push delivery. The candidate integration was committed as d280adceaebe64f241e6143c09732f4cd9358f6c.

The normal release workflow also includes a real service-worker/offline-shell regression and upgrades from 0.2, 0.3.0, 0.3.1 and 0.3.2. Image publication and additional live archive checks must be confirmed from their actual runs; this initial record does not claim they have completed.

## New in this milestone

- Eight-direction, manually entered horizon obstruction angles per location. The same interpolation affects geometry, viewing windows, notifications, the time chart and observer perspective. Existing locations default to no additional obstructions.
- A next-opportunity summary, 24-hour range, mission/provider/vehicle/site text search and evidence-quality filters. The existing observer playback and linked time graph are retained.
- Sources & health page, readable evidence classification, per-mission source-check outcomes and redacted diagnostic export.
- Actual HTTP cache fetch times separated from research-attempt times, independent direction/simulation expiry, rechecks on schedule or payload/orbit changes and failure isolation between missions.
- Mission-class selection of historical Falcon 9 ascent analogues: ISS/crew/CRS, transfer-orbit and general cases. Falcon Heavy remains separate. More appropriate historical selection is not exact current-flight data.
- Separate schedule, source and notification tasks; bounded shared model cache; rescheduling of cancelled/expired unsent reminders without replaying sent reminders; preserved password whitespace.
- Versioned asset URLs and static cache revalidation. No user alert opt-in, password, PUBLIC_URL, appdata mapping or push key is intentionally reset.

## How to use

Normal latest-channel installation: Unraid Docker → Check for Updates → Update Downrange after publication. Check footer 1.0.0-alpha.1. Saved locations → Edit → Local obstructions by direction controls the skyline limits. Sources & health shows evidence distribution and provides the optional diagnostic download.

The observer display remains symbolic: an enlarged marker and path guide, not a photorealistic prediction of exhaust, star fields, terrain or camera AR. Source health is not a probability of detection. Weather is observer-grid context and still does not gate alerts.

## Acceptance boundaries

Alpha 1 consolidates the complete installed workflow and adds reliability checks. It is not production-stable forecasting or universal validated launch visibility. Full NOTAM/NAVWARN/PDF parsing, broad non-Falcon historical profiles, directional clouds, calibrated daylight/brightness, plume evolution, universal later-burn coverage and historical sighting validation remain open. Actual production TLS and receipt of a notification on the user's device require deployment-specific testing.
