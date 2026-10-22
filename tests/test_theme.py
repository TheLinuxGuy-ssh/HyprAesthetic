#!/usr/bin/env python3
"""Theme package schema, palette resolution, and component flags."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from hypraesthetic.theme import ThemeError, ThemePackage


def write_theme(root: Path, body: str) -> Path:
    theme_dir = root / "sample"
    theme_dir.mkdir(parents=True)
    (theme_dir / "theme.toml").write_text(dedent(body).lstrip(), encoding="utf-8")
    return theme_dir


V2_TOML = """
schema = 2
name = "sample"
display_name = "Sample"
description = "A test theme"
author = "tester"
version = "1.2.0"
license = "MIT"
min_hypraesthetic = "0.2.0"

[misc]
wallpaper = "sample.png"
hw_theme = "octane"

[palette]
base00 = "#0d0d0d"
base01 = "#1a1a1a"
base02 = "#2a2a2a"
base03 = "#3a3a3a"
base04 = "#cccccc"
base05 = "#ffffff"
base06 = "#ffffff"
base07 = "#ffffff"
base08 = "#ff6b6b"
base09 = "#ff9f43"
base0A = "#ffe66d"
base0B = "#69db7c"
base0C = "#5fe4ff"
base0D = "#74b9ff"
base0E = "#a29bfe"
base0F = "#ff7675"

[colors.hyprland]
border_active = "{{palette.base0D}}"
border_inactive = "{{palette.base03}}"
shadow = "{{palette.base00}}aa"

[colors.waybar]
background = "{{palette.base00}}"
foreground = "{{palette.base05}}"
primary = "{{palette.base0D}}"
primary_fg = "{{palette.base00}}"

[layout]
bar = "waybar"
launcher = "rofi"
widgets = ["clock", "system"]

[defaults]
file_manager = "nautilus"
terminal = "kitty"

[components]
hyprland = true
waybar = false
hyprwave = true
eww = true
rofi = true
kitty = true
gtk = true
dunst = true
nvim = true
"""


class ThemePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_load_resolves_palette_references(self) -> None:
        pkg = ThemePackage.load(write_theme(self.root, V2_TOML))
        self.assertEqual(pkg.colors["hyprland"]["border_active"], "#74b9ff")
        self.assertEqual(pkg.colors["hyprland"]["shadow"], "#0d0d0daa")
        self.assertEqual(pkg.colors["waybar"]["background"], "#0d0d0d")

    def test_missing_component_colors_fill_from_palette(self) -> None:
        pkg = ThemePackage.load(write_theme(self.root, V2_TOML))
        self.assertEqual(pkg.colors["eww"]["background"], "#0d0d0d")
        self.assertEqual(pkg.colors["eww"]["error"], "#ff6b6b")
        self.assertEqual(pkg.colors["waybar"]["success"], "#69db7c")

    def test_components_are_honored(self) -> None:
        pkg = ThemePackage.load(write_theme(self.root, V2_TOML))
        self.assertTrue(pkg.enabled("hyprland"))
        self.assertFalse(pkg.enabled("waybar"))
        self.assertTrue(pkg.enabled("eww"))

    def test_layout_and_defaults(self) -> None:
        pkg = ThemePackage.load(write_theme(self.root, V2_TOML))
        self.assertEqual(pkg.layout["bar"], "waybar")
        self.assertEqual(pkg.widgets, ["clock", "system"])
        self.assertEqual(pkg.defaults["file_manager"], "nautilus")
        self.assertEqual(pkg.quotes, [])

    def test_flatten_exposes_template_keys(self) -> None:
        pkg = ThemePackage.load(write_theme(self.root, V2_TOML))
        flat = pkg.flatten()
        self.assertEqual(flat["colors_base00"], "#0d0d0d")
        self.assertEqual(flat["palette_base0D"], "#74b9ff")
        self.assertEqual(flat["colors_hyprland_border_active"], "#74b9ff")
        self.assertEqual(flat["colors_waybar_background"], "#0d0d0d")
        self.assertEqual(flat["hypr_gaps_in"], "5")
        self.assertEqual(flat["hypr_gaps_out"], "7")
        self.assertEqual(flat["hypr_border_size"], "1")
        self.assertEqual(flat["hypr_rounding"], "10")

    def test_legacy_colors_table_is_accepted_as_palette(self) -> None:
        body = """
        name = "legacy"
        display_name = "Legacy"
        author = "old"
        version = "1.0.0"
        [colors]
        base00 = "#111111"
        base01 = "#222222"
        base02 = "#333333"
        base03 = "#444444"
        base04 = "#aaaaaa"
        base05 = "#eeeeee"
        base06 = "#eeeeee"
        base07 = "#ffffff"
        base08 = "#ff0000"
        base09 = "#ff8800"
        base0A = "#ffff00"
        base0B = "#00ff00"
        base0C = "#00ffff"
        base0D = "#0000ff"
        base0E = "#ff00ff"
        base0F = "#888888"
        [components]
        waybar = true
        """
        pkg = ThemePackage.load(write_theme(self.root, body))
        self.assertEqual(pkg.palette["base00"], "#111111")
        self.assertEqual(pkg.colors["waybar"]["primary"], "#0000ff")

    def test_validate_rejects_missing_identity(self) -> None:
        theme_dir = write_theme(self.root, 'schema = 2\nname = "x"\n')
        with self.assertRaises(ThemeError):
            ThemePackage.load(theme_dir)

    def test_explicit_component_hex_is_kept(self) -> None:
        body = V2_TOML + '\n[colors.eww]\nbackground = "#dbeaf5"\nforeground = "#1c2740"\n'
        pkg = ThemePackage.load(write_theme(self.root, body))
        self.assertEqual(pkg.colors["eww"]["background"], "#dbeaf5")
        self.assertEqual(pkg.colors["eww"]["foreground"], "#1c2740")


if __name__ == "__main__":
    unittest.main()
