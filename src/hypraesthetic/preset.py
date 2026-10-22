"""Prefs adjustments before a full preset switch."""

from __future__ import annotations

from hypraesthetic.prefs import Prefs


def prepare_preset_switch(prefs: Prefs) -> Prefs:
    """Prefs mutations before a full preset apply. Must not clear wallpaper."""
    return prefs
