#!/usr/bin/env python3
"""Score candidate eww widget placements against a wallpaper's real pixels.

Usage:
  placement_check.py <wallpaper> <fg_hex> <x%> <y%> <w%> <h%> [...]
Coordinates are percentages; values may carry % or px.
"""
from __future__ import annotations

import sys
from PIL import Image


def lum(rgb):
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (v / 255 for v in rgb)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def main() -> int:
    wall, fg = sys.argv[1], sys.argv[2]
    img = Image.open(wall).convert("RGB")
    # Real screen geometry is authored against the full-resolution wallpaper.
    ref_w, ref_h = img.size
    img = img.resize((192, 108))
    px = img.load()
    W, H = img.size
    f = lum(tuple(int(fg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)))

    def pxval(v, ref_axis, grid_axis):
        """Percentages resolve against the real wallpaper; bare numbers are screen px
        authored for a 1920x1080-class desktop, so scale them onto the wallpaper."""
        v = str(v)
        if v.endswith("%"):
            return float(v[:-1]) / 100 * grid_axis
        return float(v) / 1920 * ref_axis / ref_axis * grid_axis

    args = sys.argv[3:]
    for i in range(0, len(args), 5):
        name, xv, yv, wv, hv = args[i:i + 5]
        x = pxval(xv, ref_w, W)
        y = pxval(yv, ref_h, H)
        w = pxval(wv, ref_w, W)
        h = pxval(hv, ref_h, H)
        l = max(0, min(int(x), W - 1))
        t = max(0, min(int(y), H - 1))
        r = max(l + 1, min(int(x + w) + 1, W))
        b = max(t + 1, min(int(y + h) + 1, H))
        samples = [lum(px[xp, yp]) for yp in range(t, b) for xp in range(l, r)]
        back = max(samples) if f > 0.5 else min(samples)
        print(f"{name:14s} worst={ratio(f, back):6.2f}:1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
