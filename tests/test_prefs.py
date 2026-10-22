#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from hypraesthetic.prefs import Prefs, default_prefs


class PrefsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        self.tmp.cleanup()

    def test_defaults_match_automatic_catalog(self) -> None:
        prefs = default_prefs()
        self.assertEqual(prefs["bar"], "waybar")
        self.assertEqual(prefs["file_manager"], "nautilus")
        self.assertEqual(prefs["terminal"], "kitty")
        self.assertEqual(prefs["launcher"], "rofi")
        self.assertIn("clock", prefs["widgets"])

    def test_geometry_is_namespaced_per_theme(self) -> None:
        prefs = Prefs.load()
        prefs.set_geometry_for("toji", {"clock": {"x": "4%", "y": "8%", "width": "450", "height": "155"}})
        prefs.set_geometry_for("choso", {"clock": {"x": "80%", "y": "5%", "width": "450", "height": "155"}})
        prefs.save()
        loaded = Prefs.load()
        self.assertEqual(loaded.geometry_for("toji")["clock"]["x"], "4%")
        self.assertEqual(loaded.geometry_for("choso")["clock"]["x"], "80%")
        loaded.clear_geometry_for("toji")
        self.assertEqual(loaded.geometry_for("toji"), {})
        self.assertEqual(loaded.geometry_for("choso")["clock"]["x"], "80%")

    def test_legacy_flat_geometry_adopts_onto_current_theme(self) -> None:
        prefs = Prefs.load()
        prefs.set("widget_geometry", {"clock": {"x": "12%", "y": "8%", "width": "450", "height": "155"}})
        prefs.adopt_legacy_geometry("toji")
        self.assertEqual(prefs.geometry_for("toji")["clock"]["x"], "12%")
        self.assertEqual(prefs.geometry_for("choso"), {})

    def test_roundtrip(self) -> None:
        prefs = Prefs.load()
        prefs.set("file_manager", "thunar")
        prefs.set("widgets", ["clock"])
        prefs.save()
        loaded = Prefs.load()
        self.assertEqual(loaded.get("file_manager"), "thunar")
        self.assertEqual(loaded.get("widgets"), ["clock"])


if __name__ == "__main__":
    unittest.main()
