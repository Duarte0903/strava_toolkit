#!/usr/bin/env python3
"""
Headless tests for workout_core.load_detail — no tkinter required.

Run:  python3 -m unittest test_workout_core
"""

import json
import os
import tempfile
import unittest

import workout_core as wc


def _make_item(ex_dir, live_points=None, loc_points=None, **over):
    """Write live/location JSON into ex_dir and return a workout item dict."""
    row = {
        "datauuid": "w1",
        "exercise_type": "1002",          # Run
        "duration": "600000",             # 600 s
        "distance": "2000",               # 2 km
        "mean_heart_rate": "150",
        "max_heart_rate": "182",
        "calorie": "310",
        "live_data": "",
        "location_data": "",
    }
    if live_points is not None:
        with open(os.path.join(ex_dir, "w1.live_data.json"), "w") as f:
            json.dump(live_points, f)
        row["live_data"] = "w1.live_data"
    if loc_points is not None:
        with open(os.path.join(ex_dir, "w1.location_data.json"), "w") as f:
            json.dump(loc_points, f)
        row["location_data"] = "w1.location_data"

    item = {
        "id": "w1",
        "row": row,
        "code": 1002,
        "label": "Run",
        "start": 1_000,        # epoch ms; matches first live point below
        "duration_s": 600.0,
        "distance_m": 2000.0,
        "avg_hr": 150.0,
        "has_gps": loc_points is not None,
    }
    item.update(over)
    return item


class LoadDetailTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ex_dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_hr_series_elapsed_seconds_from_live_data(self):
        live = [
            {"start_time": 1_000, "heart_rate": "100", "speed": "2.0"},
            {"start_time": 2_000, "heart_rate": "150", "speed": "3.0"},
            {"start_time": 3_000, "heart_rate": "200", "speed": "4.0"},
        ]
        item = _make_item(self.ex_dir, live_points=live)
        d = wc.load_detail(self.ex_dir, item)
        # elapsed seconds relative to the first sample, with bpm values
        self.assertEqual(d["hr_series"], [(0.0, 100.0), (1.0, 150.0), (2.0, 200.0)])

    def test_pace_series_derived_from_speed(self):
        live = [
            {"start_time": 1_000, "heart_rate": "100", "speed": "2.0"},  # 500 s/km
            {"start_time": 2_000, "heart_rate": "150", "speed": "4.0"},  # 250 s/km
        ]
        item = _make_item(self.ex_dir, live_points=live)
        d = wc.load_detail(self.ex_dir, item)
        self.assertEqual(d["pace_series"], [(0.0, 500.0), (1.0, 250.0)])

    def test_pace_series_skips_zero_and_missing_speed(self):
        live = [
            {"start_time": 1_000, "speed": "0"},       # stopped -> skipped
            {"start_time": 2_000, "speed": "5.0"},     # 200 s/km
            {"start_time": 3_000, "heart_rate": "140"},  # no speed -> skipped
        ]
        item = _make_item(self.ex_dir, live_points=live)
        d = wc.load_detail(self.ex_dir, item)
        self.assertEqual(d["pace_series"], [(1.0, 200.0)])

    def test_route_from_location_data(self):
        loc = [
            {"start_time": 1_000, "latitude": "38.72", "longitude": "-9.14"},
            {"start_time": 2_000, "latitude": "38.73", "longitude": "-9.15"},
        ]
        item = _make_item(self.ex_dir, loc_points=loc)
        d = wc.load_detail(self.ex_dir, item)
        self.assertTrue(d["has_gps"])
        self.assertEqual(d["route"], [(38.72, -9.14), (38.73, -9.15)])

    def test_no_live_data_gives_empty_series_without_error(self):
        item = _make_item(self.ex_dir)  # no live, no location
        d = wc.load_detail(self.ex_dir, item)
        self.assertEqual(d["hr_series"], [])
        self.assertEqual(d["pace_series"], [])
        self.assertEqual(d["route"], [])
        self.assertFalse(d["has_gps"])

    def test_summary_fields(self):
        item = _make_item(self.ex_dir)
        d = wc.load_detail(self.ex_dir, item)
        self.assertEqual(d["sport"], "Run")
        self.assertAlmostEqual(d["max_hr"], 182.0)
        self.assertAlmostEqual(d["calories"], 310.0)
        # 600 s over 2 km -> 300 s/km
        self.assertAlmostEqual(d["avg_pace_s_per_km"], 300.0)


if __name__ == "__main__":
    unittest.main()
