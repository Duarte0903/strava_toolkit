# Strava Toolkit — Samsung Health → Strava (free, no API)

Convert a **Samsung Health / Galaxy Watch** workout export into **TCX/GPX** files
you can upload to Strava **for free** — no Strava API, no paid subscription, no
OAuth. There's a Python desktop app, a set of command-line converters, and a
native iOS app.

## Why this exists

**Tizen OS (Galaxy Watch) no longer supports the Strava app**, so workouts
recorded on the watch can't sync to Strava directly anymore. The way to keep your
Strava integration is to **log workouts in the native Samsung Health app and
export them manually** — which is exactly what this toolkit automates. It's a
fully **manual, cost-free** method: Strava's API now needs a paid subscription,
but manual file upload at
[strava.com/upload/select](https://www.strava.com/upload/select) is free.

Samsung exports store each workout as time-series **heart rate, speed, cadence
and distance** (plus **GPS** when the workout was recorded outdoors).

- Workouts **without** GPS → **TCX** (distance + heart-rate activity, no map).
- Workouts **with** GPS → **GPX** (route map + heart rate).

## Repository layout

```
.
├── strava_gui.py            Desktop app (Tkinter) — pick workouts from a list, export
├── workout_core.py          Shared, GUI-free logic used by the app
├── export_log.py            Tracks which workouts were already exported
├── samsung_to_tcx.py        CLI converter → TCX (no-GPS workouts)
├── samsung_to_gpx.py        CLI converter → GPX (GPS workouts)
├── strava_sync.py           CLI menu launcher (auto-picks TCX/GPX per workout)
├── Run Strava Exporter (Mac).command / (Windows).bat   Double-click launchers
├── test_workout_core.py     Tests (stdlib unittest)
├── test_export_log.py       Tests (stdlib unittest)
├── ios/                     Native iOS app + Swift core package  (see ios/README.md)
└── docs/superpowers/specs/  Design specs
```

## Desktop app

Needs **Python 3 with Tk** (bundled in the python.org installers for macOS/
Windows; on Linux: `sudo apt install python3-tk`). Nothing else to install.

- **macOS:** double-click **`Run Strava Exporter (Mac).command`**
- **Windows:** double-click **`Run Strava Exporter (Windows).bat`**
- **Any system:** `python3 strava_gui.py`

In the window:

1. **Open export…** and choose your `.zip` or unzipped export folder.
2. Workouts load in a list (date, type, duration, distance, avg HR, GPS). Filter
   by **Type**, a **Since** date, or free-text **Search**; tick **Hide exported**
   to drop ones you've already sent.
3. Click a workout to **inspect** it (stats, heart-rate & pace charts, GPS route).
4. **Tick** the workouts you want (or **Select shown**), pick a **Format**
   (*Auto* = GPX when GPS is present, otherwise TCX), choose an **Output** folder,
   and click **Export selected**.
5. Upload the exported files at
   [strava.com/upload/select](https://www.strava.com/upload/select) (a free Strava
   account is fine — manual upload doesn't need the paid API).

## Command-line converters

Point the menu launcher at an export (a folder **or** a `.zip` — it unzips for you):

```
python3 strava_sync.py /path/to/DownloadPersonalData_XXXX.zip
```

Option 1 ("Convert everything") writes GPX for GPS workouts and TCX for the rest
into a `strava_upload/` folder next to your export, with no duplicates.

Or run a single converter directly:

| Command | What it does |
|---|---|
| `python3 samsung_to_tcx.py EXPORT` | Convert all workouts to TCX in `tcx_out/`. |
| `... EXPORT --since 2026-01-01` | Only workouts on/after that date. |
| `... EXPORT --out FOLDER` | Write files somewhere else. |
| `... EXPORT --min-duration 120` | Skip workouts shorter than 120 s. |
| `python3 samsung_to_gpx.py EXPORT` | Convert GPS workouts to GPX in `gpx_out/`. |

## iOS app

A native iPhone version (import the export `.zip`, inspect workouts, save TCX/GPX
into Files for manual upload) lives under [`ios/`](ios/README.md). Its conversion
core is tested; the SwiftUI app builds in Xcode. See that README for build/run
and how the app icon is generated.

## Getting a Samsung Health export

On the phone: **Samsung Health → Settings → Download personal data**, or via
**[privacy.samsung.com](https://privacy.samsung.com) → Download your data**. Then
feed the `.zip` (or the unzipped folder) to any tool above.

## Development

```
# Python tests (stdlib unittest — nothing to install)
python3 -m unittest test_workout_core test_export_log

# Swift core package: headless verification (no Xcode needed)
cd ios/StravaToolkitKit && swift run stkcheck Tests/StravaToolkitKitTests/Fixtures
```

## Notes

- **Sports:** TCX only supports Running/Biking/Other, so e.g. walks arrive as
  "Workout" — change the sport on Strava in one click. Runs and rides are detected
  automatically.
- **Time zone:** activity times come from the watch's recorded timestamps; Strava
  shows them in your account's time zone.
- **Maps:** a workout can only have a route if GPS was on when it was recorded
  (outdoor exercise mode). History can't gain a map it never captured.
