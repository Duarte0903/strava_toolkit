# Samsung → Strava iOS App — Design

Date: 2026-07-05
New component: `ios/` (Swift package + SwiftUI app)

## Goal

A native iPhone app that mirrors the desktop flow: import a Samsung Health
export `.zip`, browse/inspect workouts, and export selected ones to TCX/GPX saved
into the phone's Files, so the user uploads them manually at strava.com. No
Strava API, no OAuth, no share-sheet upload.

## Verification reality

Xcode is **not** installed on the build machine (Command Line Tools only). So:
- The **core logic** ships as a Swift Package (pure Foundation, no UIKit) and is
  verified here with `swift test` — green before hand-off.
- The **SwiftUI app + Xcode project** cannot be built or run here (no iOS SDK /
  simulator). They are best-effort; the user verifies by opening in Xcode.

This split is deliberate: all correctness-critical parsing/format code sits in
the verifiable layer.

## Layout

```
ios/
  StravaToolkitKit/        # SwiftPM package (verified)
    Package.swift
    Sources/StravaToolkitKit/*.swift
    Tests/StravaToolkitKitTests/*.swift
    Tests/.../Fixtures/     # tiny synthetic export + zip
  StravaToolkit/           # SwiftUI app (best-effort)
    StravaToolkit.xcodeproj
    StravaToolkit/*.swift
    StravaToolkit/Info.plist
  README.md                # build/run + manual-Xcode fallback steps
```

## Layer 1 — StravaToolkitKit (verified)

Direct port of the Python core. Pure value types + functions, no UIKit.

- `Workout` — id, code, label, start (Date?), durationSeconds, distanceMeters,
  avgHR?, hasGPS, and the raw CSV row (`[String:String]`). Mirrors the dict in
  `workout_core.load_workouts`.
- `SamsungExport`
  - `resolve(url:) -> ExportRoot` — locate the `com.samsung.health.exercise*.csv`
    and the `jsons/com.samsung.health.exercise` dir under a folder.
  - `loadWorkouts(root:) -> [Workout]` — parse the CSV (skipping Samsung's junk
    first line), newest-first. Ports `read_exercise_csv` + `load_workouts`.
- `LabelMap` — exercise_type → (label, TCX sport, GPX type). Ports the LABEL /
  RUNNING / BIKING tables.
- `TrackBuilder.buildTrack(points:totalDistance:)` — ports `build_track`
  (native-delta vs speed-integration distance, scaling to known total).
- `TCXBuilder.build(row:track:totalDistance:start:) -> String` — ports
  `build_tcx`.
- `GPXBuilder` — `mergeLocationHR(loc:live:)` + `build(rows:name:type:)`, ports
  `merge_location_hr` + `build_gpx`.
- `WorkoutDetail.load(exDir:workout:) -> Detail` — ports `load_detail`: summary
  fields + `hrSeries [(elapsedS, bpm)]`, `paceSeries [(elapsedS, sPerKm)]`,
  `route [(lat, lon)]`.
- `Exporter.export(exDir:workout:format:) -> (filename:String, data:Data)?` —
  ports `export_workout` (auto = GPX when GPS else TCX). Filename matches the
  desktop's `YYYY-MM-DD_HHMM_Label_id8.ext`.
- Formatting helpers: `fmtDuration`, `fmtDistance`, `fmtPace`, ISO/date parsing
  (port `parse_csv_datetime`, `iso`).
- `ZipReader.unzip(_ zipURL: URL, to dest: URL)` — minimal zip extractor:
  parse End-Of-Central-Directory + central directory, inflate stored/deflated
  entries via Apple's `Compression` (`COMPRESSION_ZLIB` raw deflate). Writes the
  tree to `dest`.
  - **Risk:** `Compression` availability under CLT toolchain. First task is a
    spike importing `Compression` and inflating a known buffer. If it fails, stop
    and pick a fallback with the user (import-unzipped-folder vs ZIPFoundation);
    do not silently proceed.

