#!/usr/bin/env python3
"""CI checks for theme.toml parsing and template rendering."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from hypraesthetic.render import render_string
from hypraesthetic.theme import ThemePackage


def test_theme_toml() -> None:
    pkg = ThemePackage.load(ROOT / "themes" / "cyberpunk")
    assert pkg.name == "cyberpunk"
    assert pkg.palette["base00"] == "#0d0d0d"
    assert pkg.enabled("waybar")
    print(f"Theme: {pkg.name}")
    print(f"Palette: {len(pkg.palette)}")
    print(f"Components: {pkg.components}")


def test_waybar_template() -> None:
    pkg = ThemePackage.load(ROOT / "themes" / "cyberpunk")
    rendered = render_string(
        (ROOT / "themes" / "_template" / "waybar" / "colors.css.template").read_text(),
        pkg.flatten(),
    )
    assert "@define-color background" in rendered
    assert "@define-color love @primary" in rendered
    assert "#0d0d0d" in rendered
    print("Waybar template OK")


def test_hyprland_template() -> None:
    pkg = ThemePackage.load(ROOT / "themes" / "cyberpunk")
    rendered = render_string(
        (ROOT / "themes" / "_template" / "hypr" / "colors.conf.template").read_text(),
        pkg.flatten(),
    )
    assert "active_border = #00f0ff" in rendered
    print("Hyprland template OK")


def test_hyprwave_template() -> None:
    pkg = ThemePackage.load(ROOT / "themes" / "cyberpunk")
    rendered = render_string(
        (ROOT / "themes" / "_template" / "hyprwave" / "config.toml.template").read_text(),
        pkg.flatten(),
    )
    assert 'background = "#0d0d0d"' in rendered
    print("Hyprwave template OK")


def test_all_theme_tomls() -> None:
    for theme_file in sorted(ROOT.glob("themes/*/theme.toml")):
        if theme_file.parent.name == "_template":
            continue
        pkg = ThemePackage.load(theme_file.parent)
        assert pkg.name
        assert pkg.palette["base00"].startswith("#")
        print(f"OK: {pkg.name}")


def main() -> int:
    test_theme_toml()
    test_waybar_template()
    test_hyprland_template()
    test_hyprwave_template()
    test_all_theme_tomls()
    print("All template tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
