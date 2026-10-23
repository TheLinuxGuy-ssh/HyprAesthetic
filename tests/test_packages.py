#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

from hypraesthetic.packages import PackageCatalog

ROOT = Path(__file__).resolve().parents[1]


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

    def test_arch_hyprwave_is_the_aur_release_not_a_missing_git_pkg(self) -> None:
        item = self.catalog.component("hyprwave")
        self.assertEqual(item.packages_for("arch"), ["hyprwave"])
        self.assertIn("hyprwave", self.catalog.aur_names("arch"))
        self.assertNotIn("hyprwave", self.catalog.aur_names("fedora"))

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

    def test_cachyos_uses_arch_family(self) -> None:
        family = self.catalog.family_for("cachyos")
        self.assertEqual(family.name, "arch")
        self.assertEqual(family.manager, "pacman")

    def test_os_release_ids_include_id_like(self) -> None:
        from hypraesthetic.packages import os_release_ids
        ids = os_release_ids('ID=cachyos\nID_LIKE=arch\n')
        self.assertEqual(ids[0], "cachyos")
        self.assertIn("arch", ids)

    def test_family_for_ids_falls_back_to_id_like(self) -> None:
        family = self.catalog.family_for_ids(["unknown-arch-spin", "arch"])
        self.assertEqual(family.name, "arch")

    def test_distro_detect_arch_case_includes_cachyos(self) -> None:
        text = (ROOT / "scripts/lib/distro-detect.sh").read_text(encoding="utf-8")
        self.assertIn("arch|manjaro|endeavouros|garuda|cachyos)", text)
        self.assertIn('[[ " ${ID_LIKE:-} " == *" arch "* ]]', text)

    def test_install_deps_arch_regex_includes_cachyos(self) -> None:
        text = (ROOT / "scripts/install-deps.sh").read_text(encoding="utf-8")
        self.assertIn("^(arch|manjaro|endeavouros|garuda|cachyos)$", text)


if __name__ == "__main__":
    unittest.main()
