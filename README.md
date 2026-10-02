# Downrange

**The launch isn't local. The view might be.**

Self-hosted launch-viewing estimates, sunlit-plume/jellyfish geometry and notifications from customizable locations. Current source release: **0.3.1-alpha.1**. Check GitHub Actions for image publication status.

## Update through Unraid

Existing users on `ghcr.io/spikked27/downrange:latest`: **Docker → Check for Updates → Update Downrange** after the release workflow succeeds. Keep the same appdata mapping, port, PUBLIC_URL, password and other settings. Reopen or refresh the web app and check its footer version. No source ZIP, reinstall, terminal command or new container is needed.

A pinned/local-build installation needs one GUI change: Docker → Downrange icon → Edit → Repository → `ghcr.io/spikked27/downrange:latest` → Apply. Exact-version tags remain available for rollback; latest is a tested **alpha** channel, not a production-accuracy claim. See [Unraid guide](docs/UNRAID.md).

## New: when to look, not just where

The viewing brief includes an elevation-versus-time-since-liftoff graph. It starts at T+0, shows the saved horizon cutoff, shades modeled powered-night and sunlit-plume intervals, and leaves engine-off gaps separate. A cursor/keyboard-accessible slider reports elapsed time, observer-local clock time, true azimuth, elevation and slant distance. Switch between the full modeled ascent and a zoom around viewing intervals. The old azimuth/elevation chart is retained as an expandable view.

First, peak and last viewing events are computed from luminous intervals in the plotted path; an unrelated later coasting high point is not the viewing peak. The union of alternative scenario windows is displayed separately so its earlier time cannot be mistaken for the single path's viewing direction. These are sampled estimates, not precise flight telemetry.

Launch cards now show start-looking T+ time and clock time, direction, horizon angle, viewing peak and end. The modeled-opportunities count/filter requires an actual modeled luminous interval, rather than just an above-horizon point. Broad estimates are sorted after better-constrained cases. Source progress and status are visible on the feed, which refreshes while open. An administrator can request a cached/rate-limited source recheck. Sources retry promptly when the first schedule is still loading.

Observer-grid cloud forecasts appear on up to six feed cards and in every requested viewing brief. The requested forecast time is the modeled viewing peak (or liftoff when no viewing peak exists). Weather is still separate from geometric opportunity and does not gate alerts.

## Prediction inputs and limits

Every schedule record with usable pad coordinates is evaluated without a launch-provider whitelist. Automatic readers match public departure directions, available Jellyfish heading metadata, limited explicit directions on linked official pages, and historical Falcon-family ascent analogues. Optional Flight Club simulations require a compatible licensed API key; authenticated access has not been verified here. Manual trajectory imports override estimates. See [sources](docs/SOURCES.md) and [model](docs/MODEL.md).

This release improves time interpretation, visible diagnostics and viewing instructions; it does not add a comprehensive new trajectory archive or validate all forecasts. Generic ascent envelopes can produce false positives and false negatives. Comprehensive aviation/maritime-notice/PDF ingestion, broader historical vehicle coverage, line-of-sight clouds, calibrated brightness, plume evolution and later-burn/daylight coverage remain unfinished.

## Accounts, data and notifications

Multiple private accounts and saved locations, town/coordinate entry, optional foreground GPS, timezones, horizon cutoffs, quiet hours and server-side browser push. Phone push requires the exact working HTTPS origin in PUBLIC_URL. Keep this setting unchanged during updates. Inferred-path alerts require estimate opt-in; low-information cases also require broad-candidate opt-in. This release does not automatically change alert settings.

A consistent pre-upgrade database/key snapshot is created under `/data/backups/before-<version>/`. Keep a separate host backup too. Existing passwords, sessions, locations, preferences, push subscriptions and VAPID keys are reused. A bootstrap ADMIN_PASSWORD value is not a reset for an existing account. See [security](docs/SECURITY.md).

## Testing

The pipeline runs Python regression tests, JavaScript timeline assertions, desktop/phone browser interactions over actual local HTTP, fresh-container startup/permissions/restart checks, and replacement tests using both published 0.2 and 0.3 predecessor images. It publishes only the tested image and verifies anonymous latest pulls. Browser fixtures are synthetic and real push is disabled; this is not sighting/forecast validation. See [release notes](docs/RELEASE-0.3.1.md) and Actions for actual outcomes.

For development: install `requirements-dev.txt`, run `python -m pytest -q`, `node tests/test_timeline.cjs`, and syntax-check the JavaScript. Browser tests require Playwright 1.57.0 and its Chromium runtime (`python -m playwright install --with-deps chromium`), then `python scripts/browser-smoke.py`. Use one container/worker per appdata directory, with separate demo data. Normal users should use the published image and [Unraid template](templates/downrange.xml).

MIT application source; third-party dependencies, data and APIs retain their terms. Check upstream terms before commercial/public use. No analytics trackers. Not affiliated with launch providers or the inspiration site.
