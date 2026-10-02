# Unraid GUI updates

## Existing container

One time: Docker → Downrange icon → Edit → Repository:

```
ghcr.io/spikked27/downrange:latest
```

Apply without changing the name, `/data` mapping, host port, PUBLIC_URL or existing settings. This works whether the old repository was a pinned GHCR tag or a local-build image. Do not add another container. No source download, terminal command or local build is required.

After the release has published, reopen WebUI and verify the footer version. Refresh once or close/reopen the installed PWA if an old tab remains. Subsequent releases: Docker → Check for Updates → Update Downrange. These controls check images; clicking the app's Refresh View only refreshes its data, not its software.

`latest` is a tested alpha update channel. Published exact-version tags remain unchanged. A pinned old version will deliberately stay on that version. GUI image updates do not change the appdata mapping, account database or environment settings.

## Data preservation and backup

On application-version changes, a consistent SQLite backup and the persistent VAPID key are saved under `/data/backups/before-<version>/`. With the default mapping this is `/mnt/user/appdata/downrange/backups/`. Backup files contain private account/location/subscription data and require protection. Do not delete appdata or change notification keys during the update. Keep a separate backup of the full appdata folder as usual.

The first-start ADMIN_PASSWORD setting is not reapplied to an existing account. Continue using the working password. PUBLIC_URL must still match the exact HTTPS origin you open. The newer error explains origin mismatch separately from an invalid password.

To roll back software, stop and edit Repository to an earlier published version (the original is `ghcr.io/spikked27/downrange:0.2.0-alpha.1`). The 0.3 release keeps the same database tables. Do not restore a database while the container runs. For a full data rollback, stop the container, preserve the current database/WAL/SHM files elsewhere, restore the matching snapshot database and key, and start the appropriate version. Do not leave unrelated WAL files alongside a restored snapshot.

## Defaults and notification setup

Container port 8097, bridge networking, appdata `/mnt/user/appdata/downrange`, PUID/PGID 99:100. The application does not need privileged mode or a Docker socket. Existing settings are compatible with 0.3; automatic trajectory-source acquisition defaults to enabled even if the old template lacks the new variable. No API key is needed for public-source acquisition.

Flight Club is optional: add variable `FLIGHTCLUB_API_KEY` only with a compatible account/key. Otherwise it should report not configured, not block other sources. Advanced variable `SOURCES_ENABLED=false` disables automatic source acquisition.

Phone push needs HTTPS at a dedicated hostname, not a subpath. Use your existing reverse proxy with HTTP upstream to the Unraid IP and mapped app port. Do not expose the Unraid management interface. Register each device in Notifications, send a test, enable the master schedule switch and per-location alerts. Estimated-path alerts need estimate opt-in; broad low-information cases additionally need candidate opt-in. Alerts use saved locations, not closed-app GPS.

## New installations

The registry template in `templates/downrange.xml` and `scripts/install-unraid.sh` use latest. The script adds a template without creating containers or overwriting existing settings. The separate local-build scripts remain developer fallbacks, not the normal upgrade path. Container package visibility must be Public for anonymous pulls; the release workflow verifies this after publication.
