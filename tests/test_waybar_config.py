#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

from hypraesthetic.waybar_config import sanitize_waybar_config


class WaybarConfigTests(unittest.TestCase):
    def test_strips_omarchy_module_and_fixes_window_rewrite(self) -> None:
        raw = """
{
  "modules-right": ["clock", "custom/voxtype", "tray"],
  "hyprland/workspaces": {
    "window-rewrite": { "custom/voxtype": {
      "exec": "omarchy-voxtype-status",
      "format": "{icon}"
    },
      "class<firefox>": "browser"
    }
  },
  "custom/omarchy": { "on-click": "omarchy-menu" }
}
"""
        out = sanitize_waybar_config(raw)
        self.assertNotIn("custom/voxtype", out)
        self.assertNotIn("custom/omarchy", out)
        self.assertNotIn("omarchy-voxtype-status", out)
        self.assertIn("class<firefox>", out)
        self.assertIn('"clock"', out)
        self.assertIn('"tray"', out)

    def test_drops_stale_exec_modules(self) -> None:
        raw = """
{
  "modules": ["cpu", "custom/gpu"],
  "custom/gpu": {
    "exec": "gpu-usage-waybar --text-format hi"
  }
}
"""
        out = sanitize_waybar_config(raw)
        self.assertNotIn("custom/gpu", out)
        self.assertNotIn("gpu-usage-waybar", out)
        self.assertIn('"cpu"', out)

    def test_replaces_omarchy_clicks_and_drops_unused_custom(self) -> None:
        raw = """
{
  "modules-right": ["pulseaudio", "battery"],
  "pulseaudio": {
    "on-click": "omarchy-launch-or-focus-tui wiremix"
  },
  "battery": {
    "on-click-right": "notify-send -u low \\"$(omarchy-battery-status)\\""
  },
  "custom/windowpill": {
    "exec": "~/.config/waybar/window_pill.py"
  }
}
"""
        out = sanitize_waybar_config(raw)
        self.assertIn("pavucontrol", out)
        self.assertNotIn("omarchy-", out)
        self.assertNotIn("custom/windowpill", out)
        self.assertNotIn("window_pill.py", out)
        self.assertIn("pulseaudio", out)
        self.assertIn("battery", out)

    def test_strips_nul_bytes(self) -> None:
        out = sanitize_waybar_config('{"modules": ["clock"]}\n\x00')
        self.assertNotIn("\x00", out)
        self.assertIn("clock", out)

    def test_missing_exclusive_is_injected(self) -> None:
        out = sanitize_waybar_config('{\n  "position": "top"\n}\n')
        self.assertIn('"exclusive"', out)
        self.assertIn('"exclusive": true', out)
        self.assertLess(out.find("{"), out.find('"exclusive"'))

    def test_explicit_exclusive_false_is_kept(self) -> None:
        raw = '{\n  "exclusive": false,\n  "position": "top"\n}\n'
        out = sanitize_waybar_config(raw)
        self.assertIn('"exclusive": false', out)
        self.assertNotIn('"exclusive": true', out)
        self.assertEqual(out.count('"exclusive"'), 1)

    def test_cyberpunk_config_sets_exclusive(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "layouts" / "bars" / "cyberpunk" / "config.jsonc").read_text(encoding="utf-8")
        self.assertIn('"exclusive": true', text)


if __name__ == "__main__":
    unittest.main()
