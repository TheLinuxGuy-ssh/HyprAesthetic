#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from hypraesthetic.paths import current_theme_file, user_config_dir
from hypraesthetic.rofi_menus import theme_menu_rows, wallpaper_menu_rows
from tests.test_theme import V2_TOML


class RofiMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.repo = Path(self.tmp.name) / "repo"
        theme = self.repo / "themes" / "sample"
        theme.mkdir(parents=True)
        (theme / "theme.toml").write_text(V2_TOML.lstrip(), encoding="utf-8")
        preview = theme / "wallpaper" / "sample.png"
        preview.parent.mkdir(parents=True)
        preview.write_bytes(b"png")
        os.environ["HYPRAESTHETIC_ROOT"] = str(self.repo)

    def tearDown(self) -> None:
        os.environ.pop("HYPRAESTHETIC_ROOT", None)
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        self.tmp.cleanup()

    def test_theme_menu_uses_theme_preview_not_only_dot_wallpapers(self) -> None:
        user_config_dir().mkdir(parents=True)
        current_theme_file().write_text("sample\n", encoding="utf-8")
        rows = theme_menu_rows()
        self.assertEqual(len(rows), 1)
        label, tid, preview = rows[0]
        self.assertEqual(tid, "sample")
        self.assertIn("(active)", label)
        self.assertTrue(Path(preview).is_file())

    def test_wallpaper_menu_lists_home_wallpapers_dir(self) -> None:
        folder = self.home / ".wallpapers"
        folder.mkdir()
        image = folder / "mine.jpg"
        image.write_bytes(b"j")
        rows = wallpaper_menu_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], str(image.resolve()))


if __name__ == "__main__":
    unittest.main()
