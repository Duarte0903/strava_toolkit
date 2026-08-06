#!/usr/bin/env python3
"""
Tests for samsung_export — the layer that makes the legacy and the current
Samsung Health export layouts look the same to the converters.

Run:  python3 -m unittest test_samsung_export
"""

import json
import os
import tempfile
import unittest

import samsung_export as sx

LEGACY_CSV = """com.samsung.health.exercise
datauuid,exercise_type,duration,distance,mean_heart_rate,time_offset,start_time,live_data,location_data
w1,1002,600000,2000,150,7200000,2021-10-08 10:48:24,w1.live_data,w1.location_data
"""

# The current export prefixes most columns, spells the file "shealth", names the
# JSON file in full, writes the offset as "UTC+0200" and stores start_time in UTC.
CURRENT_CSV = """com.samsung.shealth.exercise,7005009,17
title,source_type,com.samsung.health.exercise.datauuid,com.samsung.health.exercise.exercise_type,com.samsung.health.exercise.duration,com.samsung.health.exercise.distance,com.samsung.health.exercise.mean_heart_rate,com.samsung.health.exercise.time_offset,com.samsung.health.exercise.start_time,com.samsung.health.exercise.live_data,com.samsung.health.exercise.location_data
,4,abc12345-0000-0000-0000-000000000000,1002,600000,2000,150,UTC+0200,2021-10-08 10:48:24.000,abc12345-0000-0000-0000-000000000000.com.samsung.health.exercise.live_data.json,
"""

POINTS = [{"start_time": 1_000, "speed": 2.0}, {"start_time": 2_000, "speed": 3.0}]


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def make_legacy(base):
    _write(os.path.join(base, "com.samsung.health.exercise.202507.csv"), LEGACY_CSV)
    jdir = os.path.join(base, "jsons", "com.samsung.health.exercise")
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "w1.live_data.json"), "w") as f:
        json.dump(POINTS, f)
    return base


def make_current(base):
    _write(os.path.join(base, "com.samsung.shealth.exercise.20260723144996.csv"), CURRENT_CSV)
    # decoys that share the stem and must not be mistaken for the exercise table
    _write(os.path.join(base, "com.samsung.shealth.exercise.weather.20260723144996.csv"), "x\n")
    _write(os.path.join(base, "com.samsung.shealth.exercise.route.20260723144996.csv"), "x\n")
    # payloads live in single-hex-character subfolders
    jdir = os.path.join(base, "jsons", "com.samsung.shealth.exercise", "a")
    os.makedirs(jdir, exist_ok=True)
    name = "abc12345-0000-0000-0000-000000000000.com.samsung.health.exercise.live_data.json"
    with open(os.path.join(jdir, name), "w") as f:
        json.dump(POINTS, f)
    return base


class ExportBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        sx.clear_json_index()

    def tearDown(self):
        self._tmp.cleanup()
        sx.clear_json_index()


class LocatingTests(ExportBase):
    def test_finds_legacy_csv_and_json_dir(self):
        make_legacy(self.base)
        jdir, csv_path = sx.find_paths(self.base)
        self.assertTrue(csv_path.endswith("com.samsung.health.exercise.202507.csv"))
        self.assertTrue(jdir.endswith(os.path.join("jsons", "com.samsung.health.exercise")))

    def test_finds_current_csv_and_json_dir(self):
        make_current(self.base)
        jdir, csv_path = sx.find_paths(self.base)
        self.assertTrue(csv_path.endswith("com.samsung.shealth.exercise.20260723144996.csv"))
        self.assertTrue(jdir.endswith(os.path.join("jsons", "com.samsung.shealth.exercise")))

    def test_ignores_sibling_exercise_tables(self):
        make_current(self.base)
        _, csv_path = sx.find_paths(self.base)
        self.assertNotIn("weather", csv_path)
        self.assertNotIn("route", csv_path)

    def test_finds_export_nested_one_level_down(self):
        make_current(os.path.join(self.base, "unzipped", "samsunghealth_20260723"))
        self.assertTrue(sx.find_root(self.base).endswith("samsunghealth_20260723"))

    def test_missing_export_raises(self):
        with self.assertRaises(sx.ExportFormatError):
            sx.find_paths(self.base)
        self.assertIsNone(sx.find_root(self.base))


