#!/usr/bin/env python3
"""
Headless tests for export_log — never touches the real ~/.strava_toolkit file
(every call passes an explicit temp path).

Run:  python3 -m unittest test_export_log
"""

import os
import tempfile
import unittest

import export_log as el


class ExportLogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "sub", "exported.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty(self):
        self.assertEqual(el.load_log(self.path), {})

    def test_corrupt_file_returns_empty(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w") as f:
            f.write("{not valid json…")
        self.assertEqual(el.load_log(self.path), {})

    def test_mark_then_load_roundtrips(self):
        el.mark_exported(["a", "b"], self.path)
        log = el.load_log(self.path)
        self.assertIn("a", log)
        self.assertIn("b", log)

    def test_mark_creates_parent_dir(self):
        self.assertFalse(os.path.exists(os.path.dirname(self.path)))
        el.mark_exported(["a"], self.path)
        self.assertTrue(os.path.exists(self.path))

    def test_remark_updates_and_preserves_others(self):
        el.mark_exported(["a", "b"], self.path)
        el.mark_exported(["a"], self.path)   # re-mark a; b must survive
        log = el.load_log(self.path)
        self.assertEqual(set(log.keys()), {"a", "b"})

    def test_mark_returns_updated_map(self):
        out = el.mark_exported(["x"], self.path)
        self.assertIn("x", out)
        # dates are YYYY-MM-DD strings
        self.assertRegex(out["x"], r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
