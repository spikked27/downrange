#!/bin/bash
# New-install helper; existing installations need only a GUI Repository edit.
set -euo pipefail
[[ -f /etc/unraid-version ]] || { echo "Run this in the Unraid host terminal." >&2; exit 1; }
for cmd in docker curl; do command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }; done
IMAGE="ghcr.io/spikked27/downrange:latest"
BASE="https://raw.githubusercontent.com/spikked27/downrange/main"
if ! docker pull "$IMAGE"; then
  echo "Image unavailable. Check GitHub Actions and that the GHCR package is Public."
  exit 1
fi
DIR="/boot/config/plugins/dockerMan/templates-user"
mkdir -p "$DIR"
TARGET="$DIR/my-Downrange.xml"
if [[ -f "$TARGET" ]]; then
  echo "Existing template retained. To enable GUI updates, edit its Repository to $IMAGE."
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
echo "Ready: Docker -> Add Container -> Template: Downrange. Existing users: edit the existing container instead."
echo "Do not run two containers against the same appdata. Future updates use the Unraid GUI."
