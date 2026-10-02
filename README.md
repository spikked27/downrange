# Downrange

**The launch isn't local. The view might be.**

A self-hosted launch-viewing planner with customizable locations, observer-local sky playback, time-based viewing windows, source provenance and browser notifications. **1.0.0-alpha.1** is the first consolidated alpha milestone, not a claim of production forecasting accuracy. Check [the release record](docs/RELEASE-1.0-ALPHA.md) and Actions for publication status.

## Update in Unraid

On `ghcr.io/spikked27/downrange:latest`: **Docker → Check for Updates → Update Downrange**. Keep the same appdata, port, PUBLIC_URL, password and other settings. Reopen the web app and check the footer version. No terminal, source ZIP, reinstall or second container is required. Pinned/local-build installations need a one-time GUI Repository change to the latest reference. [Installation and rollback](docs/UNRAID.md).

## Alpha 1 refinements

**Your horizon, not just a flat cutoff.** Saved locations now accept eight optional obstruction angles: N, NE, E, SE, S, SW, W, NW. They interpolate between directions and cannot lower the global minimum viewing elevation. A higher southern skyline need not hide a clear eastern view. The observer perspective, timeline, calculated windows and notification eligibility all use the same limits. These are manually entered angles, not downloaded terrain or a photograph of your surroundings.

**Find the useful opportunity.** The feed highlights the next future modeled viewing window, preferring better-constrained directions over broad guesses. Search mission, vehicle, provider or site; select a 24-hour range; filter broad estimates out or show only mission-specific paths. The spotlight is still an estimate and can be blocked by clouds or insufficient brightness. Existing sky playback, drag-to-pan, follow, zoom and linked T+ sliders remain.

**See what the data actually supports.** Sources & health separates an available service from matched evidence for a specific mission. Viewing briefs distinguish imported tracks, simulations, published direction plus historical ascent, and generic/orbital assumptions. Actual source fetch timestamps are no longer confused with a new research attempt. Source components expire independently; payload/orbit changes and schedule shifts cause rechecks. One malformed record no longer stops the whole acquisition cycle.

**More appropriate historical analogues.** Falcon 9 station/crew missions, transfer-orbit missions and other flights use different named historical ascent candidates instead of every mission using the same two traces. Falcon Heavy remains a separate analogue family. This improves selection; it does not reconstruct the new mission or establish equally strong data for other vehicles.

**Reliability.** Schedule fetching, source acquisition and notification scheduling run separately. Shared bounded geometry caching avoids recalculation for mere feed timestamp updates. Unsent reminders cancelled by a changed prediction can be rescheduled; sent reminders cannot be requeued by this path. Password whitespace is preserved. Versioned web assets and cache revalidation reduce stale-interface confusion. Sources & health offers a redacted diagnostic download, never an automatic upload.

## Viewing and notifications

Choose a saved location, open a launch's **Viewing brief**, and explore **Your view of the sky** above **Visibility after liftoff**. The marker is deliberately enlarged, and the path is a guide, not a forecast of apparent plume size, brightness or a permanent trail. First, peak and last events use modeled luminous intervals; alternative scenario windows are shown separately. No camera feed, downloaded skyline, live guidance or automatic background GPS tracking is implied.

Phone push requires a working HTTPS origin. Register the device, enable scheduled alerts, and enable that saved location. Inferred-path reminders require the existing estimate opt-in. Broad low-information cases also require candidate opt-in. Existing alert settings are not automatically changed on update. Weather still appears separately and does not gate alerts.

## Scope of source coverage

Every scheduled record with usable pad coordinates is evaluated without a launch-provider whitelist. Automatic readers check available Next Spaceflight direction facts, Jellyfish heading metadata, limited explicit directions on linked official pages, and historical Falcon-family webcast ascent data. Flight Club is optional and requires a compatible licensed API key; authenticated retrieval has not been verified here. Manual tracks override automatic estimates.

No upstream source promises every unannounced or obscure suborbital event. An engineering envelope is not an actual mission trajectory. Comprehensive hazard-notice/PDF ingestion, a broad non-Falcon historical archive, line-of-sight weather, plume evolution, calibrated brightness, universal later burns/daylight support and historical sighting validation remain incomplete. Read [source details](docs/SOURCES.md) and [model assumptions](docs/MODEL.md).

## Installation and data

The [Unraid template](templates/downrange.xml) uses latest. Default port 8097; appdata `/mnt/user/appdata/downrange`; first account `admin`. Keep the exact working PUBLIC_URL when updating. A consistent database/key snapshot is saved before an application-version change; maintain your own external backup too. Existing accounts, sessions, locations, preferences and notification keys are reused. Do not delete appdata or run two containers against it.

The alpha is intended for private self-hosting, not an audited public SaaS. Diagnostics exclude exact locations, names, usernames, hostnames, passwords, cookies, API keys and push endpoints. Database backups are private and contain account data. [Security and privacy](docs/SECURITY.md).

## Development and validation

Run `python -m pytest -q`, `node tests/test_timeline.cjs`, `node tests/test_observer.cjs` and `node tests/test_v1.cjs`. Browser tests use Playwright 1.57.0 with Chromium: `scripts/browser-smoke.py`, `scripts/observer-browser-smoke.py`, and `scripts/pwa-smoke.py`. The separate `scripts/check-history-sources.py` performs bounded live archive compatibility checks, not sighting validation.

The release pipeline tests actual HTTP desktop/mobile interactions and isolated predecessor-image upgrades before publishing the tested Linux amd64 image. It verifies anonymous latest pulls. See the release record for completed results, not just the workflow definition. MIT application source; third-party dependencies and data retain their licenses and usage terms.
