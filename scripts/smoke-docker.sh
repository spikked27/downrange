#!/bin/bash
# An isolated CI smoke test. Never points at real user's appdata or host ports.
set -euo pipefail
IMAGE="${1:-downrange-ci:test}"
NAME="downrange-smoke-${RANDOM}-${RANDOM}"
VOLUME="${NAME}-data"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; docker volume rm "$VOLUME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker volume create "$VOLUME" >/dev/null
docker run -d --name "$NAME" --init \
  -e ADMIN_PASSWORD="$(openssl rand -hex 20)" -e WORKER_ENABLED=false \
  -v "$VOLUME:/data" "$IMAGE" >/dev/null
ready() {
  for attempt in $(seq 1 30); do
    if docker exec "$NAME" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8097/healthz',timeout=2)" 2>/dev/null; then return 0; fi
    sleep 1
  done
  docker logs "$NAME"; return 1
}
ready
docker exec --user 99:100 "$NAME" python -c "from pathlib import Path; import os; p=Path('/data/downrange.sqlite3'); assert p.stat().st_uid==99; assert p.stat().st_mode & 0o777==0o600; assert Path('/data/vapid-private.pem').exists(); assert Path('/data/vapid-private.pem').stat().st_mode & 0o777==0o600"
KEY_BEFORE=$(docker exec "$NAME" python -c "import hashlib; print(hashlib.sha256(open('/data/vapid-private.pem','rb').read()).hexdigest())")
docker restart "$NAME" >/dev/null
ready
KEY_AFTER=$(docker exec "$NAME" python -c "import hashlib; print(hashlib.sha256(open('/data/vapid-private.pem','rb').read()).hexdigest())")
test "$KEY_BEFORE" = "$KEY_AFTER"
echo "Docker runtime smoke test passed. No live launch or push delivery was tested."
