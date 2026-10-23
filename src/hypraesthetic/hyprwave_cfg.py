"""Resolve HyprWave placement and options for apply + GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

HYPRWAVE_EDGES = ("top", "left", "bottom", "right")
HYPRWAVE_LAYERS = ("background", "bottom", "top", "overlay")

HYPRWAVE_DEFAULTS: dict[str, Any] = {
    "edge": "bottom",
    "margin": 10,
    "preference": "spotify,vlc,brave",
    "builtin": "",
    "layer": "top",
    "exclusive_zone": 0,
}


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    text = str(hex_color).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return (128, 128, 128)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def rgba_hex(hex_color: str, alpha: float) -> str:
    red, green, blue = _hex_rgb(hex_color)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def hyprwave_accent_pair(palette: dict[str, str]) -> tuple[str, str]:
    """Primary + secondary accent for gradients (never base0C — Base16 cyan slot)."""
    primary = (palette.get("base0D") or palette.get("base0E") or "#888888").lower()
    for key in ("base0E", "base0A", "base08", "base09", "base0F", "base0B"):
        candidate = palette.get(key)
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered != primary:
            return palette.get("base0D") or candidate, candidate
    same = palette.get("base0D") or "#888888"
    return same, same


def hyprwave_color_variables(palette: dict[str, str]) -> dict[str, str]:
    """Map theme palette keys to HyprWave CSS tokens."""
    pick = lambda key, fallback: palette.get(key) or palette.get(fallback) or "#888888"

    base00 = pick("base00", "base01")
    base01 = pick("base01", "base00")
    base02 = pick("base02", "base01")
    base03 = pick("base03", "base02")
    base04 = pick("base04", "base05")
    base05 = pick("base05", "base04")
    primary, accent = hyprwave_accent_pair(palette)
    secondary = pick("base0E", "base0A")
    if secondary.lower() == primary.lower():
        secondary = accent

    def c(color: str, alpha: float) -> str:
        return rgba_hex(color, alpha)

    return {
        "hw_bg_primary": c(base00, 0.78),
        "hw_bg_secondary": c(base01, 0.78),
        "hw_bg_album": c(base01, 0.88),
        "hw_bg_album_secondary": c(base02, 0.88),
        "hw_btn_default": c(base03, 0.85),
        "hw_btn_default_secondary": c(base02, 0.85),
        "hw_btn_default_hover": c(base04, 0.92),
        "hw_btn_default_hover_secondary": c(base03, 0.92),
        "hw_btn_play": c(primary, 0.95),
        "hw_btn_play_secondary": c(primary, 0.9),
        "hw_btn_play_hover": c(primary, 0.98),
        "hw_btn_play_hover_secondary": c(accent, 0.95),
        "hw_btn_play_active": c(primary, 0.9),
        "hw_btn_play_active_secondary": c(primary, 0.85),
        "hw_btn_expand": c(accent, 0.95),
        "hw_btn_expand_secondary": c(secondary, 0.95),
        "hw_btn_expand_hover": c(accent, 0.98),
        "hw_btn_expand_hover_secondary": c(secondary, 0.98),
        "hw_btn_expand_active": c(accent, 0.9),
        "hw_btn_expand_active_secondary": c(secondary, 0.9),
        "hw_progress_bg": c(base02, 0.35),
        "hw_progress_fill_start": c(primary, 0.95),
        "hw_progress_fill_end": c(accent, 0.95),
        "hw_handle_color": c(primary, 0.98),
        "hw_handle_hover": c(accent, 1.0),
        "hw_handle_border": c(primary, 0.5),
        "hw_handle_shadow": c(primary, 0.55),
        "hw_text_primary": c(base05, 0.95),
        "hw_text_secondary": c(base04, 0.85),
        "hw_text_tertiary": c(base04, 0.75),
        "hw_text_muted": c(base03, 0.65),
        "hw_border_primary": c(base03, 0.35),
        "hw_border_button": c(base03, 0.3),
        "hw_border_button_hover": c(base04, 0.45),
        "hw_border_play": c(primary, 0.4),
        "hw_border_play_hover": c(primary, 0.55),
        "hw_border_expand": c(accent, 0.4),
        "hw_border_expand_hover": c(accent, 0.55),
        "hw_shadow_default": c(base00, 0.5),
        "hw_shadow_button": c(base00, 0.4),
        "hw_shadow_play": c(primary, 0.5),
        "hw_shadow_play_hover": c(primary, 0.7),
        "hw_shadow_expand": c(accent, 0.5),
        "hw_shadow_expand_hover": c(accent, 0.7),
        "hw_shadow_focus": c(primary, 0.65),
        "hw_viz_top": c(primary, 0.98),
        "hw_viz_bottom": c(accent, 0.98),
        "hw_viz_glow": c(primary, 0.65),
        "hw_viz_glow_soft": c(accent, 0.45),
    }


def hyprwave_themes_dir() -> Path:
    return Path.home() / ".local" / "share" / "hyprwave" / "themes"


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
    builtin = raw.get("builtin")
    if builtin is not None:
        out["builtin"] = str(builtin).strip().removesuffix(".css")
    layer = str(raw.get("layer") or out["layer"]).lower()
    if layer in HYPRWAVE_LAYERS:
        out["layer"] = layer
    try:
        out["exclusive_zone"] = int(raw.get("exclusive_zone", out["exclusive_zone"]))
    except (TypeError, ValueError):
        pass
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

    builtin = str(hw_prefs.get("builtin") or theme.get("builtin") or "").strip().removesuffix(".css")

    layer = str(hw_prefs.get("layer") or theme["layer"]).lower()
    if layer not in HYPRWAVE_LAYERS:
        layer = str(theme["layer"])

    zone = hw_prefs.get("exclusive_zone")
    if zone is None:
        zone = theme["exclusive_zone"]
    try:
        zone_i = int(zone)
    except (TypeError, ValueError):
        zone_i = int(theme["exclusive_zone"])
    if zone_i not in (0, -1):
        zone_i = 0

    return {
        "hyprwave_edge": edge,
        "hyprwave_margin": str(margin_i),
        "hyprwave_preference": preference,
        "hyprwave_builtin": builtin,
        "hyprwave_layer": layer,
        "hyprwave_exclusive_zone": str(zone_i),
    }


def sync_hyprwave_prefs(prefs: Any, theme_raw: dict[str, Any] | None) -> None:
    """Copy theme [hyprwave] defaults into prefs on full preset apply."""
    theme = _theme_hyprwave(theme_raw)
    prefs.set("hyprwave.edge", theme["edge"])
    prefs.set("hyprwave.margin", int(theme["margin"]))
    prefs.set("hyprwave.preference", str(theme["preference"]))
    prefs.set("hyprwave.layer", str(theme["layer"]))
    prefs.set("hyprwave.exclusive_zone", int(theme["exclusive_zone"]))
