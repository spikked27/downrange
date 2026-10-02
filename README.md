# Downrange

**The launch isn't local. The view might be.**

Self-hosted rocket-launch visibility research, sunlit-plume / space-jellyfish geometry, and browser push notifications. Mobile-first installable web app; Docker and Unraid templates included.

## Status: 0.2.0-alpha.1

This is a working research alpha, **not a validated naked-eye visibility forecast**. Selected Falcon 9 missions have automatic, explicitly hypothetical flight-path scenarios. Unknown missions stay unknown. Imported mission-specific trajectories override estimates. No real mission trajectory provider or historical sighting calibration is connected yet.

## Included

- Private accounts and up to ten saved locations per account, anywhere in the world; town search, coordinates, foreground GPS, local timezones, adjustable horizon limits.
- Centrally cached launch schedule and status, separate powered-night and sunlit-plume geometry, viewing windows, true compass directions, and a sky-path chart.
- Experimental automatic scenario sets for selected Florida/Vandenberg Falcon 9 missions. The optimistic union can produce false positives; counts are not probabilities.
- Administrator trajectory JSON import and explicitly hypothetical heading scenarios.
- Observer-grid cloud forecasts, kept separate from geometric opportunity.
- Server-side reminder scheduling, quiet hours, stale-feed suppression, reschedule notices, persistent push subscriptions and delivery-attempt history. Estimated/candidate alerts are opt-in.
- One container, SQLite appdata, unprivileged application process, persistent notification keys, and two Unraid templates.

## Install on Unraid

After the Actions workflow has published the image and the GHCR package is public, run in the Unraid host terminal:

```bash
curl -fsSL --retry 3 https://raw.githubusercontent.com/spikked27/downrange/main/scripts/install-unraid.sh -o /tmp/downrange-install.sh && bash /tmp/downrange-install.sh
```

Then **Docker -> Add Container -> Template: Downrange**. Set a 12+ character administrator password, keep port **8097** unless occupied, review `/mnt/user/appdata/downrange`, and Apply. Sign in as `admin` using the configured password. Add your own location.

The installer pulls the versioned image and adds a saved template; it does not create/change containers or overwrite existing template settings. This is not a Community Applications listing.

**Registry denied or image missing?** Check the workflow first. A public repository does not automatically make its container package public. Repository page -> Packages -> downrange -> Package settings -> Change visibility -> Public. Alternatively download/clone this source and run `bash scripts/install-unraid-local.sh`; choose **Downrange-Local** instead. Do not run both against the same appdata.

See [the full Unraid guide](docs/UNRAID.md) for HTTPS, backup, recovery, and the local-build fallback.

## Phone notifications

The website can be inspected on LAN HTTP. Phone push needs a working HTTPS origin. Configure a reverse proxy, set `PUBLIC_URL` to that exact HTTPS origin, reopen that address, install the PWA, and register the device in Notifications. Then enable scheduled alerts and select rules. Send a test and check that it arrives on the phone; a queued message or provider acceptance is not proof of device receipt.

No background location tracking. Alerts use saved locations. Estimated trajectories and unknown-path candidates are excluded by default. Without imported trajectories, enable **experimental estimated trajectories** to receive scenario-based alerts, understanding their limitations.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
node --check app/static/app.js
node --check app/static/sw.js
```

For a live local server, configure `DATA_DIR` and a bootstrap `ADMIN_PASSWORD`, then run `uvicorn app.server:app --host 127.0.0.1 --port 8097`. Use one process/worker per appdata directory. `DEMO_MODE=true` creates clearly labeled fictional data and disables real push; use separate demo appdata.

The Actions workflow tests, builds Linux amd64, smoke-tests container startup, data permissions, and key persistence, then publishes `ghcr.io/spikked27/downrange:0.2.0-alpha.1` and an exact-commit image tag. See Actions for the actual build result, not just this README.

## Limitations and privacy

Read [MODEL.md](docs/MODEL.md), [SECURITY.md](docs/SECURITY.md), and [VALIDATION.md](docs/VALIDATION.md). No brightness probabilities, terrain, trajectory doglegs, line-of-sight cloud integration, ground-track map, camera/AR view, or native app-store packages. No guaranteed live launch status or notification receipt. Do not rely on this app for safety or navigation.

Launch data: [TheSpaceDevs / Launch Library 2](https://thespacedevs.com/llapi). Forecast and geocoding: [Open-Meteo](https://open-meteo.com/) / [GeoNames](https://www.geonames.org/). Check provider licenses and usage limits before public/commercial operation. Location searches and rounded forecast coordinates leave the self-hosted server; accounts, preferences, and subscriptions are stored locally. No analytics trackers.

MIT licensed application source. Third-party dependencies and data retain their own licenses. Not affiliated with launch providers or the inspiration website.
