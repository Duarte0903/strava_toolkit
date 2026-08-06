#!/usr/bin/env python3
"""
samsung_export.py — locate and normalise a Samsung Health "download my data"
export, hiding the differences between the layouts Samsung has shipped.

Two layouts exist in the wild and this module makes them look identical to the
converters:

                        legacy                     current
  exercise CSV          com.samsung.health.        com.samsung.shealth.
                        exercise.<n>.csv           exercise.<n>.csv
  column names          duration, start_time, ...  com.samsung.health.exercise.duration, ...
  live_data cell        <uuid>.live_data           <uuid>.com.samsung.health.exercise.live_data.json
  json folder           jsons/com.samsung.         jsons/com.samsung.shealth.exercise/<hex>/
                        health.exercise/
  time_offset           7200000 (milliseconds)     "UTC+0200"
  start_time            local wall clock           UTC

The last row matters: in the legacy export start_time is local and time_offset
has to be subtracted to reach UTC, whereas the current export already stores
UTC and time_offset only says which local time the user saw. Getting this wrong
shifts every workout by a few hours, so the two are handled separately.

Standard library only.
"""

import csv
import glob
import gzip
import json
import os
import re
from datetime import datetime, timezone

# The exercise table itself, not its satellites (…exercise.weather.<n>.csv,
# …exercise.route.<n>.csv, …), which share the same stem.
_EXERCISE_CSV_RE = re.compile(r"^com\.samsung\.s?health\.exercise(\.\d+)?\.csv$", re.I)

# Column prefix used by the current export, e.g.
# "com.samsung.health.exercise.mean_heart_rate" -> "mean_heart_rate".
_COLUMN_PREFIX_RE = re.compile(r"^com\.samsung\.s?health\.exercise\.", re.I)

# time_offset as written by the current export: "UTC+0200", "UTC-0730", "UTC".
_UTC_OFFSET_RE = re.compile(r"^\s*UTC\s*(?:([+-])(\d{2}):?(\d{2}))?\s*$", re.I)

_JSON_DIR_NAMES = ("com.samsung.shealth.exercise", "com.samsung.health.exercise")


class ExportFormatError(Exception):
    """Raised when a folder doesn't look like a Samsung Health export."""


NOT_AN_EXPORT = (
    "Couldn't find the exercise data. Point me at the UNZIPPED export folder — "
    "the one holding 'com.samsung.health.exercise.*.csv' (or "
    "'com.samsung.shealth.exercise.*.csv') and a 'jsons/' folder."
)


# --------------------------------------------------------------------------- #
# Locating things
# --------------------------------------------------------------------------- #
def find_exercise_csv(base):
    """Return the path to the exercise CSV under `base`, or None."""
    direct = [e.path for e in _scandir(base) if e.is_file() and _EXERCISE_CSV_RE.match(e.name)]
    if direct:
        return sorted(direct)[0]

    hits = []
    for path in glob.glob(os.path.join(base, "**", "com.samsung.*exercise*.csv"), recursive=True):
        if _EXERCISE_CSV_RE.match(os.path.basename(path)):
            hits.append(path)
    return sorted(hits)[0] if hits else None


def find_exercise_json_dir(base):
    """Return the folder holding the per-workout live/location JSON, or None."""
    for name in _JSON_DIR_NAMES:
        candidate = os.path.join(base, "jsons", name)
        if os.path.isdir(candidate):
            return candidate
    for name in _JSON_DIR_NAMES:
        hits = [p for p in glob.glob(os.path.join(base, "**", name), recursive=True)
                if os.path.isdir(p)]
        if hits:
            return sorted(hits)[0]
    return None


def find_root(path):
    """Return the folder containing the exercise CSV, or None."""
    csv_path = find_exercise_csv(path)
    return os.path.dirname(csv_path) if csv_path else None


def find_paths(base):
    """Return (json_dir, csv_path). Raises ExportFormatError if either is missing."""
    csv_path = find_exercise_csv(base)
    json_dir = find_exercise_json_dir(base)
    if not csv_path or not json_dir:
        raise ExportFormatError(NOT_AN_EXPORT)
    return json_dir, csv_path


def _scandir(path):
    try:
        return list(os.scandir(path))
    except OSError:
        return []


