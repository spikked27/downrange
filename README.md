# Downrange

**The launch isn't local. The view might be.**

Self-hosted launch-viewing estimates, jellyfish geometry and notifications from customizable locations. Source version **0.3.2-alpha.1** adds an observer-local perspective. Check Actions for completed publication before updating.

## Unraid GUI update

On `ghcr.io/spikked27/downrange:latest`, use **Docker → Check for Updates → Update Downrange**. Keep appdata, PUBLIC_URL, port, password and other settings unchanged. Reopen the app and check the footer version. No new container or source download is required. A previously pinned/local image needs a one-time GUI Repository change to the latest reference. Exact-version images remain rollback points. See [Unraid instructions](docs/UNRAID.md).

## Your vantage point

Open a launch's **Viewing brief → Your view of the sky**. The new view appears above the existing time graph when a modeled path is available. It looks outward from the selected saved location, using that observer's calculated azimuth/elevation rather than an overhead map or a launchpad bearing.

Drag the sky to pan/tilt, use +/− to change field of view, select Frame flight, or Follow marker. Play flight replays at 1×, 10× or 30×. Its time slider and the time graph stay synchronized, including graph taps and first/peak/last buttons. Playback is never automatic; it stops when the brief closes or the page is hidden.

The position marker is deliberately enlarged. It is hidden below the geometric horizon, filled for modeled powered-night/sunlit-plume phases, and otherwise an unassessed position guide. The line is a trajectory guide, NOT a prediction of visible exhaust. Future and engine-off path segments are differentiated. The horizon is generic and flat; trees, buildings, terrain, star positions, plume brightness/size and camera AR are not modeled. A historical analogue remains an estimate in this view. See [observer release details](docs/RELEASE-0.3.2.md).

## Existing features

The time graph plots elevation against time since liftoff, with viewing-window zoom, cursor, local times, compass bearings, horizon cutoff and separate burn/plume windows. Feed cards show when to start looking and source status. Observer-grid weather is requested near the modeled viewing peak, shown separately, and does not gate alerts.

All launch-provider records with usable pad coordinates enter the evaluator. Automatic source readers use available matched departure directions, limited linked official information and historical Falcon-family ascent analogues; optional Flight Club simulations require a suitable API key. Manual tracks override estimates. Generic paths are not validated mission guidance. Comprehensive hazard-notice/PDF ingestion, wider historic vehicle data, directional clouds, brightness calibration and later-burn/daylight coverage remain unfinished. See [sources](docs/SOURCES.md) and [model](docs/MODEL.md).

Private accounts and saved locations, horizon cutoffs, timezones, quiet hours and server-side browser push are retained. Phone push needs the exact working HTTPS origin in PUBLIC_URL. Estimate and low-information alerts require their existing opt-ins. The update does not change permissions or settings. Pre-upgrade database/key snapshots and the normal external appdata backup should be kept. See [security](docs/SECURITY.md).

## Validation

New geometry assertions cover perspective projection, north crossing, camera orientation, horizon clipping and field-of-view fitting. Full pipeline tests exercise both graph and perspective at desktop/phone sizes over local HTTP, then upgrade isolated data from published predecessor images before publishing. Test fixtures are synthetic and do not validate actual visibility or phone push delivery. Refer to the release record and Actions for completed results.

Development: install requirements-dev.txt, run pytest and `node tests/test_observer.cjs`. Browser tests use Playwright 1.57.0/Chromium and `scripts/browser-smoke.py` plus `scripts/observer-browser-smoke.py`. The renderer uses only local assets. No device camera, motion, geolocation or new network-service permission is requested for this view.

MIT application source; third-party data and APIs retain their terms. The latest image is still an alpha, not a production-accuracy claim.
