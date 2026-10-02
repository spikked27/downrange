# 0.3.1-alpha.1 — viewing time and useful briefs

## Implemented

- An interactive elevation-versus-elapsed-time chart, T+0/full-ascent view, viewing-window zoom, horizon cutoff, powered-night/plume shading, cursor and keyboard-accessible time slider. A time table and the previous direction chart remain available.
- Sampled first, highest luminous elevation and last viewing events, with T+ time, observer-local date/time, azimuth and elevation. Cutoff/restart gaps remain separate. Later nonluminous coasting peaks are excluded from the viewing peak.
- Plotted-path windows are distinguished from the union of alternative trajectories. A direction from one scenario is not combined with a time from another.
- More useful feed cards and modeled-opportunity counts, source-progress/status display, administrator recheck requests honoring cache/quota controls, and automatic visible-feed refresh.
- Observer cloud forecasts on up to six cards, requested for the viewing peak rather than always liftoff. Weather is not a visibility guarantee or an alert filter.

## Validation status

During preparation, 146 tests passed in the local source working copy, plus JavaScript timeline assertions. Desktop and phone component-browser tests passed using synthetic data and an in-memory ASGI transport. Browser navigation is restricted in the authoring environment, so that local component harness is not an HTTP/TLS deployment test.

The GitHub release workflow is configured to test the complete repository, then run actual HTTP browser tests at 1440x1100 and 390x844, fresh-container checks, and upgrades from both published 0.2.0-alpha.1 and 0.3.0-alpha.2 images. It will publish the exact tested image as the version tag and latest only if those checks succeed. Consult Actions for completed results; this document does not claim a pending workflow has passed.

## Scope

This is a timing/usability improvement, not a claim of new mission-trajectory accuracy or complete provider coverage. The existing automatic-source engine remains in use. No user settings, notification opt-ins or appdata mapping should be changed to install it. Use the Unraid GUI update on the existing latest channel. Existing data-preserving upgrade/snapshot behavior remains enabled.
