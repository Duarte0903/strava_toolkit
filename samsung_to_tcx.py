#!/usr/bin/env python3
"""
samsung_to_tcx.py

Convert a Samsung Health data export into TCX files you can upload to Strava for
FREE (drag-and-drop at https://www.strava.com/upload/select) — no Strava API,
no subscription, no OAuth.

Why TCX (not GPX)?  This export contains NO GPS coordinates — the watch stored
each workout as time-series heart rate / speed / distance only. TCX carries all
of that without a map; Strava will show distance, pace, duration and a heart-rate
graph. (GPX is a map format and would be empty here.)

Usage:
  python3 samsung_to_tcx.py /path/to/unzipped/export
  python3 samsung_to_tcx.py /path/to/unzipped/export --out mytcx --since 2025-01-01

Then go to https://www.strava.com/upload/select and drag in the .tcx files.
Standard library only — nothing to install.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import samsung_export as sx  # noqa: E402

# Re-exported so the GUI and the older call sites keep working unchanged.
load_json = sx.load_json
read_exercise_csv = sx.read_exercise_csv
parse_csv_datetime = sx.parse_csv_datetime
tz_offset_ms = sx.tz_offset_ms
load_points = sx.load_points

# Samsung exercise_type -> (label for the activity name, TCX Sport attribute).
# TCX Sport only allows Running / Biking / Other; Strava maps those to
# Run / Ride / Workout. Fix the exact sport on Strava afterward if you like.
RUNNING = {1002, 9001, 1002}
BIKING = {11007, 15003, 15004, 15005, 15006}
LABEL = {
    1001: "Walk",
    1002: "Run",
    9001: "Run",
    11007: "Ride",
    13001: "Hike",
    15003: "Ride",
    15004: "Ride",
    14001: "Swim",
    0: "Workout",
}


def sport_for(code):
    if code in RUNNING:
        return "Running"
    if code in BIKING:
        return "Biking"
    return "Other"


def label_for(code):
    return LABEL.get(code, "Workout")


def iso(unix_ms):
    return datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def fnum(v):
    try:
        s = str(v).strip()
        return float(s) if s not in ("", "nan") else None
    except (TypeError, ValueError):
        return None


def find_paths(base):
    try:
        return sx.find_paths(base)
    except sx.ExportFormatError as e:
        sys.exit(str(e))


def build_track(points, total_distance):
    """
    Merge the live_data samples (each has some of: heart_rate, speed, distance,
    cadence, start_time) into a clean per-timestamp track with a monotonically
    increasing cumulative distance. Returns (trackpoints, computed_total).

    trackpoints: list of dicts {t, dist, hr, speed, cad}
    """
    pts = sorted((p for p in points if p.get("start_time")), key=lambda p: p["start_time"])
    if not pts:
        return [], 0.0

    have_native_dist = any("distance" in p and fnum(p.get("distance")) is not None for p in pts)

    track = []
    cum = 0.0
    last_speed = 0.0
    last_hr = None
    last_cad = None
    prev_t = None

    for p in pts:
        t = p["start_time"]
        hr = fnum(p.get("heart_rate"))
        sp = fnum(p.get("speed"))
        cad = fnum(p.get("cadence"))
        nd = fnum(p.get("distance"))

        if hr is not None:
            last_hr = hr
        if cad is not None:
            last_cad = cad

        if have_native_dist:
            # Samsung's per-point "distance" is an incremental delta, not a
            # running total, so accumulate it.
            if nd is not None:
                cum += nd
        else:
            # integrate speed (m/s) over the elapsed interval
            if prev_t is not None:
                dt = (t - prev_t) / 1000.0
                if dt > 0:
                    cum += last_speed * dt
            if sp is not None:
                last_speed = sp
        prev_t = t

        track.append({"t": t, "dist": cum, "hr": last_hr, "speed": sp, "cad": last_cad})

    computed = track[-1]["dist"] if track else 0.0

    # If we synthesized distance and we know the real total, scale to match so
    # pace/distance are accurate.
    if not have_native_dist and total_distance and computed > 0:
        factor = total_distance / computed
        for tp in track:
            tp["dist"] *= factor
        computed = total_distance

    return track, computed


def xml_escape(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_tcx(row, track, total_distance, start_ms):
    dur_s = (fnum(row.get("duration")) or 0) / 1000.0
    cal = fnum(row.get("calorie"))
    mean_hr = fnum(row.get("mean_heart_rate"))
    max_hr = fnum(row.get("max_heart_rate"))
    code = int(fnum(row.get("exercise_type")) or 0)
    sport = sport_for(code)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TrainingCenterDatabase '
        'xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2" '
        'xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 '
        'http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd">',
        "<Activities>",
        '<Activity Sport="{}">'.format(sport),
        "<Id>{}</Id>".format(iso(start_ms)),
        '<Lap StartTime="{}">'.format(iso(start_ms)),
        "<TotalTimeSeconds>{:.0f}</TotalTimeSeconds>".format(dur_s),
        "<DistanceMeters>{:.2f}</DistanceMeters>".format(total_distance or 0.0),
    ]
    if cal is not None:
        out.append("<Calories>{:.0f}</Calories>".format(cal))
    if mean_hr is not None:
        out.append("<AverageHeartRateBpm><Value>{:.0f}</Value></AverageHeartRateBpm>".format(mean_hr))
    if max_hr is not None:
        out.append("<MaximumHeartRateBpm><Value>{:.0f}</Value></MaximumHeartRateBpm>".format(max_hr))
    out.append("<Intensity>Active</Intensity>")
    out.append("<TriggerMethod>Manual</TriggerMethod>")
    out.append("<Track>")

    for tp in track:
        out.append("<Trackpoint>")
        out.append("<Time>{}</Time>".format(iso(tp["t"])))
        out.append("<DistanceMeters>{:.2f}</DistanceMeters>".format(tp["dist"]))
        if tp["hr"] is not None:
            out.append("<HeartRateBpm><Value>{:.0f}</Value></HeartRateBpm>".format(tp["hr"]))
        if tp["cad"] is not None and code in BIKING:
            out.append("<Cadence>{:.0f}</Cadence>".format(min(tp["cad"], 254)))
        if tp["speed"] is not None:
            out.append(
                "<Extensions><ns3:TPX><ns3:Speed>{:.3f}</ns3:Speed></ns3:TPX></Extensions>".format(
                    tp["speed"]
                )
            )
        out.append("</Trackpoint>")

    out.extend(["</Track>", "</Lap>", "</Activity>", "</Activities>", "</TrainingCenterDatabase>"])
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Samsung Health export -> TCX (for free manual Strava upload)")
    ap.add_argument("export_dir", help="Path to the UNZIPPED Samsung Health export folder")
    ap.add_argument("--out", default=os.path.join(HERE, "tcx_out"), help="Output folder for .tcx files")
    ap.add_argument("--since", help="Only workouts on/after this date, e.g. 2025-01-01")
    ap.add_argument("--min-duration", type=int, default=60, help="Skip workouts shorter than N seconds (default 60)")
    ap.add_argument("--skip-gps", action="store_true",
                    help="Skip workouts that have a GPS track (let samsung_to_gpx.py handle those)")
    args = ap.parse_args()

    since_ms = None
    if args.since:
        since_ms = int(datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    ex_dir, csv_path = find_paths(args.export_dir)
    os.makedirs(args.out, exist_ok=True)

    made = skipped_short = skipped_empty = skipped_old = 0
    for row in read_exercise_csv(csv_path):
        ex_id = row.get("datauuid")
        if not ex_id:
            continue

        if args.skip_gps and (row.get("location_data") or "").strip():
            continue  # has GPS -> handled by samsung_to_gpx.py

        # live_data time series (the column names a JSON file next to the CSV)
        points = sx.load_points(ex_dir, row.get("live_data"))

        total_distance = fnum(row.get("distance")) or 0.0
        track, computed = build_track(points, total_distance)

        # Start time: prefer the unambiguous epoch from live_data; else parse
        # the CSV's local date string (adjusting for its time_offset).
        if track:
            start = track[0]["t"]
        else:
            start = parse_csv_datetime(row.get("start_time"), row.get("time_offset"))
        if start is None:
            continue

        if since_ms and start < since_ms:
            skipped_old += 1
            continue
        dur_s = (fnum(row.get("duration")) or 0) / 1000.0
        if dur_s < args.min_duration:
            skipped_short += 1
            continue

        # Need at least some data to make a meaningful activity.
        has_hr = any(tp["hr"] is not None for tp in track)
        if not track or (total_distance == 0 and not has_hr):
            skipped_empty += 1
            continue

        tcx = build_tcx(row, track, total_distance or computed, start)
        label = label_for(int(fnum(row.get("exercise_type")) or 0))
        day = datetime.fromtimestamp(start / 1000, tz=timezone.utc)
        fname = "{}_{}_{}.tcx".format(day.strftime("%Y-%m-%d_%H%M"), label, ex_id[:8])
        with open(os.path.join(args.out, fname), "w") as f:
            f.write(tcx)
        made += 1

    print("\nCreated {} TCX files in: {}".format(made, args.out))
    print("Skipped: {} too short, {} no usable data, {} before --since".format(
        skipped_short, skipped_empty, skipped_old))
    print("\nNext: open https://www.strava.com/upload/select and drag in the .tcx files")
    print("(Strava lets you multi-select; upload in batches if you have a lot.)")


if __name__ == "__main__":
    main()
