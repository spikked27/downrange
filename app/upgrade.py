"""Consistent pre-upgrade snapshots of appdata; never reset existing accounts."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import sqlite3
from . import __version__


def protect_existing_data(data_dir: Path) -> Path | None:
    database = data_dir / 'downrange.sqlite3'
    if not database.exists():
        return None
    # A snapshot covers database contents including committed WAL data. It is
    # not made by copying a live SQLite file. No source network access occurs.
    import fcntl
    lock_path = data_dir / 'upgrade.lock'
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with sqlite3.connect(database, timeout=30) as source:
            row = source.execute("SELECT value FROM meta WHERE key='application_version'").fetchone()
            prior = json.loads(row[0]) if row else 'legacy'
            if prior == __version__:
                return None
            directory = data_dir / 'backups' / ('before-' + __version__)
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.parent.chmod(0o700)
            directory.chmod(0o700)
            completed = directory / 'snapshot.json'
            if completed.exists():
                return directory
            target = directory / 'downrange.sqlite3'
            # Preserve the earliest successfully completed snapshot per release.
            with sqlite3.connect(target, timeout=30) as snapshot:
                source.backup(snapshot)
            target.chmod(0o600)
            key = data_dir / 'vapid-private.pem'
            if key.exists():
                shutil.copyfile(key, directory / key.name)
                (directory / key.name).chmod(0o600)
            completed.write_text(json.dumps({'from': prior, 'to': __version__,
                'contents': 'SQLite consistent backup and persistent VAPID key',
                'restore': 'Stop container before restoring database and key. Never restore over a running database.'}, indent=2))
            completed.chmod(0o600)
            return directory


def record_version(store) -> None:
    store.set_meta('application_version', __version__)
