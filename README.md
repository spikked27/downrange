# Downrange

**The launch isn't local. The view might be.**

A self-hosted, multi-location launch-viewing and space-jellyfish research app with browser push. Version **0.3.0-alpha.2** integrates automatic public-source acquisition and introduces Unraid GUI updates.

## Update an existing Unraid installation — no terminal required

Open **Docker → Downrange icon → Edit**. Change **Repository** to:

```
ghcr.io/spikked27/downrange:latest
```

Keep the same container name, appdata mapping, port, PUBLIC_URL, password, and other settings. Click **Apply**, then reopen WebUI. The footer should show **0.3.0-alpha.2** once that release's workflow has succeeded. This first change moves an old pinned-version/local-build installation onto the update channel. Future releases use **Docker → Check for Updates → Update**. Do not add a second container or delete appdata.

`latest` means the current tested **alpha**, not production-stable forecasting. Exact version tags remain available for rollback. The workflow promotes latest only from current main, after tests, fresh-container checks, and an actual old-image upgrade test. It also checks anonymous registry access. Check Actions for the actual build outcome.

Before changing application version, Downrange creates a consistent SQLite snapshot and copies the notification key into `/data/backups/before-<new-version>/`. This does not replace a separate host backup. Existing credentials, locations, preferences, and push subscriptions are reused. A new ADMIN_PASSWORD environment value is not a password reset.

## Automatic prediction inputs

Every provider/vehicle in the cached schedule with usable pad coordinates enters the evaluator. There is no Falcon-9-only gate. That is not a promise of equally good evidence for all missions.

- Launch Library 2 supplies the paginated schedule, pads, vehicles and mission information, under a persistent request budget.
- Next Spaceflight public mission pages and the Jellyfish site's available heading metadata supply matched departure directions when available.
- Linked recognized operator/agency pages are checked for explicitly stated flight directions.
- Historical webcast-derived Falcon-family ascent analogues are fetched automatically. A previous flight is never relabeled as current telemetry.
- Flight Club simulation acquisition is optional with a suitable `FLIGHTCLUB_API_KEY`; no purchase or key is included. Authenticated access remains unverified without a key.

Sources are cached and checked separately from the notification worker. Mission identity, date, coordinates and source provenance matter. The viewing brief includes source evidence and distinguishes simulations, historical analogues and broad assumptions. Manual trajectory imports take precedence. See [sources and limits](docs/SOURCES.md) and [model](docs/MODEL.md).

## Locations and notifications

Private accounts, up to ten saved locations each, town search, coordinates, foreground device location, per-location timezones and horizon cutoffs. Separate powered-night and sunlit-plume intervals, a sky-path chart, observer-grid cloud forecasts, and persistent server-side push reminders.

HTTPS is required for phone push. Keep the exact working `PUBLIC_URL`. Enable this device, master scheduled alerts, and per-location alerts. Inferred-path reminders require **Include experimental estimated trajectories**. Broad low-information cases also require **Include broad / low-information candidates**. Quiet hours and stale/uncertain launch times suppress alerts. Send a test and verify actual receipt on the phone; server acceptance is not proof of delivery.

## New Unraid install

Use [templates/downrange.xml](templates/downrange.xml), which points to latest. The optional one-time installer is:

```bash
curl -fsSL --retry 3 https://raw.githubusercontent.com/spikked27/downrange/main/scripts/install-unraid.sh -o /tmp/downrange-install.sh && bash /tmp/downrange-install.sh
```

Then Docker → Add Container → Downrange. Default port 8097; appdata `/mnt/user/appdata/downrange`; username `admin`; choose a 12+ character bootstrap password. HTTPS may be configured after the initial LAN test. This is a saved template, not a Community Applications listing. See [Unraid guide](docs/UNRAID.md).

## Validation and remaining work

135 automated local tests passed for the integrated release preparation. CI separately tests the published predecessor image's data surviving container replacement. Do not infer CI success from this paragraph: see the repository's Actions run and [validation record](docs/VALIDATION.md).

This remains a research alpha. Generic trajectories are estimates, not vehicle performance certification. No calibrated detection probabilities, comprehensive NOTAM/NAVWARN/PDF ingestion, terrain model, line-of-sight cloud integration, universal later-burn/daylight coverage, or historically validated sighting accuracy yet. Weather is shown separately and does not gate alerts. Upstream feeds may omit unannounced or some suborbital flights. No app-store release or background GPS tracking.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
node --check app/static/app.js
node --check app/static/sources-ui.js
node --check app/static/sw.js
```

Single worker/container per appdata. Use separate appdata for `DEMO_MODE=true`. No privileged mode, Docker socket, or additional database service is required. MIT source license; third-party data and dependencies retain their terms. Protect appdata and backups; see [security](docs/SECURITY.md). Not affiliated with launch providers or the inspiration site.
