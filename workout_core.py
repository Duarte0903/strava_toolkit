#!/usr/bin/env python3
"""
workout_core.py — GUI-free logic shared by the Strava exporter UI.

Responsibilities:
  * resolve an export (folder or .zip) to the folder holding the exercise CSV,
  * list workouts (fast, from the CSV only),
  * export a chosen workout to GPX or TCX, reusing samsung_to_gpx / samsung_to_tcx.

Kept free of tkinter so it can be tested headlessly.
"""

import os
import sys
import glob
import tempfile
import zipfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import samsung_to_tcx as tcx   # noqa: E402
import samsung_to_gpx as gpx   # noqa: E402


# --------------------------------------------------------------------------- #
# Resolving the export location
# --------------------------------------------------------------------------- #
def resolve_export(path):
    """Accept a folder or .zip; return (export_root, note). Raises ValueError."""
    path = os.path.abspath(os.path.expanduser(str(path).strip().strip('"').strip("'")))
    if not os.path.exists(path):
        raise ValueError("That path doesn't exist:\n" + path)

    note = ""
    if zipfile.is_zipfile(path):
        dest = os.path.join(tempfile.gettempdir(), "samsung_export_gui")
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(path) as z:
            z.extractall(dest)
        note = "Unzipped to a temporary folder."
        path = dest

    root = _find_root(path)
    if not root:
        raise ValueError(
            "Couldn't find Samsung workout data under:\n" + path +
            "\n\nExpected a 'com.samsung.health.exercise.*.csv' somewhere inside."
        )
    return root, note


def _find_root(path):
    if glob.glob(os.path.join(path, "com.samsung.health.exercise*.csv")):
        return path
    hits = glob.glob(os.path.join(path, "**", "com.samsung.health.exercise*.csv"), recursive=True)
    return os.path.dirname(hits[0]) if hits else None


# --------------------------------------------------------------------------- #
# Listing workouts (fast: reads only the CSV)
# --------------------------------------------------------------------------- #
def load_workouts(export_root):
    """Return (ex_dir, [workout dict, ...]) sorted newest-first."""
    ex_dir, csv_path = tcx.find_paths(export_root)
    items = []
    for row in tcx.read_exercise_csv(csv_path):
        ex_id = row.get("datauuid")
        if not ex_id:
            continue
        code = int(tcx.fnum(row.get("exercise_type")) or 0)
        dur_s = (tcx.fnum(row.get("duration")) or 0) / 1000.0
        dist_m = tcx.fnum(row.get("distance")) or 0.0
        hr = tcx.fnum(row.get("mean_heart_rate"))
        offset = tcx.fnum(row.get("time_offset")) or 0
        start = tcx.parse_csv_datetime(row.get("start_time"), offset)
        has_gps = bool((row.get("location_data") or "").strip())
        items.append({
            "id": ex_id,
            "row": row,
            "code": code,
            "label": tcx.label_for(code),
            "start": start,                       # epoch ms (UTC) or None
            "duration_s": dur_s,
            "distance_m": dist_m,
            "avg_hr": hr,
            "has_gps": has_gps,
        })
    items.sort(key=lambda x: x["start"] or 0, reverse=True)
    return ex_dir, items


# --------------------------------------------------------------------------- #
# Display helpers
# --------------------------------------------------------------------------- #
def fmt_date(start_ms):
    if not start_ms:
        return "—"
    return datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def fmt_duration(sec):
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return "{}:{:02d}:{:02d}".format(h, m, s) if h else "{}:{:02d}".format(m, s)


def fmt_distance(m):
    return "{:.2f} km".format(m / 1000.0) if m else "—"


# --------------------------------------------------------------------------- #
# Exporting one workout
# --------------------------------------------------------------------------- #
def _safe_name(start_ms, label, ex_id, ext):
    day = datetime.fromtimestamp((start_ms or 0) / 1000, tz=timezone.utc)
    return "{}_{}_{}.{}".format(day.strftime("%Y-%m-%d_%H%M"), label, ex_id[:8], ext)


def _load(ex_dir, ref):
    ref = (ref or "").strip()
    if not ref:
        return []
    p = os.path.join(ex_dir, ref + ".json")
    if os.path.exists(p):
        try:
            return tcx.load_json(p)
        except Exception:
            return []
    return []


