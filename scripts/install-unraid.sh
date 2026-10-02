#!/bin/bash
# Standalone registry-template installer. Never creates or changes a container.
set -euo pipefail
[[ -f /etc/unraid-version ]] || { echo "Run this in the Unraid host terminal." >&2; exit 1; }
for cmd in docker curl; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done
IMAGE="ghcr.io/spikked27/downrange:0.2.0-alpha.1"
BASE="https://raw.githubusercontent.com/spikked27/downrange/main"
if ! docker pull "$IMAGE"; then
  echo "Image unavailable. Check the GitHub Actions build and GHCR package visibility."
  echo "The package must be public for this anonymous installation."
  echo "Local-build fallback: download the repository and run scripts/install-unraid-local.sh."
  exit 1
fi
DIR="/boot/config/plugins/dockerMan/templates-user"
mkdir -p "$DIR"
TARGET="$DIR/my-Downrange.xml"
if [[ -f "$TARGET" ]]; then
  echo "Existing template retained, including your settings: $TARGET"
else
  TMP=$(mktemp "$DIR/.downrange-template.XXXXXX")
  trap 'rm -f "$TMP"' EXIT
  curl --fail --silent --show-error --location --retry 3 "$BASE/templates/downrange.xml" -o "$TMP"
  grep -q '<Container version="2">' "$TMP"
  grep -q '<Name>Downrange</Name>' "$TMP"
  grep -q '</Container>' "$TMP"
  chmod 600 "$TMP"
  mv "$TMP" "$TARGET"
fi
echo "Ready: Docker -> Add Container -> Template: Downrange."
echo "Set a 12+ character admin password, review port 8097 and appdata, then Apply."
echo "Start with the LAN WebUI. Add HTTPS before enabling phone notifications."
