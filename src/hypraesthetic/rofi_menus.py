"""Data helpers for rofi theme and wallpaper picker menus."""

from __future__ import annotations

from pathlib import Path

from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.discover import list_wallpapers, live_wallpaper_path, resolve_wallpaper, theme_preview_image
from hypraesthetic.paths import current_theme_file
from hypraesthetic.prefs import Prefs


def theme_menu_rows() -> list[tuple[str, str, str]]:
    """Return (display_label, theme_id, preview_path) for each installed theme."""
    catalog = ThemeCatalog()
    current = ""
    path = current_theme_file()
    if path.is_file():
        current = path.read_text(encoding="utf-8").strip()
    rows: list[tuple[str, str, str]] = []
    for name in catalog.names():
        pkg = catalog.get(name)
        label = pkg.display_name
        if name == current:
            label = f"{label} (active)"
        preview = theme_preview_image(pkg) or resolve_wallpaper(pkg=pkg)
        preview_path = str(preview) if preview is not None else ""
        rows.append((label, name, preview_path))
    return rows


def wallpaper_menu_rows() -> list[tuple[str, str]]:
    """Return (label, absolute_path) for each wallpaper image."""
    current_name = ""
    live = live_wallpaper_path()
    if live is not None:
        current_name = live.name
    else:
        stored = Path(str(Prefs.load().get("wallpaper") or "")).name
        if stored:
            current_name = stored
    rows: list[tuple[str, str]] = []
    for image in list_wallpapers():
        name = image.name
        label = name
        if name == current_name:
            label = f"{name} (current)"
        rows.append((label, str(image.resolve())))
    return rows
