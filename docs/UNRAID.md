# Unraid installation

## Registry template

Wait for a successful **Test and publish Downrange** Actions run and make the `downrange` GHCR package public. Then:

```bash
curl -fsSL --retry 3 https://raw.githubusercontent.com/spikked27/downrange/main/scripts/install-unraid.sh -o /tmp/downrange-install.sh && bash /tmp/downrange-install.sh
```

Open **Docker -> Add Container -> Template: Downrange**. Administrator username is `admin`. Set a password of at least 12 characters. Default host port: `8097`; appdata: `/mnt/user/appdata/downrange`; app UID/GID: `99:100`. Leave PUBLIC_URL blank for the first LAN-only HTTP test. Apply, open WebUI, and add a saved location. Launch data may take a worker iteration to appear.

The script installs `/boot/config/plugins/dockerMan/templates-user/my-Downrange.xml` after a successful image pull. It preserves an existing template. It does not expose router ports or change other containers. No privileged mode, Docker socket, GPU, or separate database is required.

## Local-build fallback

Download this repository with GitHub's **Code -> Download ZIP**, extract it, and copy the repository contents to `/mnt/user/appdata/downrange-src`. Then:

```bash
cd /mnt/user/appdata/downrange-src
bash scripts/install-unraid-local.sh
```

Choose **Downrange-Local** in Add Container. It uses the same default port and appdata; run only one variant. Source can also be cloned with Git where available. `compose.yaml` is supplied for Docker Compose installations, not required by Unraid.

## HTTPS and notifications

Using an existing reverse proxy such as Nginx Proxy Manager, create a dedicated hostname with a valid trusted TLS certificate. Forward it to the Unraid host IP and mapped Downrange port, HTTP upstream. Downrange needs the root of its own hostname, not a subpath. Do not forward the Unraid management interface or Docker API.

Set `PUBLIC_URL` in the template to the exact HTTPS origin, e.g. `https://launch.example.com`, with no path. Apply and sign in through that HTTPS address: cookies become Secure. A certificate alone does not establish remote access; DNS/routing must also reach your reverse proxy. Prefer LAN/VPN exposure during alpha testing rather than unrestricted Internet access.

Install/open the PWA on your phone. On iPhone, add it to the home screen before requesting web push. Open Notifications, enable this device, send a test, and confirm receipt. Enable the master schedule switch and choose reminder lead times. Each saved location must also permit alerts. Quiet hours use each location's timezone.

Scenario alerts require opting into experimental estimates. Unknown-path candidates require a separate opt-in and do not provide a known viewing direction. No updates are based on closed-app GPS. Weather does not gate alerts yet.

## Updates and backup

The initial image tag is versioned. Future releases require selecting their published tag/template; blindly clicking Update does not move a pinned version to a new version. Stop the container and back up the full appdata directory, including the SQLite database and `vapid-private.pem`. Restore it before restart. Do not change notification keys unless willing to re-register devices. Do not mix demo and live appdata.

A bootstrap ADMIN_PASSWORD is used only when the database is first created. Change it inside Account thereafter. To recover a lost administrator password locally:

```bash
docker exec -it --user 99:100 Downrange python -m app.reset_password
```

Use `Downrange-Local` instead when that is your container name. This resets the admin password and revokes existing admin sessions.

## Troubleshooting

Registry denied: verify the image exists and its package visibility is Public, or use the local-build template. Port conflict: change only the host-side port. Login fails after setting PUBLIC_URL: use the matching HTTPS address. No launch reminders: check master switch, device subscription, per-location setting, estimate opt-in, quiet hours, fresh provider data, precise launch time, eligible launch status, and an actual modeled opportunity. A provider cache can be stale even while the container health check is green.