# --------------------------------------------------------------------------- #
# Reading the exercise CSV
# --------------------------------------------------------------------------- #
def normalise_row(row):
    """Strip the 'com.samsung.health.exercise.' column prefix.

    Original keys are kept too, so callers that know the long names still work.
    A prefixed column never overwrites a plain column of the same name.
    """
    out = dict(row)
    for key, value in row.items():
        if not isinstance(key, str):
            continue
        short = _COLUMN_PREFIX_RE.sub("", key)
        if short != key and short not in row:
            out[short] = value
    return out


def read_exercise_csv(csv_path):
    """Yield normalised dict rows from the exercise CSV.

    Samsung prefixes the file with a junk line naming the data type; skip it.
    """
    with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
        first = f.readline()
        if not first.lower().startswith("com.samsung"):
            f.seek(0)  # no junk line, rewind
        for row in csv.DictReader(f):
            yield normalise_row(row)


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #
def tz_offset_ms(raw):
    """Local UTC offset of a workout, in milliseconds (0 when unknown).

    Accepts both the legacy numeric milliseconds and the current "UTC+0200".
    """
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)

    text = str(raw).strip()
    if not text:
        return 0

    m = _UTC_OFFSET_RE.match(text)
    if m:
        if not m.group(1):
            return 0  # plain "UTC"
        sign = -1 if m.group(1) == "-" else 1
        return sign * (int(m.group(2)) * 3600 + int(m.group(3)) * 60) * 1000

    try:
        return int(float(text))
    except ValueError:
        return 0


def _timestamps_are_utc(raw_offset):
    """True when start_time is already UTC (current export), False for legacy.

    The current export writes time_offset as "UTC+0200" and stores UTC
    timestamps; the legacy one writes plain milliseconds and stores local time.
    """
    return isinstance(raw_offset, str) and bool(_UTC_OFFSET_RE.match(raw_offset.strip()))


def parse_csv_datetime(s, time_offset=0):
    """Parse the CSV's start_time into a UTC epoch in milliseconds.

    `time_offset` is the row's raw time_offset cell (either format).
    """
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y, %H:%M:%S", "%m/%d/%Y, %H:%M:%S"):
        try:
            dt = datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
        naive_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        if _timestamps_are_utc(time_offset):
            return naive_ms
        return naive_ms - tz_offset_ms(time_offset)
    return None


# --------------------------------------------------------------------------- #
# Per-workout JSON payloads
# --------------------------------------------------------------------------- #
_INDEX_CACHE = {}


def _json_index(json_dir):
    """Lazily map every JSON basename under `json_dir` to its full path.

    The current export shards files into single-hex-character subfolders, so a
    flat join isn't enough. Names are indexed with and without the .json suffix
    because the CSV cell includes it in one layout and not the other.
    """
    cached = _INDEX_CACHE.get(json_dir)
    if cached is not None:
        return cached

    index = {}
    for dirpath, _dirnames, filenames in os.walk(json_dir):
        for name in filenames:
            if not name.lower().endswith(".json"):
                continue
            full = os.path.join(dirpath, name)
            index.setdefault(name, full)
            index.setdefault(name[: -len(".json")], full)
    _INDEX_CACHE[json_dir] = index
    return index


def clear_json_index(json_dir=None):
    """Forget cached directory listings (tests, or a re-imported export)."""
    if json_dir is None:
        _INDEX_CACHE.clear()
    else:
        _INDEX_CACHE.pop(json_dir, None)


def resolve_json(json_dir, ref):
    """Turn a CSV live_data / location_data cell into a readable path, or None."""
    ref = (ref or "").strip()
    if not ref or not json_dir:
        return None

    # Cheap hits first, so an untouched legacy export never triggers a walk.
    candidates = [ref, ref + ".json"]
    if ref[0].isalnum():
        candidates += [os.path.join(ref[0], ref), os.path.join(ref[0], ref + ".json")]
    for candidate in candidates:
        path = os.path.join(json_dir, candidate)
        if os.path.isfile(path):
            return path

    index = _json_index(json_dir)
    return index.get(ref) or index.get(ref + ".json")


def load_json(path):
    """Read a JSON payload; Samsung gzips some of them without changing the name."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", errors="replace"))


def load_points(json_dir, ref):
    """Load a live_data / location_data payload, or [] if absent or unreadable."""
    path = resolve_json(json_dir, ref)
    if not path:
        return []
    try:
        points = load_json(path)
    except Exception:
        return []
    return points if isinstance(points, list) else []
