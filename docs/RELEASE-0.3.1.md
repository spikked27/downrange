# 0.3.1-alpha.1 — viewing time and useful briefs

## Published October 2, 2026

[Release workflow 37014555009](https://github.com/spikked27/downrange/actions/runs/37014555009) completed successfully for application commit `73ad9b70f93bb3b47ec22212940e9367b83a3f23`. The exact tested Linux amd64 image was published as `ghcr.io/spikked27/downrange:0.3.1-alpha.1` and `ghcr.io/spikked27/downrange:latest` at approximately 13:42 UTC.

Published registry manifest digest: `sha256:3fc3279cd8a74be99ba0a22f66a23e53a50c2576a5cc65e0829e7d734fc1b79f`.

An anonymous registry pull with an empty Docker credential configuration succeeded. The pulled reference reported version `0.3.1-alpha.1` and matched the tested image ID. This does not mean an existing Unraid installation has already updated: use Docker → Check for Updates → Update Downrange on the existing latest channel. Keep the working appdata, port, PUBLIC_URL, password and other settings unchanged.

## Implemented

- An interactive elevation-versus-elapsed-time chart, T+0/full-ascent view, viewing-window zoom, horizon cutoff, powered-night/plume shading, cursor and keyboard-accessible time slider. A time table and the previous direction chart remain available.
- Sampled first, highest luminous elevation and last viewing events, with T+ time, observer-local date/time, azimuth and elevation. Cutoff/restart gaps remain separate. Later nonluminous coasting peaks are excluded from the viewing peak.
- Plotted-path windows are distinguished from the union of alternative trajectories. A direction from one scenario is not combined with a time from another.
- Feed cards show start-looking times, directions and viewing intervals, not only nominal liftoff. Modeled-opportunity counts require a luminous interval rather than any above-horizon point. Better-constrained cases appear before broad estimates.
- Source-progress/status display, administrator recheck requests honoring cache/quota controls, and automatic visible-feed refresh. Source acquisition retries promptly when the first launch feed is still loading.
- Observer cloud forecasts on up to six cards, requested for the viewing peak rather than always liftoff. Weather is not a visibility guarantee or an alert filter.

## Completed validation

- Clean GitHub Python 3.13 regression suite: **150 tests passed**, with one upstream deprecation warning. JavaScript and shell syntax checks and dedicated time-axis/interpolation assertions passed.
- Real HTTP browser interactions passed in Chromium at desktop 1440x1100 and phone 390x844 sizes. Checked login, feed instructions, source panel, time chart, engine-off gap, event buttons, zoom, keyboard slider, modal reopening, JavaScript errors and horizontal overflow.
- Fresh Docker startup, file permissions and restart/key-persistence checks passed.
- Upgrade from the actual published `0.2.0-alpha.1` image passed using isolated test data.
- Upgrade from the actual published `0.3.0-alpha.2` image passed using isolated test data.
- Both replacement tests confirmed that the old password, existing session, saved location, alert preferences, push subscription and VAPID key survived. Automatic pre-upgrade database/key snapshots were present.
- Publication and anonymous latest pull/version/image-identity checks passed.

During preparation, 146 tests passed in the local source working copy, which did not include four existing repository upgrade tests. Local desktop/phone component tests also passed using an in-memory ASGI transport; those were not HTTP/TLS tests. The separate GitHub browser job above used actual local HTTP. All browser fixtures were clearly synthetic, external requests were blocked, and real push was disabled. Browser screenshots are test illustrations, not actual launch predictions.

## Scope and remaining work

This is a timing/usability improvement, not a claim of new mission-trajectory accuracy or complete provider coverage. The existing automatic-source engine remains in use. Generic envelopes and historical analogues remain estimates. Comprehensive aviation/maritime notice and PDF ingestion, broader historical vehicle coverage, line-of-sight cloud screening, calibrated brightness, plume evolution and universal later-burn/daylight coverage remain unfinished.

No user's server or real appdata was used for these tests. Actual production HTTPS/PWA lifecycle, phone notification receipt and historical sighting accuracy are not validated by this release. Existing data-preserving upgrade/snapshot behavior remains enabled, and the release does not change notification opt-ins.
