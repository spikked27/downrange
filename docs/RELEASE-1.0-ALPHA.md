# 1.0.0-alpha.1 — consolidated alpha milestone

## Published and verified — October 2, 2026

[Release workflow 37035217498](https://github.com/spikked27/downrange/actions/runs/37035217498) completed successfully for application commit `47a46ce7b60a0a83dcc788c3d45ac06996109d1b`. It published the tested Linux amd64 image as `ghcr.io/spikked27/downrange:1.0.0-alpha.1` and advanced `ghcr.io/spikked27/downrange:latest`. The anonymous-pull verification step completed successfully, confirming the reported version and exact image identity after publication. Documentation-only commits after this release do not change that image.

Existing latest-channel installations: **Unraid → Docker → Check for Updates → Update Downrange**. Keep the same appdata, port, PUBLIC_URL, password and other settings. Reopen the PWA and verify footer `1.0.0-alpha.1`. There is no source download, local build, second container, or reinstall requirement. Publication does not itself update the user's server.

## New in this milestone

**Local skyline limits.** Saved locations → Edit → Local obstructions by direction accepts eight optional angles above the level horizon: N, NE, E, SE, S, SW, W, NW. Linear interpolation blends between directions and the global minimum remains a floor. The same limits affect ordinary/plume viewing windows, notification eligibility, the time chart and the observer-local perspective. Existing locations retain their previous flat minimum by default. These are manually entered obstructions, not downloaded terrain or a photographed skyline.

**A more focused planner.** The existing observer perspective and linked time playback are preserved. A next-opportunity summary points to a future modeled viewing window; better-constrained directions are preferred over broad guesses. Search mission, provider, vehicle or launch site, select the next 24 hours, or filter broad estimates out. These remain modeled opportunities, not guarantees of clear skies or detectable brightness.

**Sources & health.** A new page separates service availability from matched per-mission evidence. Viewing briefs distinguish imported tracks, mission simulations, direction plus historical ascent, direction plus generic ascent, orbital/site assumptions and broad estimates. Actual source fetch timestamps are separate from research attempts. Directions and simulations expire independently, schedule or payload/orbit changes cause rechecks, and one failed mission does not abort all other acquisition.

**Historical input improvements.** Falcon 9 station/crew/CRS, transfer-orbit and general flights have separate named analogue selections; Falcon Heavy remains separate. A live audit exposed an incorrect CRS-8 catalogue URL and the application now corrects that exact verified link. It does not rewrite arbitrary URLs or modify the upstream archive. Previous flights are still labelled historical analogues, not current mission telemetry.

**Reliability and support.** Schedule polling, trajectory research and notification delivery use separate tasks. Bounded shared geometry caching avoids recalculation for mere feed timestamp changes. Cancelled/expired unsent reminders can be requeued after a changed prediction; the same code path does not replay sent reminders. Password whitespace is preserved. Versioned web assets and cache revalidation reduce stale-interface confusion. The Sources & health diagnostic download excludes coordinates, location names, usernames, hostname, passwords, API keys, cookies, push endpoints and private keys; nothing is automatically uploaded.

## Completed verification

- Clean Python 3.13 regression suite: **187 tests passed**, with one upstream deprecation warning.
- JavaScript timeline assertions, **179 observer projection/state assertions**, and v1 horizon/filter/state assertions passed; JavaScript and shell syntax checks passed.
- Actual HTTP desktop 1440×1100 and phone 390×844 browser interactions passed, including horizon save/readback, search, source-health UI, diagnostics, viewing-event buttons, time slider, zoom, modal reopening and overflow checks.
- Actual HTTP observer tests passed for linked flight clocks, follow/pan/zoom, horizon behavior, path guide, playback and cleanup.
- Actual localhost Chromium service-worker installation, versioned shell/observer caching, query-string offline shell, private API exclusion and online session recovery passed. This was not a production TLS or cross-version service-worker-migration test.
- Fresh Docker startup, data permissions and restart/key-persistence checks passed.
- Actual published predecessor-image upgrade tests passed from **0.2.0-alpha.1, 0.3.0-alpha.2, 0.3.1-alpha.1 and 0.3.2-alpha.1**. The old password, existing session, saved location, preferences, push subscription and VAPID key were preserved, and pre-upgrade snapshots existed.
- Versioned-image publication, latest-channel promotion and anonymous pull/version/image-identity verification passed.

All browser/upgrade checks used synthetic data and isolated CI volumes. No test accessed the user's server/appdata or sent a real phone notification.

## Separate live source audit

[Candidate/source workflow 37034963761](https://github.com/spikked27/downrange/actions/runs/37034963761), commit `e3de8731c0bf75eca840de1d91a9f428a6ce1f4c`, passed the bounded live archive compatibility check after the CRS-8 correction. Each configured class—Falcon 9 station, transfer-orbit, general low-orbit and Falcon Heavy—had at least one successfully retrieved and parsed historical analogue. The same source-reader correction is included in the published release. This verifies retrieval, units and event/profile parsing, not actual sighting accuracy.

## Acceptance boundaries

Alpha 1 consolidates the installed workflow and reliability checks; it is not production-stable forecasting or universal validated launch visibility. Comprehensive NOTAM/NAVWARN/PDF ingestion, broad non-Falcon historical profiles, directional clouds, calibrated daylight/brightness, plume evolution, universal later-burn coverage and historical sighting validation remain open. Observer-grid weather remains contextual and does not gate alerts. The observer rendering uses an enlarged marker and path guide, not a physically accurate plume or camera AR. Actual production TLS and receipt of a notification on the user's device remain deployment-specific checks.
