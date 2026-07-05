# Workout Inspector + Visual Refresh — Design

Date: 2026-07-05
Component: `strava_gui.py` (UI) + `workout_core.py` (data)

## Goal

Let the user inspect an individual Samsung Health workout from within the
exporter GUI — full stats, heart-rate and pace charts, and a GPS route trace —
and give the whole app a cleaner, more modern look. Zero new dependencies:
everything stays Python standard library (tkinter `Canvas` for charts).

## Non-goals (YAGNI)

- No map tiles — the route is a plain traced path, not a slippy map.
- No chart zoom/pan, no tooltips.
- No dark mode, no per-km splits (may add later).
- Export flow, format selection, and file output are unchanged.

## Architecture

Two layers, matching the existing split:

- `workout_core.py` — GUI-free, headlessly testable. Gains one function that
  turns a workout item into a fully-populated detail structure.
- `strava_gui.py` — tkinter. Gains a detail panel beside the list, plus a
  visual restyle.

### Data layer: `load_detail(ex_dir, item)`

Returns a dict the panel can render without further parsing:

```
{
  "sport": str,            # item["label"]
  "date": str,             # fmt_date(item["start"])
  "duration_s": float,
  "distance_m": float,
  "avg_hr": float | None,
  "max_hr": float | None,  # from row["max_heart_rate"]
  "calories": float | None,# from row["calorie"]
  "avg_pace_s_per_km": float | None,   # derived from distance + duration
  "has_gps": bool,
  "hr_series":   [(elapsed_s, bpm), ...],      # may be empty
  "pace_series": [(elapsed_s, s_per_km), ...], # from speed; may be empty
  "route":       [(lat, lon), ...],            # empty when no GPS
}
```

Implementation notes:
- Reuse `tcx.build_track(live_points, item["distance_m"])` for the time series.
  `elapsed_s` = `(tp["t"] - track[0]["t"]) / 1000`.
- HR series: points where `tp["hr"]` is not None.
- Pace series: derive from `tp["speed"]` (m/s → s/km = `1000 / speed` when
  `speed > 0`); skip zero/None speeds.
- Route: read `row["location_data"]` via the existing `_load` helper; each GPS
  point contributes `(latitude, longitude)`. Empty when `has_gps` is False.
- `avg_pace_s_per_km` = `duration_s / (distance_m / 1000)` when distance > 0.

This keeps all file/JSON parsing out of the GUI and testable without tkinter.

### UI layer

**Split layout.** Replace the single table frame with a horizontal
`ttk.PanedWindow`:
- Left pane (~55%): the existing filters + Treeview, unchanged in behavior.
- Right pane (~45%): a scrollable detail panel.

**Selection.** Clicking a row keeps its current job — toggling the checkbox —
and *additionally* loads that row into the detail panel (track the
"focused" row id separately from the checkbox `selected` set). The detail panel
starts on an empty state: a muted "Select a workout to inspect."

**Detail panel, top → bottom:**
1. Header — `"{sport} · {date}"`, large font.
2. Stat tiles — a wrapped row of labeled tiles: Distance, Duration, Avg pace,
   Avg HR, Max HR, Calories. Tiles whose value is None are omitted.
3. HR chart — a `Canvas` sparkline (accent-colored line) of `hr_series` vs
   elapsed time, with min/max bpm labels. Hidden if `hr_series` is empty.
4. Pace chart — a second `Canvas` of `pace_series` (lower pace = faster, so the
   y-axis is inverted for intuitive "up = faster"). Hidden if empty.
5. Route — a `Canvas` tracing `route`, auto-scaled to fit with correct aspect
   (longitude scaled by `cos(mean_latitude)`). Shown only when `has_gps`;
   otherwise a small note: "No GPS — indoor/treadmill workout."

**Canvas charting helper.** A small internal function draws a polyline into a
canvas given a list of `(x, y)` data points and pixel bounds: computes
data min/max, maps to padded pixel box, draws axis baseline + the polyline.
Reused by all three canvases (charts pass time/value; route passes lon/lat).
Redraws on `<Configure>` so charts follow panel resizing.

### Visual refresh (ttk `clam` theme)

- Palette: light background `#F7F7F8`, card/white `#FFFFFF`, text `#1A1A1A`,
  muted `#6B6B6B`, accent `#FC5200` (Strava orange), zebra row `#F0F0F1`.
- Treeview: row height ~28px, header style with bold text and subtle bottom
  border, accent-colored selection background, zebra striping via row tags.
- Buttons: accent background, white text; flat relief.
- Progress bar: accent-colored trough fill.
- Fonts: a slightly larger UI font for headers/stat values; muted secondary
  labels. Use tkinter's default family (no font files to ship).
- Consistent padding and section spacing throughout the detail panel.

All styling via `ttk.Style` configuration + tk widget options — no images, no
external assets, cross-platform.

## Error handling

- `load_detail` degrades gracefully: missing/unreadable `live_data` or
  `location_data` → empty series / empty route, never raises. The panel simply
  hides the affected chart.
- Charts with 0 or 1 data point render nothing (no crash from a degenerate
  min==max range — guard by drawing a flat midline).
- Focusing a workout whose detail fails to load shows the empty state plus a
  muted "Couldn't read this workout's data" note; the app keeps running.

## Testing

Headless (no tkinter) tests for `workout_core.load_detail` against a small
synthetic export fixture:
- Workout with HR + speed live_data → non-empty `hr_series` / `pace_series`,
  correct `avg_pace_s_per_km`.
- Workout with GPS `location_data` → non-empty `route`; `has_gps` True.
- Workout with no live_data → empty series, no exception.
- Pace derivation: speed 0 / None points are skipped; `1000/speed` correct.

GUI is verified manually by loading a real export, clicking rows, and confirming
the panel, charts, and route render and resize.

## Files touched

- `workout_core.py` — add `load_detail` (+ any small helpers it needs).
- `strava_gui.py` — PanedWindow split, detail panel, canvas charting helper,
  `ttk.Style` restyle, focused-row tracking.
- New test file for `load_detail`.
