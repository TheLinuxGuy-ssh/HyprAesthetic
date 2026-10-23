#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

from hypraesthetic.bar_schematic import modules_for_bar
from hypraesthetic.discover import bar_display_name

_REPO = Path(__file__).resolve().parents[1]
_CAPSULE = (
    ["hyprland/workspaces", "custom/separator", "tray", "idle_inhibitor", "custom/separator2", "mpris"],
    ["custom/separator", "custom/clock", "custom/separator2"],
    [
        "custom/separator",
        "bluetooth",
        "custom/separator3",
        "backlight",
        "custom/separator4",
        "power-profiles-daemon",
        "custom/separator3",
        "pulseaudio",
        "custom/separator3",
        "cpu",
        "custom/separator3",
        "memory",
        "custom/separator4",
        "battery",
    ],
)
_COMPACT = (
    ["hyprland/workspaces"],
    ["custom/clock"],
    ["pulseaudio", "battery", "tray"],
)


_ENGLISH = (
    ("v1", "Top split", "Workspaces left, tray right"),
    ("v1.1", "Toji thin", "Slim top bar"),
    ("v1.2", "Light clash", "Used with Toji vs Sukuna"),
    ("v2", "Red island", "Rounded modules"),
    ("v2.9e", "Capsule dock", "Centered workspaces with meters"),
    ("v3", "Violet modules", "Used with Choso"),
    ("v4", "Ember", "Used with Tanjiro"),
    ("v5", "Night City classic", "Flat modules with window title"),
    ("v7", "Sky slim", "Open-air bar"),
    ("default", "Capsule", "Rounded island bar"),
    ("compact", "Compact", "Workspaces, clock, and tray"),
    ("a70", "Dock", "Centered workspaces with meters"),
    ("cyberpunk", "Night City", "Flat modules with window title"),
    ("none", "Hide the bar", "No status bar"),
)


class BarSchematicTests(unittest.TestCase):
    def test_modules_for_bar_reads_three_groups(self) -> None:
        text = '{ /* c */ "modules-left": ["work", "clock"], "modules-center": [], "modules-right": ["tray"] }'
        left, center, right = modules_for_bar(text)
        self.assertEqual(left, ["work", "clock"])
        self.assertEqual(center, [])
        self.assertEqual(right, ["tray"])

    def test_modules_for_bar_strips_line_comments_and_keeps_strings(self) -> None:
        text = """
        {
          // lead
          "modules-left": ["hyprland/workspaces"],
          "modules-center": ["custom/clock"], /* mid */
          "modules-right": ["tray"], // end
          "format": "http://example.com",
          "note": "keep /* inside */"
        }
        """
        left, center, right = modules_for_bar(text)
        self.assertEqual(left, ["hyprland/workspaces"])
        self.assertEqual(center, ["custom/clock"])
        self.assertEqual(right, ["tray"])

    def test_modules_for_bar_drops_trailing_commas_left_by_comments(self) -> None:
        text = """
        {
          "modules-left": ["hyprland/workspaces",],
          "modules-center": ["custom/clock"],
          "modules-right": ["tray"],
          "status-icons": { "paused": "x" },
          //"ignored-players": ["firefox"]
        }
        """
        left, center, right = modules_for_bar(text)
        self.assertEqual(left, ["hyprland/workspaces"])
        self.assertEqual(center, ["custom/clock"])
        self.assertEqual(right, ["tray"])

    def test_shipped_capsule_and_compact_configs_have_modules(self) -> None:
        capsule = (_REPO / "layouts" / "bars" / "default" / "config.jsonc").read_text(encoding="utf-8")
        compact = (_REPO / "layouts" / "bars" / "compact" / "config.jsonc").read_text(encoding="utf-8")
        self.assertEqual(modules_for_bar(capsule), _CAPSULE)
        self.assertEqual(modules_for_bar(compact), _COMPACT)
        self.assertTrue(all(_CAPSULE))
        self.assertTrue(all(_COMPACT))

    def test_modules_for_bar_returns_empty_groups_on_parse_error(self) -> None:
        self.assertEqual(modules_for_bar("not json"), ([], [], []))
        self.assertEqual(modules_for_bar(""), ([], [], []))
        left, center, right = modules_for_bar(
            '{"modules-left": ["ok", 1, {"a": 1}], "modules-center": "nope"}'
        )
        self.assertEqual(left, ["ok"])
        self.assertEqual(center, [])
        self.assertEqual(right, [])

    def test_bar_display_name_never_uses_raw_version_as_title(self) -> None:
        title, blurb = bar_display_name("v2.9e")
        self.assertEqual(title, "Capsule dock")
        self.assertNotEqual(title, "v2.9e")
        self.assertEqual(blurb, "Centered workspaces with meters")
        title, blurb = bar_display_name("v6.ab2")
        self.assertEqual(title, "Waybar layout")
        self.assertEqual(blurb, "v6.ab2")

    def test_bar_display_name_uses_the_english_map(self) -> None:
        for style_id, title, blurb in _ENGLISH:
            self.assertEqual(bar_display_name(style_id), (title, blurb))
            self.assertEqual(bar_display_name(style_id, "   "), (title, blurb))

    def test_bar_toml_name_wins_when_non_empty(self) -> None:
        title, blurb = bar_display_name("v2.9e", "Island")
        self.assertEqual(title, "Island")
        self.assertEqual(blurb, "Centered workspaces with meters")
        title, blurb = bar_display_name("v6.ab2", "Harbor")
        self.assertEqual(title, "Harbor")
        self.assertEqual(blurb, "v6.ab2")
        title, blurb = bar_display_name("v1", "V1")
        self.assertEqual(title, "V1")
        self.assertEqual(blurb, "Workspaces left, tray right")
