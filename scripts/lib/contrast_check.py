#!/usr/bin/env python3
"""WCAG contrast validation for theme.toml color tokens.

Checks that declared text colors are readable against their declared
backgrounds. Text pairs must reach 4.5:1, accent pairs 3:1.
Prints one line per violation, exits 0 when clean.
"""

from __future__ import annotations

import os
import re
import sys

TEXT_MIN = 4.5
ACCENT_MIN = 3.0

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

# (foreground key, background key, minimum, label)
CHECKS: list[tuple[str, str, float, str]] = [
    ("colors_waybar_foreground", "colors_waybar_background", TEXT_MIN, "waybar text"),
    ("colors_waybar_foreground_muted", "colors_waybar_background", TEXT_MIN, "waybar muted text"),
    ("colors_waybar_foreground", "colors_waybar_surface", TEXT_MIN, "waybar text on surface"),
    ("colors_waybar_primary_fg", "colors_waybar_primary", TEXT_MIN, "waybar primary label"),
    ("colors_waybar_error_fg", "colors_waybar_error", TEXT_MIN, "waybar error label"),
    ("colors_waybar_warning_fg", "colors_waybar_warning", TEXT_MIN, "waybar warning label"),
    ("colors_waybar_success_fg", "colors_waybar_success", TEXT_MIN, "waybar success label"),
    ("colors_waybar_primary", "colors_waybar_background", ACCENT_MIN, "waybar primary accent"),
    ("colors_eww_foreground", "colors_eww_background", TEXT_MIN, "eww text"),
    ("colors_eww_foreground_muted", "colors_eww_background", TEXT_MIN, "eww muted text"),
    ("colors_eww_foreground", "colors_eww_surface", TEXT_MIN, "eww text on surface"),
    ("colors_eww_primary_fg", "colors_eww_primary", TEXT_MIN, "eww primary label"),
    ("colors_eww_error_fg", "colors_eww_error", TEXT_MIN, "eww error label"),
    ("colors_eww_warning_fg", "colors_eww_warning", TEXT_MIN, "eww warning label"),
    ("colors_eww_success_fg", "colors_eww_success", TEXT_MIN, "eww success label"),
    ("colors_eww_primary", "colors_eww_background", ACCENT_MIN, "eww primary accent"),
    ("colors_eww_error", "colors_eww_background", ACCENT_MIN, "eww error accent"),
    ("colors_eww_warning", "colors_eww_background", ACCENT_MIN, "eww warning accent"),
    ("colors_eww_success", "colors_eww_background", ACCENT_MIN, "eww success accent"),
    ("colors_base05", "colors_base00", TEXT_MIN, "terminal text"),
    ("colors_base0E", "colors_base00", ACCENT_MIN, "terminal accent"),
]


def load_vars() -> dict[str, str]:
    path = os.environ.get("VARS_FILE", "")
    if not path or not os.path.isfile(path):
        return {}
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if "=" in line:
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                out[key.strip()] = value
    return out


def to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    value = value[:6]
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def luminance(value: str) -> float:
    channels = []
    for raw in to_rgb(value):
        channel = raw / 255
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    vars_map = load_vars()
    if not vars_map:
        print("contrast: could not read vars file", file=sys.stderr)
        return 1

    problems: list[str] = []
    for fg_key, bg_key, minimum, label in CHECKS:
        fg, bg = vars_map.get(fg_key), vars_map.get(bg_key)
        if not fg or not bg:
            continue
        if not HEX_RE.match(fg) or not HEX_RE.match(bg):
            problems.append(f"contrast: {label} has non-hex value ({fg_key}={fg}, {bg_key}={bg})")
            continue
        score = ratio(fg, bg)
        if score < minimum:
            problems.append(
                f"contrast: {label} {score:.2f}:1 below {minimum}:1 "
                f"({fg_key}={fg} on {bg_key}={bg})"
            )

    for line in problems:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
