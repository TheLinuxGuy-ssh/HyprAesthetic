#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from hypraesthetic.cli import main
from hypraesthetic.export_theme import PALETTE_EXPORT_TOAST, export_theme, generate_from_wallpaper
from hypraesthetic.paths import current_theme_file, user_themes_dir
from hypraesthetic.prefs import Prefs
from hypraesthetic.theme import ThemePackage
from tests.test_theme import V2_TOML


class ExportThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.old_home = os.environ.get("HOME")
        self.old_root = os.environ.get("HYPRAESTHETIC_ROOT")
        os.environ["HOME"] = str(self.home)
        self.repo = Path(self.tmp.name) / "repo"
        theme = self.repo / "themes" / "sample"
        theme.mkdir(parents=True)
        body = V2_TOML.replace('widgets = ["clock", "system"]', 'bar_style = "v7"\nwidgets = ["clock", "system"]')
        (theme / "theme.toml").write_text(body.lstrip(), encoding="utf-8")
        (theme / "wallpaper").mkdir()
        (theme / "wallpaper" / "sample.png").write_bytes(b"THEMEWALL")
        (theme / "preview.png").write_bytes(b"PREV")
        (theme / "nvim" / "lua").mkdir(parents=True)
        (theme / "nvim" / "lua" / "huge.lua").write_text("do not copy\n", encoding="utf-8")
        os.environ["HYPRAESTHETIC_ROOT"] = str(self.repo)
        current = current_theme_file()
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text("sample\n", encoding="utf-8")
        wall = self.home / "Pictures" / "desk.png"
        wall.parent.mkdir(parents=True)
        wall.write_bytes(b"DESK")
        self.wall = wall
        prefs = Prefs.load()
        prefs.set("bar_style", "compact")
        prefs.set("wallpaper", str(wall))
        prefs.set_widgets_for("sample", ["clock", "quote"])
        prefs.save()

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        if self.old_root is None:
            os.environ.pop("HYPRAESTHETIC_ROOT", None)
        else:
            os.environ["HYPRAESTHETIC_ROOT"] = self.old_root
        self.tmp.cleanup()

    def test_export_copies_palette_layout_wallpaper_and_preview(self) -> None:
        dest = export_theme("myrice")
        self.assertEqual(dest, user_themes_dir() / "myrice")
        self.assertFalse((dest / "nvim").exists())
        self.assertTrue((dest / "desk.png").is_file())
        self.assertEqual((dest / "desk.png").read_bytes(), b"DESK")
        self.assertTrue((dest / "preview.png").is_file())
        self.assertEqual((dest / "preview.png").read_bytes(), b"PREV")
        pkg = ThemePackage.load(dest)
        self.assertEqual(pkg.name, "myrice")
        self.assertEqual(pkg.palette["base00"], "#0d0d0d")
        self.assertEqual(pkg.layout["bar_style"], "compact")
        self.assertEqual(pkg.widgets, ["clock", "quote"])
        self.assertEqual(pkg.wallpaper, "desk.png")
        self.assertNotEqual(pkg.root, self.repo / "themes" / "sample")

    def test_export_cli_uses_temp_home(self) -> None:
        from io import StringIO
        import sys

        out, err = StringIO(), StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            code = main(["export-theme", "myrice"])
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        self.assertEqual(code, 0)
        self.assertIn("myrice", out.getvalue())
        self.assertEqual(err.getvalue(), "")
        self.assertTrue((user_themes_dir() / "myrice" / "theme.toml").is_file())

    def test_export_rejects_path_names(self) -> None:
        with self.assertRaises(ValueError):
            export_theme("../oops")
        with self.assertRaises(ValueError):
            export_theme("a/b")
        with self.assertRaises(ValueError):
            export_theme("  ")

    def test_generate_from_wallpaper_runs_export_theme(self) -> None:
        calls: list[list[str]] = []

        def which(name: str) -> str | None:
            if name == "wallust":
                return "/usr/bin/wallust"
            return None

        message = generate_from_wallpaper(
            "myrice",
            which=which,
            runner=lambda cmd: calls.append(list(cmd)),
        )
        self.assertEqual(calls, [["hat", "export-theme", "myrice"]])
        self.assertEqual(message, PALETTE_EXPORT_TOAST)
        self.assertEqual(
            message,
            "Install wallust to generate a palette; until then export copies the current preset colors.",
        )

    def test_generate_accepts_matugen_on_path(self) -> None:
        calls: list[list[str]] = []
        message = generate_from_wallpaper(
            "myrice",
            which=lambda name: "/usr/bin/matugen" if name == "matugen" else None,
            runner=lambda cmd: calls.append(list(cmd)),
        )
        self.assertEqual(calls, [["hat", "export-theme", "myrice"]])
        self.assertIn("export copies the current preset colors", message)

    def test_generate_refuses_without_a_palette_tool(self) -> None:
        with self.assertRaises(RuntimeError):
            generate_from_wallpaper(
                "myrice",
                which=lambda _name: None,
                runner=lambda _cmd: None,
            )


if __name__ == "__main__":
    unittest.main()
