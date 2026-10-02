# Validation: 0.3.0-alpha.2

Local integrated suite: **135 tests passed** during release preparation. JavaScript and shell syntax checks also passed. Source-adapter tests cover mission/date matching, conflicting direction retention, robots/backoff, endpoint boundaries, historical units, Earth-fixed simulation conversion, and multiple provider families. Account and notification tests cover ownership isolation, eligibility, key persistence and upgrade continuity.

The release workflow builds once, runs startup/permission/restart tests, then upgrades isolated appdata from the actual published `0.2.0-alpha.1` image to the candidate. That test checks the old password and login session, saved location, preferences, push subscription, private key, and pre-upgrade backup. It does not use anyone's real appdata or send real push.

Only after the test jobs pass does the workflow publish the exact tested image. It retains exact-version tags, promotes `latest` only from current main, and attempts an anonymous pull with an empty Docker credential configuration. Read the associated Actions logs for completed versus pending results; workflow definitions alone are not evidence of success.

Earlier live public-source adapter check: Actions run 36968346040 matched NROL-97 public directions and a historical Falcon Heavy ascent analogue. This proves data conversion and geometry, not actual sighting or weather accuracy. Authenticated Flight Club access, production phone notification receipt and forecast validation remain unverified.
