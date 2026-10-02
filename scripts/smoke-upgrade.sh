#!/bin/bash
# Test replacing the previous published image against isolated CI data only.
set -euo pipefail
NEW_IMAGE="${1:-downrange-ci:test}"
OLD_IMAGE="${2:-ghcr.io/spikked27/downrange:0.2.0-alpha.1}"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="downrange-upgrade-${RANDOM}-${RANDOM}"
VOLUME="${NAME}-data"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; docker volume rm "$VOLUME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker pull "$OLD_IMAGE"
docker volume create "$VOLUME" >/dev/null
wait_ready() {
  for attempt in $(seq 1 40); do
    if docker exec "$NAME" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8097/healthz',timeout=2)" 2>/dev/null; then return; fi
    sleep 1
  done
  docker logs "$NAME"; return 1
}
start() {
  docker run -d --name "$NAME" --init \
    -e ADMIN_PASSWORD="$(openssl rand -hex 24)" -e WORKER_ENABLED=false -e SOURCES_ENABLED=false \
    -v "$VOLUME:/data" "$1" >/dev/null
  wait_ready
}
start "$OLD_IMAGE"
docker exec -i --user 99:100 "$NAME" python - seed < "$ROOT/scripts/upgrade-fixture.py"
docker stop "$NAME" >/dev/null
docker rm "$NAME" >/dev/null
start "$NEW_IMAGE"
VERSION=$(docker exec "$NAME" python -c 'from app import __version__; print(__version__)')
docker exec -i --user 99:100 -e EXPECTED_VERSION="$VERSION" "$NAME" python - check < "$ROOT/scripts/upgrade-fixture.py"
