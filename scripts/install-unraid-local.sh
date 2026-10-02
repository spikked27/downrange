#!/bin/bash
# Developer fallback. For GUI updates use the published latest image instead.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="/boot/config/plugins/dockerMan/templates-user"
if [[ ! -f /etc/unraid-version ]]; then echo "Run this on the Unraid host." >&2; exit 1; fi
command -v docker >/dev/null || { echo "Enable Docker in Unraid settings." >&2; exit 1; }
docker info >/dev/null
docker build --tag downrange-local:0.3.1-alpha.1 "$ROOT"
mkdir -p "$TEMPLATE_DIR"
TARGET="$TEMPLATE_DIR/my-Downrange-Local.xml"
if [[ -f "$TARGET" ]]; then
  echo "Existing template retained. Review its Repository tag before use."
else
  install -m 600 "$ROOT/templates/downrange-local.xml" "$TARGET"
fi
echo "Developer image built. Normal GUI updates use ghcr.io/spikked27/downrange:latest."
echo "No existing container or appdata was changed."
