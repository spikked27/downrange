#!/bin/sh
set -eu
umask 077
: "${DATA_DIR:=/data}" "${PUID:=99}" "${PGID:=100}"
case "$PUID:$PGID" in *[!0-9:]*|:*|*:) echo "PUID and PGID must be numeric" >&2; exit 1;; esac
mkdir -p "$DATA_DIR"
if [ "$(id -u)" = 0 ]; then
    chown "$PUID:$PGID" "$DATA_DIR"
    chmod 700 "$DATA_DIR"
    for file in "$DATA_DIR"/downrange.sqlite3 "$DATA_DIR"/downrange.sqlite3-wal "$DATA_DIR"/downrange.sqlite3-shm "$DATA_DIR"/vapid-private.pem "$DATA_DIR"/worker.lock; do
        if [ -f "$file" ] && [ ! -L "$file" ]; then chown "$PUID:$PGID" "$file"; chmod 600 "$file"; fi
    done
    exec gosu "$PUID:$PGID" "$@"
fi
exec "$@"