def export_workout(ex_dir, item, out_dir, fmt="auto"):
    """
    Write one workout to out_dir. fmt: 'auto' | 'gpx' | 'tcx'.
    Returns (path, kind) on success, or (None, reason) if it couldn't be made.
    """
    row = item["row"]
    ex_id = item["id"]
    code = item["code"]
    start = item["start"]
    total_distance = item["distance_m"]
    has_gps = item["has_gps"]

    live_points = _load(ex_dir, row.get("live_data"))

    want_gpx = (fmt == "gpx") or (fmt == "auto" and has_gps)

    if want_gpx and has_gps:
        loc_points = _load(ex_dir, row.get("location_data"))
        merged = gpx.merge_location_hr(loc_points, live_points)
        label, gtype = gpx.LABEL.get(code, ("Workout", "other"))
        s = start or (merged[0]["start_time"] if merged else None)
        gpx_text, n = gpx.build_gpx(merged, "{} {}".format(label, tcx.iso(s)) if s else label, gtype)
        if gpx_text:
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, _safe_name(s, label, ex_id, "gpx"))
            with open(path, "w") as f:
                f.write(gpx_text)
            return path, "gpx"
        if fmt == "gpx":
            return None, "no GPS points"
        # auto: fall through to TCX

    if fmt == "gpx":
        return None, "no GPS"

    # TCX
    track, computed = tcx.build_track(live_points, total_distance)
    has_hr = any(tp["hr"] is not None for tp in track)
    if not track or (total_distance == 0 and not has_hr):
        return None, "no usable data"
    s = start or track[0]["t"]
    label = tcx.label_for(code)
    tcx_text = tcx.build_tcx(row, track, total_distance or computed, s)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, _safe_name(s, label, ex_id, "tcx"))
    with open(path, "w") as f:
        f.write(tcx_text)
    return path, "tcx"


# --------------------------------------------------------------------------- #
# Inspecting one workout (GUI-free; reused by the detail panel)
# --------------------------------------------------------------------------- #
def load_detail(ex_dir, item):
    """Build a fully-populated detail dict for a single workout item.

    Returns summary numbers plus time-series and route data ready to render:
      hr_series   : [(elapsed_s, bpm), ...]
      pace_series : [(elapsed_s, s_per_km), ...]  (derived from speed)
      route       : [(lat, lon), ...]             (empty when no GPS)

    Degrades gracefully — missing/unreadable data yields empty lists, never
    raises.
    """
    row = item["row"]
    live_points = _load(ex_dir, row.get("live_data"))
    track, _ = tcx.build_track(live_points, item["distance_m"])

    hr_series = []
    pace_series = []
    if track:
        t0 = track[0]["t"]
        for tp in track:
            elapsed = (tp["t"] - t0) / 1000.0
            if tp["hr"] is not None:
                hr_series.append((elapsed, float(tp["hr"])))
            sp = tp["speed"]
            if sp is not None and sp > 0:
                pace_series.append((elapsed, 1000.0 / sp))  # m/s -> s per km

    route = []
    if item["has_gps"]:
        for p in _load(ex_dir, row.get("location_data")):
            lat = tcx.fnum(p.get("latitude"))
            lon = tcx.fnum(p.get("longitude"))
            if lat is not None and lon is not None:
                route.append((lat, lon))

    dist_m = item["distance_m"]
    dur_s = item["duration_s"]
    avg_pace = (dur_s / (dist_m / 1000.0)) if dist_m else None

    return {
        "sport": item["label"],
        "date": fmt_date(item["start"]),
        "duration_s": dur_s,
        "distance_m": dist_m,
        "avg_hr": item["avg_hr"],
        "max_hr": tcx.fnum(row.get("max_heart_rate")),
        "calories": tcx.fnum(row.get("calorie")),
        "avg_pace_s_per_km": avg_pace,
        "has_gps": item["has_gps"],
        "hr_series": hr_series,
        "pace_series": pace_series,
        "route": route,
    }


def fmt_pace(s_per_km):
    """Format seconds-per-km as m:ss /km."""
    if not s_per_km or s_per_km <= 0:
        return "—"
    s = int(round(s_per_km))
    return "{}:{:02d} /km".format(s // 60, s % 60)


# Distinct sport labels present, for building a filter dropdown.
def sport_labels(items):
    return sorted({it["label"] for it in items})
