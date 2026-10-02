#!/bin/bash
# Builds only this image and adds a template. Does not create/change containers.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="/boot/config/plugins/dockerMan/templates-user"
if [[ ! -f /etc/unraid-version ]]; then echo "Run this script in the Unraid host terminal." >&2; exit 1; fi
command -v docker >/dev/null || { echo "Docker is not available. Enable Docker in Unraid settings." >&2; exit 1; }
docker info >/dev/null
printf '\nBuilding Downrange locally from %s\n' "$ROOT"
docker build --tag downrange-local:0.2.0-alpha.1 "$ROOT"
mkdir -p "$TEMPLATE_DIR"
TARGET="$TEMPLATE_DIR/my-Downrange-Local.xml"
if [[ -f "$TARGET" ]]; then
  echo "Existing template retained, including your settings: $TARGET"
else
  install -m 600 "$ROOT/templates/downrange-local.xml" "$TARGET"
fi
printf '\nImage built. In Unraid: Docker → Add Container → Template: Downrange-Local.\n'
printf 'Set the administrator password, review the port and appdata path, then click Apply.\n'
printf 'Default WebUI: http://YOUR-UNRAID-IP:8097\n'
printf 'HTTPS is required later for phone push. No other container or server setting was changed.\n'
