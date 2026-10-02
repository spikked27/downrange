#!/bin/bash
# Use only AFTER the GitHub workflow has published the public image.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f /etc/unraid-version ]]; then echo "Run on the Unraid host." >&2; exit 1; fi
IMAGE="ghcr.io/spikked27/downrange:0.2.0-alpha.1"
docker pull "$IMAGE" || { echo "Image is not available publicly yet. Use the local installer, or finish GHCR publication." >&2; exit 1; }
DIR="/boot/config/plugins/dockerMan/templates-user"; mkdir -p "$DIR"
if [[ -f "$DIR/my-Downrange.xml" ]]; then echo "Existing template retained."; else install -m 600 "$ROOT/templates/downrange.xml" "$DIR/my-Downrange.xml"; fi
echo "Docker → Add Container → Template: Downrange → review settings → Apply."
echo "Do not run alongside Downrange-Local using the same appdata or port."
