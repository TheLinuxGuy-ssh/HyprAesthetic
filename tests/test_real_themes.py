#!/usr/bin/env python3

from __future__ import annotations

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
        self.assertIn("cyberpunk", names)
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


if __name__ == "__main__":
    unittest.main()
