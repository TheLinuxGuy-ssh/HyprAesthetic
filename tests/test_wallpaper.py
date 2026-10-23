#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hypraesthetic.prefs import Prefs
from hypraesthetic.wallpaper import set_user_wallpaper


class WallpaperTests(unittest.TestCase):
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

    def test_set_user_wallpaper_saves_prefs_without_daemon(self) -> None:
        image = self.home / "Pictures" / "Wallpapers" / "a.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"x")
        with patch("hypraesthetic.wallpaper.shutil.which", return_value=None):
            self.assertTrue(set_user_wallpaper(image))
        prefs = Prefs.load()
        self.assertEqual(prefs.get("wallpaper"), str(image.resolve()))


if __name__ == "__main__":
    unittest.main()
