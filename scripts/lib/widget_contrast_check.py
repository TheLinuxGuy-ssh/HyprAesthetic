#!/usr/bin/env python3
"""Widget text contrast against the wallpaper it sits on.

eww widgets are overlays: the text color comes from theme.toml while the
backdrop is whatever the wallpaper has in that region. This samples the region
each widget occupies and checks the real contrast ratio.

Widgets drawn on a translucent panel (.panel class) are checked against the
panel surface token instead, since the wallpaper no longer shows through
directly behind the glyphs.

Only widgets listed in the theme's [eww] default_widgets are checked, since
those are the ones that actually get opened. Prints one advisory line per risky
widget, exits 0 always.
"""

from __future__ import annotations

import os
import re
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow missing
    print("widget-contrast: Pillow unavailable, skipping", file=sys.stderr)
    sys.exit(0)

TEXT_MIN = 4.5
# Large display type (clock digits, big labels) may use the WCAG large-text floor.
LARGE_TEXT_MIN = 3.0
DECORATIVE_MIN = 2.0

DEFWINDOW_RE = re.compile(
    r"\(defwindow\s+([A-Za-z0-9_-]+)(.*?)(?=\(defwindow\s|\(defwidget|\Z)",
    re.DOTALL | re.IGNORECASE,
)
GEOMETRY_RE = re.compile(r"\(geometry\s*:(.*?)\)", re.DOTALL | re.IGNORECASE)
KEYVAL_RE = re.compile(r':([A-Za-z0-9_-]+)\s*(?:"([^"]*)"|(\S+))')
SCREEN_RE = re.compile(r":screen\s+(\d+)")
GEOM_OPEN_RE = re.compile(r"\(geometry\b")
DEFWIDGET_RE = re.compile(r"\(defwidget\s+([A-Za-z0-9_-]+)(.*?)(?=\(defwidget|\(defwindow|\Z)", re.DOTALL)

# Widgets whose text is mostly transparent or purely decorative.
DECORATIVE = {"matrix"}
# Widgets rendered at large font sizes.
LARGE = {"clock"}

SAMPLE_W, SAMPLE_H = 192, 108


def load_vars() -> dict[str, str]:
    path = os.environ.get("VARS_FILE", "")
    out: dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if "=" in line:
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                out[key.strip()] = value
    return out


def parse_windows(yuck: str) -> dict[str, dict[str, str]]:
    windows: dict[str, dict[str, str]] = {}
    for match in DEFWINDOW_RE.finditer(yuck):
        name = match.group(1)
        body = match.group(2)

        geom = GEOMETRY_RE.search(body)
        if not geom:
            continue

        # Only look at the defwindow header, i.e. text before the geometry call.
        header = body[: GEOM_OPEN_RE.search(body).start()] if GEOM_OPEN_RE.search(body) else body

        attrs: dict[str, str] = {}
        # Re-add the leading colon consumed by the geometry regex so the first
        # key (x) matches KEYVAL_RE the same way as the rest.
        for key, quoted, bare in KEYVAL_RE.findall(":" + geom.group(1)):
            attrs[key] = quoted if quoted else bare
        screen = SCREEN_RE.search(header)
        attrs["_screen"] = screen.group(1) if screen else "0"
        windows[name] = attrs
    return windows


def parse_panels(yuck: str) -> set[str]:
    """Widgets whose root box carries the .panel class."""
    panels = set()
    for match in DEFWIDGET_RE.finditer(yuck):
        body = match.group(2)
        for cls in re.findall(r':class\s+"([^"]*)"', body):
            if re.search(r"\bpanel\b", cls):
                panels.add(match.group(1))
                break
    return panels


def parse_default_widgets(vars_map: dict[str, str]) -> list[str]:
    raw = vars_map.get("eww_default_widgets", "")
    return [w.strip().strip("'\"") for w in raw.strip("[]").split(",") if w.strip()]


