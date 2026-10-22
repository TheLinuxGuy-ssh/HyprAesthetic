#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

from hypraesthetic.packages import PackageCatalog


class PackageCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = PackageCatalog.load()

    def test_fedora_asahi_uses_fedora_family(self) -> None:
        family = self.catalog.family_for("fedora-asahi-remix")
        self.assertEqual(family.manager, "dnf")
        self.assertEqual(family.name, "fedora")

    def test_required_includes_hyprland_and_portal(self) -> None:
        names = {item.id for item in self.catalog.required()}
        self.assertIn("hyprland", names)
        self.assertIn("portal", names)
        self.assertIn("fonts", names)

    def test_optional_hyprwave_on_debian(self) -> None:
        item = self.catalog.component("hyprwave")
        self.assertFalse(item.required)
        self.assertEqual(item.packages_for("debian"), [])

    def test_selection_adds_file_manager_packages(self) -> None:
        pkgs = self.catalog.packages_for_selection(
            "arch",
            {"file_manager": "nautilus", "terminal": "kitty", "bar": "waybar"},
        )
        self.assertIn("hyprland", pkgs)
        self.assertIn("nautilus", pkgs)
        self.assertIn("kitty", pkgs)
        self.assertIn("waybar", pkgs)

    def test_unknown_distro_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.catalog.family_for("haiku")


if __name__ == "__main__":
    unittest.main()
