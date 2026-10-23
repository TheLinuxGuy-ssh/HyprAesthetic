"""Prefs adjustments before a full preset switch."""

from __future__ import annotations

from hypraesthetic.prefs import Prefs


def prepare_preset_switch(prefs: Prefs) -> Prefs:
    """Drop a user wallpaper override so the target preset's wallpaper applies."""
    prefs.set("wallpaper", "")
    return prefs