class ColumnTests(ExportBase):
    def test_legacy_columns_pass_through(self):
        make_legacy(self.base)
        _, csv_path = sx.find_paths(self.base)
        row = next(sx.read_exercise_csv(csv_path))
        self.assertEqual(row["datauuid"], "w1")
        self.assertEqual(row["exercise_type"], "1002")

    def test_current_columns_are_unprefixed(self):
        make_current(self.base)
        _, csv_path = sx.find_paths(self.base)
        row = next(sx.read_exercise_csv(csv_path))
        self.assertEqual(row["exercise_type"], "1002")
        self.assertEqual(row["distance"], "2000")
        # the long name is preserved as well
        self.assertEqual(row["com.samsung.health.exercise.distance"], "2000")

    def test_plain_column_wins_over_prefixed_one(self):
        row = {"title": "kept", "com.samsung.health.exercise.title": "dropped"}
        self.assertEqual(sx.normalise_row(row)["title"], "kept")


class TimeTests(unittest.TestCase):
    def test_utc_offset_string_to_ms(self):
        self.assertEqual(sx.tz_offset_ms("UTC+0200"), 7_200_000)
        self.assertEqual(sx.tz_offset_ms("UTC-0500"), -18_000_000)
        self.assertEqual(sx.tz_offset_ms("UTC+0530"), 19_800_000)
        self.assertEqual(sx.tz_offset_ms("UTC"), 0)

    def test_legacy_numeric_offset_passes_through(self):
        self.assertEqual(sx.tz_offset_ms("7200000"), 7_200_000)
        self.assertEqual(sx.tz_offset_ms(7_200_000), 7_200_000)
        self.assertEqual(sx.tz_offset_ms(""), 0)
        self.assertEqual(sx.tz_offset_ms(None), 0)

    def test_current_start_time_is_already_utc(self):
        # "UTC+0200" means the cell is UTC; the offset must NOT be subtracted.
        ms = sx.parse_csv_datetime("2021-10-08 10:48:24.000", "UTC+0200")
        self.assertEqual(sx.parse_csv_datetime("2021-10-08 10:48:24", "UTC"), ms)

    def test_legacy_start_time_is_local_and_shifted_to_utc(self):
        local = sx.parse_csv_datetime("08/10/2021, 10:48:24", 0)
        shifted = sx.parse_csv_datetime("08/10/2021, 10:48:24", 7_200_000)
        self.assertEqual(local - shifted, 7_200_000)

    def test_unparseable_start_time_is_none(self):
        self.assertIsNone(sx.parse_csv_datetime("not a date", "UTC+0200"))
        self.assertIsNone(sx.parse_csv_datetime("", "UTC+0200"))


class PayloadTests(ExportBase):
    def test_legacy_reference_without_extension(self):
        make_legacy(self.base)
        jdir, _ = sx.find_paths(self.base)
        self.assertEqual(sx.load_points(jdir, "w1.live_data"), POINTS)

    def test_current_reference_inside_hex_subfolder(self):
        make_current(self.base)
        jdir, csv_path = sx.find_paths(self.base)
        row = next(sx.read_exercise_csv(csv_path))
        self.assertEqual(sx.load_points(jdir, row["live_data"]), POINTS)

    def test_reference_found_even_if_sharding_differs(self):
        """A file filed under an unexpected subfolder is still located."""
        make_current(self.base)
        jdir, _ = sx.find_paths(self.base)
        stray = os.path.join(jdir, "z", "stray.live_data.json")
        os.makedirs(os.path.dirname(stray), exist_ok=True)
        with open(stray, "w") as f:
            json.dump(POINTS, f)
        sx.clear_json_index()
        self.assertEqual(sx.load_points(jdir, "stray.live_data"), POINTS)

    def test_missing_or_empty_reference_gives_empty_list(self):
        make_current(self.base)
        jdir, _ = sx.find_paths(self.base)
        self.assertEqual(sx.load_points(jdir, ""), [])
        self.assertEqual(sx.load_points(jdir, None), [])
        self.assertEqual(sx.load_points(jdir, "nope.live_data"), [])

    def test_unreadable_payload_gives_empty_list(self):
        make_current(self.base)
        jdir, _ = sx.find_paths(self.base)
        broken = os.path.join(jdir, "b", "broken.live_data.json")
        os.makedirs(os.path.dirname(broken), exist_ok=True)
        with open(broken, "w") as f:
            f.write("{not json")
        self.assertEqual(sx.load_points(jdir, "broken.live_data"), [])


if __name__ == "__main__":
    unittest.main()
