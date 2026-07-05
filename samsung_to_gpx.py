#!/usr/bin/env python3
"""
samsung_to_gpx.py

Convert a Samsung Health data export into GPX files (GPS track + heart rate) that
you can upload to Strava for FREE at https://www.strava.com/upload/select.

Use this for workouts that HAVE GPS (recorded in an outdoor / GPS exercise mode).
For workouts WITHOUT GPS (heart rate + distance only), use samsung_to_tcx.py
instead — GPX needs coordinates and can't represent a mapless workout.

Usage:
  python3 samsung_to_gpx.py /path/to/unzipped/export
  python3 samsung_to_gpx.py /path/to/unzipped/export --since 2026-01-01 --out mygpx

Standard library only — nothing to install.
"""

import argparse
import csv
import glob
import gzip
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

# Samsung exercise_type -> (label, GPX <type> hint). GPX <type> is advisory;
# Strava lets you correct the sport afterward.
LABEL = {
    1001: ("Walk", "walking"),
    1002: ("Run", "running"),
    9001: ("Run", "running"),
    11007: ("Ride", "cycling"),
    13001: ("Hike", "hiking"),
    14001: ("Swim", "swimming"),
    15003: ("Ride", "cycling"),
    15004: ("Ride", "cycling"),
    0: ("Workout", "other"),
}


def load_json(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", errors="replace"))


def iso(unix_ms):
    return datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fnum(v):
    try:
        s = str(v).strip()
        return float(s) if s not in ("", "nan") else None
    except (TypeError, ValueError):
        return None


def find_paths(base):
    ex_dir = os.path.join(base, "jsons", "com.samsung.health.exercise")
    if not os.path.isdir(ex_dir):
        hits = glob.glob(os.path.join(base, "**", "com.samsung.health.exercise"), recursive=True)
        ex_dir = hits[0] if hits else None
    csvs = glob.glob(os.path.join(base, "com.samsung.health.exercise*.csv"))
    if not ex_dir or not csvs:
        sys.exit(
            "Couldn't find the exercise data. Point me at the UNZIPPED export folder "
            "(with 'com.samsung.health.exercise.*.csv' and a 'jsons/' folder)."
        )
    return ex_dir, csvs[0]


def read_exercise_csv(csv_path):
    with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
        first = f.readline()
        if not first.lower().startswith("com.samsung"):
            f.seek(0)
        yield from csv.DictReader(f)


def merge_location_hr(loc_points, live_points):
    """
    Combine GPS points (latitude/longitude/altitude/start_time) with heart-rate
    samples (from live_data) by timestamp, carrying the most recent HR forward
    onto each GPS point.
    """
    merged = {}
    for p in loc_points or []:
        t = p.get("start_time")
        if t is None:
            continue
        merged.setdefault(t, {}).update(p)
    for p in live_points or []:
        t = p.get("start_time")
        if t is None:
            continue
        hr = fnum(p.get("heart_rate"))
        if hr is not None:
            merged.setdefault(t, {})["heart_rate"] = hr

    rows = [merged[k] for k in sorted(merged.keys())]

    # carry HR forward onto GPS points that lack their own sample
    last_hr = None
    for r in rows:
        if r.get("heart_rate") is not None:
            last_hr = r["heart_rate"]
        elif last_hr is not None:
            r["heart_rate"] = last_hr
    return rows


def build_gpx(rows, name, gpx_type):
    gps = [r for r in rows if fnum(r.get("latitude")) is not None and fnum(r.get("longitude")) is not None]
    if not gps:
        return None, 0
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx creator="samsung_to_gpx" version="1.1" '
        'xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">',
        "<metadata><time>{}</time></metadata>".format(iso(gps[0]["start_time"])),
        "<trk>",
        "<name>{}</name>".format(name),
        "<type>{}</type>".format(gpx_type),
        "<trkseg>",
    ]
    n = 0
    for r in gps:
        out.append('<trkpt lat="{}" lon="{}">'.format(fnum(r["latitude"]), fnum(r["longitude"])))
        out.append("<time>{}</time>".format(iso(r["start_time"])))
        alt = fnum(r.get("altitude"))
        if alt is not None:
            out.append("<ele>{:.1f}</ele>".format(alt))
        hr = fnum(r.get("heart_rate"))
        if hr is not None:
            out.append(
                "<extensions><gpxtpx:TrackPointExtension>"
                "<gpxtpx:hr>{:.0f}</gpxtpx:hr>"
                "</gpxtpx:TrackPointExtension></extensions>".format(hr)
            )
        out.append("</trkpt>")
        n += 1
    out.extend(["</trkseg>", "</trk>", "</gpx>"])
    return "\n".join(out), n


