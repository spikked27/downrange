# Alpha security and privacy

Use a private LAN/VPN deployment initially. This is not an independently audited public SaaS service.

Passwords use salted scrypt; session identifiers are randomly generated and stored hashed, with HttpOnly/SameSite cookies (Secure when PUBLIC_URL is set). Mutating browser API calls require a same-origin custom header. Registration is off without an invitation code. Accounts are isolated by ownership checks. Request bodies are limited to 1 MiB and authentication endpoints are rate-limited. The container drops to configured UID/GID before starting the app.

Push endpoints are restricted to known browser push-service hosts and redirects are blocked by the sending session. Private keys and appdata files have restrictive permissions. An initially generated bootstrap password is printed once in the container log if ADMIN_PASSWORD is absent; prefer setting one in the template, then changing it in Account. Do not publish logs, appdata, .env files, notification subscriptions, or recovery credentials.

Locations, preferences, and subscriptions are stored in plaintext inside the private SQLite database; this is not encryption at rest. Protect host access and backups. Geocoding sends search text to Open-Meteo. Forecast requests send rounded location coordinates. Notifications travel via third-party browser push services. No analytics/tracking scripts are included.

Run one container and one worker per appdata directory. Expose only the application via a properly configured HTTPS reverse proxy. Do not expose Unraid management/Docker API. PUBLIC_URL must match the address used by clients. Keep dependencies and images current; the cryptography dependency range respects pywebpush 2.5's minimum version. Pinned application image tags do not automatically advance to new releases.

Limits: no MFA, email password reset, per-device session UI, account-deletion interface, administrator role management, or independent penetration test. Do not put passwords, exact locations, or notification endpoints into public GitHub issues. Report security issues privately to the repository owner through an appropriate private channel.
