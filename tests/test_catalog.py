#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.theme import ThemePackage
from tests.test_theme import V2_TOML, write_theme


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        themes = self.root / "themes"
        write_theme(themes, V2_TOML.replace('name = "sample"', 'name = "sample"', 1))
        # write_theme uses folder "sample"; keep name in sync
        sample = themes / "sample"
        (sample / "theme.toml").write_text(
            (sample / "theme.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        user = self.root / "user-themes" / "community"
        user.mkdir(parents=True)
        (user / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "community"').replace(
                'display_name = "Sample"', 'display_name = "Community"'
            ),
            encoding="utf-8",
        )
        self.catalog = ThemeCatalog(
            official_root=themes,
            user_root=self.root / "user-themes",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_lists_official_and_user_themes(self) -> None:
        names = [pkg.name for pkg in self.catalog.list()]
        self.assertIn("sample", names)
        self.assertIn("community", names)

    def test_get_by_name(self) -> None:
        pkg = self.catalog.get("community")
        self.assertIsInstance(pkg, ThemePackage)
        self.assertEqual(pkg.display_name, "Community")

    def test_list_visible_hides_export_when_base_exists(self) -> None:
        export = self.root / "user-themes" / "sample-export"
        export.mkdir(parents=True)
        (export / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "sample-export"').replace(
                'display_name = "Sample"', 'display_name = "Sample"'
            ),
            encoding="utf-8",
        )
        visible = [pkg.name for pkg in self.catalog.list_visible()]
        self.assertIn("sample", visible)
        self.assertNotIn("sample-export", visible)
        self.assertIn("sample-export", [pkg.name for pkg in self.catalog.list()])

    def test_skips_template_dir(self) -> None:
        (self.root / "themes" / "_template").mkdir()
        (self.root / "themes" / "_template" / "theme.toml").write_text(
            'name="_template"\n', encoding="utf-8"
        )
        names = [pkg.name for pkg in self.catalog.list()]
        self.assertNotIn("_template", names)


if __name__ == "__main__":
    unittest.main()