def main():
    ap = argparse.ArgumentParser(description="Samsung Health export -> GPX (GPS + heart rate)")
    ap.add_argument("export_dir", help="Path to the UNZIPPED Samsung Health export folder")
    ap.add_argument("--out", default=os.path.join(HERE, "gpx_out"), help="Output folder for .gpx files")
    ap.add_argument("--since", help="Only workouts on/after this date, e.g. 2026-01-01")
    ap.add_argument("--min-points", type=int, default=2, help="Minimum GPS points to keep a track")
    args = ap.parse_args()

    since_ms = None
    if args.since:
        since_ms = int(datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    ex_dir, csv_path = find_paths(args.export_dir)
    os.makedirs(args.out, exist_ok=True)

    made = no_gps = 0
    for row in read_exercise_csv(csv_path):
        ex_id = row.get("datauuid")
        if not ex_id:
            continue

        loc_ref = (row.get("location_data") or "").strip()
        if not loc_ref:
            no_gps += 1
            continue  # no GPS track for this workout

        loc_path = os.path.join(ex_dir, loc_ref + ".json")
        if not os.path.exists(loc_path):
            no_gps += 1
            continue
        try:
            loc_points = load_json(loc_path)
        except Exception as e:
            print("  ! could not read {}: {}".format(os.path.basename(loc_path), e))
            no_gps += 1
            continue

        live_ref = (row.get("live_data") or "").strip()
        live_points = []
        if live_ref:
            lp = os.path.join(ex_dir, live_ref + ".json")
            if os.path.exists(lp):
                try:
                    live_points = load_json(lp)
                except Exception:
                    pass

        rows_merged = merge_location_hr(loc_points, live_points)
        gps = [r for r in rows_merged if fnum(r.get("latitude")) is not None]
        if len(gps) < args.min_points:
            no_gps += 1
            continue

        start = gps[0]["start_time"]
        if since_ms and start < since_ms:
            continue

        code = int(fnum(row.get("exercise_type")) or 0)
        label, gpx_type = LABEL.get(code, ("Workout", "other"))
        gpx, n = build_gpx(rows_merged, "{} {}".format(label, iso(start)), gpx_type)
        if not gpx:
            no_gps += 1
            continue

        day = datetime.fromtimestamp(start / 1000, tz=timezone.utc)
        fname = "{}_{}_{}.gpx".format(day.strftime("%Y-%m-%d_%H%M"), label, ex_id[:8])
        with open(os.path.join(args.out, fname), "w") as f:
            f.write(gpx)
        made += 1
        print("Converted {} {}  ({} GPS pts)".format(label, day.strftime("%Y-%m-%d"), n))

    print("\nCreated {} GPX files in: {}".format(made, args.out))
    if made == 0:
        print(
            "\nNo workouts in this export had GPS coordinates, so no GPX could be made.\n"
            "For heart-rate / distance workouts without GPS, use samsung_to_tcx.py instead."
        )
    else:
        print("Next: open https://www.strava.com/upload/select and drag in the .gpx files.")
    if no_gps:
        print("({} workouts skipped for having no GPS track.)".format(no_gps))


if __name__ == "__main__":
    main()