def resolve(value: str, axis_total: int) -> float:
    """Percentages resolve against the axis; bare numbers are screen pixels."""
    value = str(value).strip()
    if value.endswith("%"):
        try:
            return float(value[:-1]) / 100.0 * axis_total
        except ValueError:
            return 0.0
    match = re.match(r"^(\d+)", value)
    if match:
        # Widget geometry px are authored for a 1920-wide desktop.
        return float(match.group(1)) / 1920 * axis_total
    return 0.0


def luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for raw in rgb:
        channel = raw / 255
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: float, b: float) -> float:
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    value = value[:6]
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return 0, 0, 0


def main() -> int:
    yuck_path = os.environ.get("YUCK", "")
    wallpaper = os.environ.get("WALLPAPER", "")
    if not yuck_path or not os.path.isfile(yuck_path):
        return 0

    vars_map = load_vars()
    widgets = parse_default_widgets(vars_map)
    if not widgets:
        return 0

    fg_value = vars_map.get("colors_eww_foreground")
    surface_value = vars_map.get("colors_eww_surface", "#000000")
    primary_key = "colors_eww_primary"
    text_key = "colors_eww_foreground"
    if not fg_value:
        return 0

    with open(yuck_path, encoding="utf-8") as handle:
        yuck_text = handle.read()
    windows = parse_windows(yuck_text)
    panels = parse_panels(yuck_text)
    if not windows:
        return 0

    need_wallpaper = any(w not in panels for w in widgets)
    image = None
    if need_wallpaper:
        if not wallpaper or not os.path.isfile(wallpaper):
            return 0
        try:
            image = Image.open(wallpaper).convert("RGB")
        except Exception:
            return 0

    img_w, img_h = image.size if image else (0, 0)
    small = image.resize((SAMPLE_W, SAMPLE_H)) if image else None
    pixels = small.load() if small else None

    for widget in widgets:
        attrs = windows.get(widget)
        if not attrs:
            continue
        # Widgets on the secondary screen sit on their own bg, not the wallpaper.
        if attrs.get("_screen") == "1":
            continue

        if widget in LARGE:
            minimum = LARGE_TEXT_MIN
        elif widget in DECORATIVE:
            minimum = DECORATIVE_MIN
        else:
            minimum = TEXT_MIN

        fg_lum = luminance(to_rgb(fg_value))

        if widget in panels:
            # Text sits on the panel surface, not directly on the wallpaper.
            backdrop = luminance(to_rgb(surface_value))
            where = "panel surface"
        else:
            if pixels is None:
                continue
            x = resolve(attrs.get("x", "0"), img_w)
            y = resolve(attrs.get("y", "0"), img_h)
            w = resolve(attrs.get("width", "0"), img_w)
            h = resolve(attrs.get("height", "0"), img_h)
            if w <= 0 or h <= 0:
                continue

            left = max(0, min(int(x / img_w * SAMPLE_W), SAMPLE_W - 1))
            top = max(0, min(int(y / img_h * SAMPLE_H), SAMPLE_H - 1))
            right = max(left + 1, min(int((x + w) / img_w * SAMPLE_W) + 1, SAMPLE_W))
            bottom = max(top + 1, min(int((y + h) / img_h * SAMPLE_H) + 1, SAMPLE_H))

            samples = [luminance(pixels[px, py]) for py in range(top, bottom) for px in range(left, right)]
            if not samples:
                continue
            # Worst case: brightest backdrop for light text, darkest for dark text.
            backdrop = max(samples) if fg_lum > 0.5 else min(samples)
            where = "wallpaper"

        score = ratio(fg_lum, backdrop)
        if score < minimum:
            print(
                f"widget '{widget}' {score:.2f}:1 vs {where} (needs {minimum}:1) "
                f"at {attrs.get('x','?')},{attrs.get('y','?')} — "
                f"move it to a calmer region, add the .panel class, "
                f"or adjust {text_key}/{primary_key}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
