"""Control-center page registry (importable without GTK)."""

from __future__ import annotations

PAGES: list[tuple[str, str, str]] = [
    ("presets", "Presets", "Theme tiles with live apply"),
    ("bar", "Bar", "Independent Waybar layouts"),
    ("widgets", "Widgets", "Desktop overlays and placement"),
    ("fonts", "Fonts", "Interface, bar, and terminal fonts"),
    ("apps", "Apps", "Default file manager, terminal, browser, launcher"),
    ("look", "Look", "Wallpaper, GTK, icons, hyprwave"),
    ("store", "Store", "Search and install themes"),
    ("doctor", "Doctor", "Missing packages and repair"),
]
