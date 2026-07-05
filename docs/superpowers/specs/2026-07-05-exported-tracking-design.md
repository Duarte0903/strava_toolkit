# Track Exported Workouts + "Hide exported" Filter — Design

Date: 2026-07-05
Component: new `export_log.py` + `strava_gui.py`

## Goal

Remember which workouts have already been exported, and let the user filter the
list down to just the not-yet-exported ones — so re-running against the same
Samsung export doesn't re-surface everything already uploaded to Strava.

## Storage

A single central file: `~/.strava_toolkit/exported.json`, a flat map keyed by
Samsung `datauuid` (globally unique):

```json
{ "3f2a…": "2026-07-05", "9c81…": "2026-07-04" }
```

Central (not per-export) is fine because ids are globally unique. Human-readable
so the user can inspect/edit it.

## New module: `export_log.py` (GUI-free, unit-testable)

- `DEFAULT_PATH = ~/.strava_toolkit/exported.json`
- `load_log(path=None) -> dict`
  - Reads the JSON map. Returns `{}` when the file is missing OR unreadable OR
    corrupt (never raises). `path` defaults to `DEFAULT_PATH`.
- `mark_exported(ids, path=None) -> dict`
  - Merges each id in `ids` with today's date (`YYYY-MM-DD`), writes the whole
    map back **atomically** (write temp file in the same dir, then `os.replace`),
    creating the parent directory if needed. Re-marking an existing id just
    updates its date. Returns the updated map.
- `path` is injectable purely so tests use a temp file and never touch the real
  home-dir log.

Kept out of the GUI so it can be tested headlessly, matching `workout_core`.

## Wiring into `strava_gui.py`

- On `App.__init__`, load once: `self.exported = export_log.load_log()`.
- Filter bar gains a `ttk.Checkbutton` "Hide exported" bound to a
  `tk.BooleanVar` (`self.hide_exported`), default off, calling `refresh_view` on
  toggle.
- `refresh_view`: when `hide_exported` is set, skip any `it` whose `it["id"]` is
  in `self.exported`.
- `export()`: track the ids that actually produced a file (the `made` path,
  `path` truthy). After the loop, if any were made:
  `self.exported = export_log.mark_exported(made_ids)`, then `refresh_view()` so
  freshly-exported rows drop out when the filter is on. Wrap the write in
  try/except; on failure, note it in the status line and keep the app usable
  (in-memory `self.exported` is still updated so the session behaves correctly).

Re-exporting a workout is allowed — it just refreshes the stored date.

## Error handling

- Missing / corrupt log → treated as empty; app starts clean, export still
  works and re-creates the file on next successful export.
- Failed atomic write → caught in `export()`; surfaced in the status label as a
  warning, not a crash.

## Testing

Stdlib `unittest` (`test_export_log.py`) against a temp path:
- `load_log` on a missing file → `{}`.
- `load_log` on a corrupt file (garbage bytes) → `{}`.
- `mark_exported([...])` then `load_log` round-trips the ids.
- Re-marking an existing id updates rather than duplicates; other ids preserved.
- `mark_exported` creates the parent directory when absent.

GUI filter verified by driving the real `App`: mark a workout exported, toggle
the checkbox, confirm the row disappears / reappears.

## Scope (YAGNI)

No exported badge/column, no manual mark-unmark, no detail-panel line. Just the
central log + the "Hide exported" filter. Any of those are easy follow-ons.

## Files touched

- `export_log.py` — new.
- `strava_gui.py` — load log, filter checkbox, mark-on-export wiring.
- `test_export_log.py` — new.
