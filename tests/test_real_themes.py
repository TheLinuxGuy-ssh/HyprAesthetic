#!/usr/bin/env python3

from __future__ import annotations

import re
import unittest
from pathlib import Path

from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.paths import REPO_ROOT
from hypraesthetic.theme import ThemePackage


class RealThemeTests(unittest.TestCase):
    def test_every_official_theme_loads(self) -> None:
        catalog = ThemeCatalog(official_root=REPO_ROOT / "themes", user_root=Path("/nonexistent"))
        names = catalog.names()
        self.assertIn("toji", names)
        self.assertIn("spartan", names)
        for pkg in catalog.list():
            self.assertTrue(pkg.palette["base00"].startswith("#"))
            self.assertIn("waybar", pkg.colors)
            self.assertTrue(pkg.flatten()["colors_waybar_background"].startswith("#"))

    def test_official_themes_ship_quotes(self) -> None:
        catalog = ThemeCatalog(official_root=REPO_ROOT / "themes", user_root=Path("/nonexistent"))
        for pkg in catalog.list():
            self.assertTrue(pkg.quotes, msg=f"{pkg.name} missing quotes")

    def test_schema_v2_uses_palette_table(self) -> None:
        pkg = ThemePackage.load(REPO_ROOT / "themes" / "toji")
        self.assertEqual(pkg.schema, 2)
        self.assertEqual(pkg.colors["hyprland"]["border_active"], pkg.palette["base0D"])

    def test_official_widget_sets_match_identity_cast(self) -> None:
        expected = {
            "toji": ["clock", "quote", "music", "system", "matrix"],
            "toji_2": ["clock", "quote", "music", "system", "matrix"],
            "jjk": ["clock", "quote", "music", "matrix"],
            "choso": ["clock", "quote", "system", "matrix"],
            "tanjiro": ["clock", "quote", "music", "weather", "system"],
            "spartan": ["clock", "quote", "music", "system", "matrix"],
            "sky": ["clock", "music"],
            "a70": ["clock", "music"],
        }
        for name, widgets in expected.items():
            pkg = ThemePackage.load(REPO_ROOT / "themes" / name)
            self.assertEqual(pkg.widgets, widgets, msg=name)

    def test_toji_2_matrix_color_contrasts_red_wallpaper_accent(self) -> None:
        pkg = ThemePackage.load(REPO_ROOT / "themes" / "toji_2")
        self.assertEqual(pkg.colors["eww"]["primary"], pkg.palette["base0D"])
        self.assertEqual(pkg.colors["eww"]["matrix_color"], pkg.palette["base05"])

    def test_toji_spartan_choso_matrix_charsets_differ(self) -> None:
        toji = ThemePackage.load(REPO_ROOT / "themes" / "toji")
        spartan = ThemePackage.load(REPO_ROOT / "themes" / "spartan")
        choso = ThemePackage.load(REPO_ROOT / "themes" / "choso")
        self.assertNotEqual(toji.identity["matrix_chars"], spartan.identity["matrix_chars"])
        self.assertNotEqual(toji.identity["matrix_chars"], choso.identity["matrix_chars"])
        self.assertNotEqual(spartan.identity["matrix_chars"], choso.identity["matrix_chars"])
        self.assertIn("/", toji.identity["matrix_chars"])
        self.assertEqual(spartan.identity["matrix_mode"], "crest")
        self.assertIn("Λ", spartan.identity["matrix_chars"])

    def test_spartan_uses_black_foreground_tokens(self) -> None:
        pkg = ThemePackage.load(REPO_ROOT / "themes" / "spartan")
        self.assertEqual(pkg.colors["eww"]["foreground"], "#000000")
        self.assertEqual(pkg.colors["waybar"]["foreground"], "#000000")
        self.assertEqual(pkg.colors["waybar"]["background"], "#b00404")
        self.assertNotEqual(pkg.palette["base05"], "#000000")
        self.assertEqual(pkg.wallpaper, "spartan.png")
        yuck = (REPO_ROOT / "themes" / "spartan" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "4%" :y "6%"', yuck)
        self.assertIn(':anchor "top right"', yuck)

    def test_spartan_and_a70_do_not_share_toji_primary(self) -> None:
        toji = ThemePackage.load(REPO_ROOT / "themes" / "toji")
        spartan = ThemePackage.load(REPO_ROOT / "themes" / "spartan")
        a70 = ThemePackage.load(REPO_ROOT / "themes" / "a70")
        self.assertNotEqual(spartan.palette["base0D"], toji.palette["base0D"])
        self.assertNotEqual(a70.palette["base0D"], toji.palette["base0D"])

    def test_music_card_fits_in_a_compact_window(self) -> None:
        scss = (REPO_ROOT / "themes" / "_template" / "eww" / "eww.scss.template").read_text(
            encoding="utf-8"
        )
        self.assertIn("$cover-size: {{identity.cover_size}}px;", scss)
        self.assertIn("min-height: $cover-size;", scss)
        yuck = (REPO_ROOT / "layouts" / "default" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        match = re.search(
            r"\(defwindow music[\s\S]*?:geometry \(geometry :x \S+ :y \S+ :width \S+ :height (\S+)\)",
            yuck,
        )
        self.assertIsNotNone(match)
        height = int(str(match.group(1)).strip('"'))
        self.assertLessEqual(height, 100)


if __name__ == "__main__":
    unittest.main()
