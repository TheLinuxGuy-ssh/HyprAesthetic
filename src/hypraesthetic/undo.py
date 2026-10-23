"""Snapshot and restore the prefs state from before the last full apply."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from hypraesthetic.apply import ApplyEngine, ApplyResult
from hypraesthetic.paths import current_theme_file, user_config_dir
from hypraesthetic.prefs import Prefs, _copy_spec, _dump_toml, _is_widget_spec

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore

_SNAPSHOT_FIELDS = ("wallpaper", "bar_style", "bar", "widgets")


def snapshot_path() -> Path:
    """Resolved at call time so tests can point HOME at a temp directory."""
    return user_config_dir() / "last-apply.toml"


def snapshot(prefs: Prefs, theme: str) -> None:
    data: dict[str, Any] = {
        "theme": theme,
        "wallpaper": prefs.get("wallpaper") or "",
        "bar_style": prefs.get("bar_style") or "",
        "bar": prefs.get("bar") or "",
        "widgets": list(prefs.get("widgets") or []),
        "widget_geometry": _geometry_for_theme(prefs, theme),
    }
    if "widgets_by_theme" in prefs.data:
        data["widgets_by_theme"] = deepcopy(prefs.get("widgets_by_theme"))
    path = snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_toml(data).strip() + "\n", encoding="utf-8")


def load_snapshot() -> dict[str, Any] | None:
    path = snapshot_path()
    if not path.is_file() or tomllib is None:
        return None
    with path.open("rb") as handle:
        loaded = tomllib.load(handle)
    return loaded if isinstance(loaded, dict) else None


def undo(engine: ApplyEngine) -> ApplyResult:
    """Reapply snapshot theme+prefs. Raise FileNotFoundError if none.

    The outgoing snapshot is kept in memory and written only after apply
    returns, so a raised restore leaves last-apply.toml in place.
    """
    saved = load_snapshot()
    theme = str((saved or {}).get("theme") or "").strip()
    if saved is None or not theme:
        raise FileNotFoundError(snapshot_path())
    # Capture the theme being left, with its own live prefs, so a second undo
    # toggles back. Held until apply returns: writing it first would replace
    # last-apply.toml even when the restore raises. apply(snapshot=False)
    # must not write this file itself, or it would store the restored prefs
    # under the theme that is still current at the start of apply.
    outgoing_prefs = Prefs.load()
    current_path = current_theme_file()
    outgoing_theme = (
        current_path.read_text(encoding="utf-8").strip() if current_path.is_file() else ""
    )
    prefs = Prefs.load()
    for key in _SNAPSHOT_FIELDS:
        if key in saved:
            prefs.set(key, saved[key])
    geom = saved.get("widget_geometry")
    if isinstance(geom, dict):
        prefs.set_geometry_for(theme, geom)
    if "widgets_by_theme" in saved:
        prefs.set("widgets_by_theme", deepcopy(saved["widgets_by_theme"]))
    # apply() rewrites `widgets` from widgets_for(theme) or the package list.
    # Pin this theme to the snapshotted list first so that rewrite keeps it:
    # a per-theme set copied into `widgets` before the snapshot, or a flat
    # edit made after the last apply.
    if theme and "widgets" in saved:
        prefs.set_widgets_for(theme, list(saved["widgets"]))
    prefs.save()
    result = engine.apply(theme, snapshot=False)
    # A full apply copies the theme's bar_style over the restored pref.
    # Put that pref back and deploy only the bar when the theme replaced it.
    restored_style = saved.get("bar_style")
    if restored_style is not None:
        current = Prefs.load()
        if current.get("bar_style") != restored_style:
            current.set("bar_style", restored_style)
            current.save()
            if current.get("bar") != "none":
                follow = engine.apply(theme, components=["waybar"])
                result.errors.extend(follow.errors)
    snapshot(outgoing_prefs, outgoing_theme)
    return result


def _geometry_for_theme(prefs: Prefs, theme: str) -> dict[str, Any]:
    raw = prefs.get("widget_geometry") or {}
    if not isinstance(raw, dict):
        return {}
    if theme:
        nested = prefs.geometry_for(theme)
        if nested:
            return nested
    return {
        str(key): _copy_spec(value)
        for key, value in raw.items()
        if isinstance(value, dict) and _is_widget_spec(value)
    }
