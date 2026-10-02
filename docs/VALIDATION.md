# Validation record: 0.2.0-alpha.1

Local automated suite: **91 tests passed**. Coverage includes geometry fixtures, scenario labeling and overrides, input validation, ownership isolation, cookie/CSRF handling, subscription validation, provider caching/error handling, reminder eligibility, cancellation/deduplication, and key persistence. This does not validate real launch sightings.

JavaScript syntax checks passed for app.js and sw.js. An offline Chromium harness exercised the actual HTML/CSS/JS against FastAPI TestClient responses: login, three synthetic launch cards, detail canvas, saved-location creation, notification defaults, and account status. Desktop 1440x1050 and phone 390x844 produced no page errors and no mobile horizontal overflow. This harness did not test HTTP routing, TLS, service-worker lifecycle, actual GPS, or actual push delivery.

The first GitHub Actions run exposed a dependency conflict: pywebpush 2.5.0 requires cryptography >=47 whereas the original alpha pinned 46.0.4. Requirements now allow >=47,<51. Check the latest Actions run for the actual clean-environment test/build result; local tests used the environment's preinstalled libraries and are not proof that a fresh dependency installation succeeds.

CI contains a Docker startup/permission/restart-persistence smoke test and only publishes after tests pass. Docker was unavailable in the authoring environment. Real phone notification receipt, production HTTPS/PWA behavior, live-provider integration under deployment conditions, and historical forecast accuracy still require field testing.
