#!/usr/bin/env python3

from __future__ import annotations

import unittest

from hypraesthetic.waybar_css import set_bar_font, theme_waybar_css


class WaybarCssTests(unittest.TestCase):
    def test_named_red_becomes_primary(self) -> None:
        css = '@import "colors.css";\n@define-color red #c7c7c7;\n@define-color bg #111111;\n'
        out = theme_waybar_css(css)
        self.assertIn("@define-color red @primary;", out)
        self.assertIn("@define-color bg @background;", out)

    def test_active_hex_and_hover_follow_primary(self) -> None:
        css = """
@import "colors.css";
#workspaces button.active {
    background-color: #fabd2f;
    color: #282828;
}
#clock:hover {
    color: #fabd2f;
}
#battery.critical {
    color: #f53c3c;
}
"""
        out = theme_waybar_css(css)
        self.assertIn("background-color: @primary", out)
        self.assertIn("color: @primary_fg", out)
        self.assertIn("#clock:hover {\n    color: @primary;", out)
        self.assertIn("#battery.critical {\n    color: #f53c3c;", out)

    def test_active_empty_keeps_readable_on_primary_pill(self) -> None:
        css = """
#workspaces button.active {
    background: @primary;
    color: @primary_fg;
}
#workspaces button.active.empty {
    color: @primary;
}
"""
        out = theme_waybar_css(css)
        self.assertRegex(out, r"button.active.empty\s*\{[^}]*color: @primary_fg")
        self.assertNotRegex(out, r"button.active.empty\s*\{[^}]*color: @primary;")

    def test_text_only_active_uses_primary(self) -> None:
        css = """
@import "colors.css";
#workspaces button.active {
  color: @foreground;
}
"""
        out = theme_waybar_css(css)
        self.assertIn("color: @primary", out)
        self.assertNotIn("color: @foreground", out)

    def test_love_alias_becomes_primary(self) -> None:
        out = theme_waybar_css("@define-color love #eb6f92;\n")
        self.assertIn('@import "colors.css"', out)
        self.assertIn("@define-color love @primary;", out)

    def test_primary_fill_uses_primary_fg(self) -> None:
        css = """
#workspaces button.focused {
    background: @primary;
    color: @foreground;
}
#workspaces button.active {
    color: @bg;
    background: alpha(@red, 1);
}
"""
        out = theme_waybar_css(css)
        self.assertIn("background: @primary", out)
        self.assertIn("color: @primary_fg", out)
        self.assertNotIn("color: @foreground", out)
        self.assertNotIn("color: @bg;", out)

    def test_inverted_active_keeps_readable_contrast(self) -> None:
        css = """
#workspaces button.active {
    background-color: alpha(@foreground, 0.9);
    color: @primary;
}
#clock {
    background-color: alpha(@foreground, 0.65);
    color: @background;
}
"""
        out = theme_waybar_css(css)
        self.assertIn("background-color: @primary", out)
        self.assertIn("color: @primary_fg", out)
        self.assertIn("#clock {\n    background-color: alpha(@foreground, 0.65);\n    color: @background;", out)

    def test_washed_out_text_on_light_pill_is_opaque(self) -> None:
        css = """
#mpris {
    background-color: alpha(@foreground, 0.65);
    color: alpha(@background, 0.45);
}
"""
        out = theme_waybar_css(css)
        self.assertIn("color: @background", out)
        self.assertNotIn("alpha(@background, 0.45)", out)

    def test_stale_module_selectors_are_removed(self) -> None:
        css = """
#custom-weather,
#clock,
#custom-omarchy {
    min-width: 14px;
}
#l1 #custom-omarchy {
    border: none;
}
#custom-voxtype.recording {
    color: @primary;
}
#custom-gpu-usage {
    color: @foreground;
}
"""
        out = theme_waybar_css(css)
        self.assertIn("#clock", out)
        self.assertNotIn("custom-weather", out)
        self.assertNotIn("custom-omarchy", out)
        self.assertNotIn("custom-voxtype", out)
        self.assertNotIn("custom-gpu-usage", out)

    def test_single_quoted_font_is_replaced(self) -> None:
        css = "* { font-family: 'CaskaydiaMono Nerd Font Propo'; }"
        out = set_bar_font(css, "JetBrainsMono Nerd Font")
        self.assertIn('font-family: "JetBrainsMono Nerd Font"', out)
        self.assertNotIn("CaskaydiaMono", out)

    def test_known_hex_define_and_themed_alpha_stay_correct(self) -> None:
        css = """
@define-color fg2 #df6124;
@define-color hover_bg #665B32;
@define-color hover_fg #1e1e1e;
@define-color border alpha(@foreground, 0.1);
@define-color already @foreground;
#cpu.critical { color: #df6124; }
"""
        out = theme_waybar_css(css)
        self.assertIn("@define-color fg2 @primary;", out)
        self.assertIn("@define-color hover_bg @primary;", out)
        self.assertIn("@define-color hover_fg @primary_fg;", out)
        self.assertIn("@define-color border alpha(@foreground, 0.1);", out)
        self.assertIn("@define-color already @foreground;", out)
        self.assertIn("#cpu.critical { color: #df6124; }", out)


if __name__ == "__main__":
    unittest.main()
