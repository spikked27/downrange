# Validation: 0.3.0-alpha.2

## Published release — October 2, 2026

[GitHub Actions run 37007731533](https://github.com/spikked27/downrange/actions/runs/37007731533) completed successfully for application commit `95f72b35e6f56112c249e9de7406fb8b3c86643d`.

- Clean Python 3.13 test job: **135 tests passed**, one upstream Starlette/AnyIO deprecation warning. JavaScript and shell syntax checks passed.
- Linux amd64 Docker image build: passed.
- Fresh-container startup, file permissions and restart/key-persistence checks: passed.
- Actual previous-image upgrade: passed. The test pulled the published `0.2.0-alpha.1` image, created isolated test appdata through its HTTP API, replaced the container with the new image, and confirmed that the old password, existing login session, saved location, notification preferences, push subscription and VAPID private key all survived.
- Automatic pre-upgrade consistent database snapshot and notification-key copy: verified present.
- Publication of the exact tested image as `ghcr.io/spikked27/downrange:0.3.0-alpha.2`, `ghcr.io/spikked27/downrange:latest`, and the exact-commit tag: passed.
- Anonymous pull of `latest` with an empty Docker credential configuration: passed. The downloaded reference reported version `0.3.0-alpha.2` and matched the tested local image ID.

Published manifest digest: `sha256:41715e56e33d79a4b59e3c8c1d8a4e8bf6e387b0ae3244dfb1754f7194a3292d`.

The update channel was published at approximately 12:38 UTC. Later documentation-only commits do not change this image. Existing Unraid installations must change the Repository once from a pinned/local tag to `ghcr.io/spikked27/downrange:latest`; subsequent versions can be applied through the normal Unraid Docker update controls. Exact version tags remain rollback points. `latest` is still an alpha channel, not a claim of production forecasting maturity.

## Test scope and limits

The local integrated suite also passed 135 tests. Source-adapter tests cover mission/date matching, conflicting direction retention, robots/backoff, endpoint boundaries, historical units, Earth-fixed simulation conversion, and multiple provider families. Account and notification tests cover ownership isolation, eligibility, key persistence and upgrade continuity.

Upgrade tests used temporary CI volumes, not the user's server or real appdata, and did not send real push messages. Publication does not mean an existing Unraid instance has already updated; its owner must Apply the repository change or run the GUI update. The full production HTTPS/PWA/device-notification path still needs deployment testing.

Earlier live public-source adapter check: [Actions run 36968346040](https://github.com/spikked27/downrange/actions/runs/36968346040) matched NROL-97 public directions and a historical Falcon Heavy ascent analogue. This proves data conversion and geometry, not actual sighting or weather accuracy. Authenticated Flight Club access and historical forecast accuracy remain unverified. Weather is displayed separately and does not yet gate alerts.