### JSON note
Samsung's per-workout series files (`<ref>.json`) may be gzip'd (magic `1f 8b`)
— port `load_json`'s gzip sniff. gunzip also via `Compression`
(`COMPRESSION_ZLIB`/gzip handling) or a tiny gzip wrapper; covered by the same
spike.

## Layer 2 — StravaToolkit SwiftUI app (best-effort)

Depends on the local `StravaToolkitKit` package.

- `ImportView` — `.fileImporter` for a `.zip` (UTType.zip). Copies into
  `NSTemporaryDirectory()`, calls `ZipReader.unzip`, then `SamsungExport`.
  On the agreed fallback path it would pick a folder instead.
- `WorkoutListView` — `List` of workouts; Type `Picker`, Since date filter,
  Search field; multi-select via tap-to-toggle checkmarks; format `Picker`
  (Auto / TCX / GPX); Export button.
- `WorkoutDetailView` (tap a row) — stat tiles, HR & pace charts via **Swift
  Charts**, GPS route via a SwiftUI `Canvas`/`Path` (aspect-corrected like the
  desktop). Strava-orange accent.
- Export action — writes each file into the app's **Documents** directory;
  shows a summary sheet ("Exported N files — find them in Files → On My iPhone →
  StravaToolkit, then upload at strava.com").
- `Info.plist`: `UIFileSharingEnabled = YES`,
  `LSSupportsOpeningDocumentsInPlace = YES` so Documents is visible in Files.

### Xcode project
Hand-authored `.xcodeproj` referencing the sources and the local package. Since
it can't be validated here, `ios/README.md` documents a reliable manual fallback
(create an iOS App target in Xcode, add the Swift files, add the local package
dependency, set the two Info.plist keys).

## Error handling

- Unreadable/absent CSV or JSON → empty results, never crash (mirror the Python
  `try/except` degradations).
- Bad zip / unsupported entry → surfaced as a user-visible import error.
- Detail series with <2 points → charts show "No data" (mirror desktop).

## Testing (Layer 1, via `swift test`)

Fixtures: a tiny synthetic export (CSV + one live_data JSON + one location_data
JSON) and a `.zip` of it (committed as a fixture, generated once with Python).

- `loadWorkouts` parses the fixture CSV → expected count, labels, hasGPS flags,
  newest-first order.
- `TrackBuilder` distance from speed-integration and from native deltas; scaling
  to a known total.
- `TCXBuilder` output contains `<Activity Sport=...>`, trackpoints, distance, HR.
- `GPXBuilder` output contains `<trkpt lat lon>` and forwarded HR.
- `WorkoutDetail`: hrSeries/paceSeries elapsed-seconds + values; pace skips
  zero/None speed; route from location_data; empty when no live_data.
- `Exporter` filename format + auto→gpx-when-GPS / tcx-otherwise.
- `ZipReader` round-trips the fixture zip to the same file tree.

App/UI: not verified here; manual in Xcode.

## Scope (YAGNI)

Core flow + inspect view only. No Strava API, no share-sheet upload. Deferred,
easy to add later.

## Addendum (2026-07-05): Hide-exported tracking

Added after the core shipped, to reach parity with the desktop.

- `ExportLog` in StravaToolkitKit (verified via `stkcheck`): `load(path:)` →
  id→date map ([:] on missing/corrupt), `mark(_:path:)` atomic write (temp +
  replace, first-write falls back to atomic write since `replaceItemAt` needs an
  existing file), `defaultURL()` → `Library/Application Support/exported.json`.
  Path is injectable so the checker uses a temp file. Port of `export_log.py`.
- `AppModel`: loads the log on init; `hideExported` flag; `filtered` skips
  exported ids when on; `exportSelected` marks the ids that produced a file.
- UI: a "Hide exported" `Toggle` in the filter bar (off by default). No badge /
  manual unmark, matching the desktop.
- Verified: `stkcheck` covers load-missing/corrupt/round-trip/re-mark/dir-create
  against a temp path; AppModel + Toggle wiring is parse-checked only.
