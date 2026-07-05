#!/usr/bin/env python3
"""
export_log.py — remembers which workouts have already been exported.

State lives in a single central file (`~/.strava_toolkit/exported.json`), a flat
map of Samsung `datauuid` -> export date ("YYYY-MM-DD"). Samsung ids are globally
unique, so a central file is safe.

GUI-free so it can be tested headlessly. Every function accepts an optional
`path` (defaulting to the home-dir file) so tests can use a temp file.
"""

import json
import os
import tempfile
from datetime import date

DEFAULT_PATH = os.path.join(os.path.expanduser("~"), ".strava_toolkit", "exported.json")


def load_log(path=None):
    """Return the exported map. Missing/unreadable/corrupt file -> {} (never raises)."""
    path = path or DEFAULT_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def mark_exported(ids, path=None):
    """Merge `ids` into the log with today's date and write it back atomically.

    Creates the parent directory if needed. Re-marking an existing id refreshes
    its date; other entries are preserved. Returns the updated map.
    """
    path = path or DEFAULT_PATH
    log = load_log(path)
    today = date.today().isoformat()
    for i in ids:
        log[i] = today

    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".exported-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, sort_keys=True)
        os.replace(tmp, path)          # atomic on the same filesystem
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return log


def is_exported(log, workout_id):
    """Convenience predicate."""
    return workout_id in log
