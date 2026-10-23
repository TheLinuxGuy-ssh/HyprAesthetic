"""Resolve HyprWave placement and options for apply + GUI."""

from __future__ import annotations

from typing import Any

HYPRWAVE_EDGES = ("top", "left", "bottom", "right")

HYPRWAVE_DEFAULTS: dict[str, Any] = {
    "edge": "bottom",
    "margin": 10,
    "preference": "spotify,vlc,brave",
}


def _theme_hyprwave(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(HYPRWAVE_DEFAULTS)
    if not isinstance(raw, dict):
        return out
    edge = str(raw.get("edge") or out["edge"]).lower()
    if edge in HYPRWAVE_EDGES:
        out["edge"] = edge
    try:
        out["margin"] = int(raw.get("margin", out["margin"]))
    except (TypeError, ValueError):
        pass
    pref = raw.get("preference")
    if pref is not None:
        out["preference"] = str(pref).strip()
    return out


def hyprwave_from_theme(raw: dict[str, Any] | None) -> dict[str, Any]:
    return _theme_hyprwave(raw)


def resolve_hyprwave(pkg_hyprwave: dict[str, Any], prefs_data: dict[str, Any]) -> dict[str, str]:
    theme = _theme_hyprwave(pkg_hyprwave)
    hw_prefs = prefs_data.get("hyprwave")
    if not isinstance(hw_prefs, dict):
        hw_prefs = {}

    edge = str(hw_prefs.get("edge") or theme["edge"]).lower()
    if edge not in HYPRWAVE_EDGES:
        edge = str(theme["edge"])

    margin = hw_prefs.get("margin")
    if margin is None:
        margin = theme["margin"]
    try:
        margin_i = int(margin)
    except (TypeError, ValueError):
        margin_i = int(theme["margin"])

    preference = str(hw_prefs.get("preference") or theme["preference"]).strip()
    if not preference:
        preference = str(theme["preference"])

    return {
        "hyprwave_edge": edge,
        "hyprwave_margin": str(margin_i),
        "hyprwave_preference": preference,
    }


def sync_hyprwave_prefs(prefs: Any, theme_raw: dict[str, Any] | None) -> None:
    """Copy theme [hyprwave] defaults into prefs on full preset apply."""
    theme = _theme_hyprwave(theme_raw)
    prefs.set("hyprwave.edge", theme["edge"])
    prefs.set("hyprwave.margin", int(theme["margin"]))
    prefs.set("hyprwave.preference", str(theme["preference"]))
