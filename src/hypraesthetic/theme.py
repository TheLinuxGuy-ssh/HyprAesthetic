"""Load, validate, and resolve HyprAesthetic theme packages."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PALETTE_KEYS = [f"base{i:02X}" for i in range(16)]

COMPONENT_IDS = (
    "hyprland",
    "waybar",
    "hyprwave",
    "eww",
    "rofi",
    "kitty",
    "gtk",
    "dunst",
    "nvim",
)

SURFACE_KEYS = (
    "background",
    "foreground",
    "surface",
    "surface_hover",
    "border",
    "foreground_muted",
    "primary",
    "primary_fg",
    "error",
    "error_fg",
    "warning",
    "warning_fg",
    "success",
    "success_fg",
)

SURFACE_FROM_PALETTE = {
    "background": "base00",
    "foreground": "base05",
    "surface": "base01",
    "surface_hover": "base02",
    "border": "base03",
    "foreground_muted": "base04",
    "primary": "base0D",
    "primary_fg": "base00",
    "error": "base08",
    "error_fg": "base00",
    "warning": "base0A",
    "warning_fg": "base00",
    "success": "base0B",
    "success_fg": "base00",
}

HYPRLAND_FROM_PALETTE = {
    "border_active": "base0D",
    "border_inactive": "base03",
}

REF_RE = re.compile(
    r"\{\{(?:palette|colors)\.([A-Za-z0-9_]+)\}\}([0-9a-fA-F]{0,2})"
)

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

HYPR_DEFAULTS = {
    "gaps_in": 5,
    "gaps_out": 7,
    "border_size": 1,
    "rounding": 10,
}

IDENTITY_DEFAULTS = {
    "font_ui": "Adwaita Sans, Inter, Sans",
    "font_clock": "JetBrainsMono Nerd Font, Iosevka, monospace",
    "font_mono": "JetBrainsMono Nerd Font, Iosevka, monospace",
    "font_quote": "Iosevka, Adwaita Sans, Sans",
    "clock_size": "80",
    "music_radius": "8",
    "cover_size": "64",
    "matrix_chars": "010101$#%&",
    "matrix_rows": "48",
    "matrix_cols": "1",
    "matrix_density": "3",
}


def _int_map(raw: Any, defaults: dict[str, int]) -> dict[str, int]:
    out = dict(defaults)
    if not isinstance(raw, dict):
        return out
    for key, default in defaults.items():
        if key not in raw:
            continue
        try:
            out[key] = int(raw[key])
        except (TypeError, ValueError):
            out[key] = default
    return out


def _identity_map(raw: Any) -> dict[str, str]:
    out = dict(IDENTITY_DEFAULTS)
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if value is None:
            continue
        out[str(key)] = str(value)
    return out


class ThemeError(ValueError):
    """Theme package is missing required fields or has invalid colors."""


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _quote_list(raw: dict[str, Any], misc: dict[str, Any]) -> list[str]:
    for blob in (raw.get("quotes"), misc.get("quotes"), (raw.get("components") or {}).get("quotes")):
        if isinstance(blob, list):
            return [str(item) for item in blob if str(item).strip()]
    return []


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    if value is None:
        return default
    return bool(value)


def _resolve_string(value: str, palette: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        suffix = match.group(2) or ""
        hexv = palette.get(key)
        if hexv is None:
            return match.group(0)
        return f"{hexv}{suffix}"

    return REF_RE.sub(repl, value)


def _resolve_mapping(data: Any, palette: dict[str, str]) -> Any:
    if isinstance(data, dict):
        return {key: _resolve_mapping(val, palette) for key, val in data.items()}
    if isinstance(data, list):
        return [_resolve_mapping(item, palette) for item in data]
    if isinstance(data, str):
        return _resolve_string(data, palette)
    return data


def _fill_surface(table: dict[str, str], palette: dict[str, str]) -> dict[str, str]:
    filled = dict(table)
    for key in SURFACE_KEYS:
        if key not in filled or not filled[key]:
            filled[key] = palette[SURFACE_FROM_PALETTE[key]]
    return filled


def _extract_palette(raw: dict[str, Any]) -> dict[str, str]:
    palette_src = raw.get("palette")
    if not isinstance(palette_src, dict):
        colors = raw.get("colors")
        palette_src = colors if isinstance(colors, dict) else {}
    palette: dict[str, str] = {}
    for key in PALETTE_KEYS:
        value = palette_src.get(key)
        if isinstance(value, str) and value:
            palette[key] = value
    return palette


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        flat_key = f"{prefix}{key}".replace("-", "_")
        if isinstance(value, dict):
            out.update(_flatten(value, f"{flat_key}_"))
        elif isinstance(value, bool):
            out[flat_key] = str(value).lower()
        elif isinstance(value, (int, float)):
            out[flat_key] = str(value)
        elif isinstance(value, list):
            continue
        elif value is None:
            continue
        else:
            out[flat_key] = str(value)
    return out


@dataclass
class ThemePackage:
    root: Path
    data: dict[str, Any]
    palette: dict[str, str]
    colors: dict[str, dict[str, str]]
    components: dict[str, bool]
    layout: dict[str, Any]
    defaults: dict[str, str]
    widgets: list[str]
    name: str
    display_name: str
    author: str
    version: str
    description: str = ""
    license: str = "MIT"
    min_hypraesthetic: str = "0.2.0"
    schema: int = 2
    wallpaper: str = ""
    hw_theme: str = ""
    source: str = ""
    preview: str = ""
    quotes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    hypr: dict[str, int] = field(default_factory=lambda: dict(HYPR_DEFAULTS))
    identity: dict[str, str] = field(default_factory=lambda: dict(IDENTITY_DEFAULTS))

    @classmethod
    def load(cls, path: Path) -> ThemePackage:
        theme_dir = Path(path)
        toml_path = theme_dir / "theme.toml"
        if not toml_path.is_file():
            raise ThemeError(f"Theme missing theme.toml: {theme_dir}")
        raw = _read_toml(toml_path)
        palette = _extract_palette(raw)
        missing_palette = [key for key in PALETTE_KEYS if key not in palette]
        errors: list[str] = []
        if missing_palette:
            errors.append("missing palette keys: " + ", ".join(missing_palette))

        resolved_colors = _resolve_mapping(raw.get("colors") or {}, palette)
        if not isinstance(resolved_colors, dict):
            resolved_colors = {}

        waybar = _fill_surface(dict(resolved_colors.get("waybar") or {}), palette) if palette else {}
        eww = _fill_surface(dict(resolved_colors.get("eww") or {}), palette) if palette else {}
        hyprland = dict(resolved_colors.get("hyprland") or {})
        if palette:
            for key, pal_key in HYPRLAND_FROM_PALETTE.items():
                if not hyprland.get(key):
                    hyprland[key] = palette[pal_key]
            if not hyprland.get("shadow"):
                hyprland["shadow"] = f"{palette['base00']}aa"

        colors = {
            "hyprland": hyprland,
            "waybar": waybar,
            "eww": eww,
        }
        for key, value in resolved_colors.items():
            if key in {"hyprland", "waybar", "eww"}:
                continue
            if isinstance(value, dict):
                colors[key] = {str(k): str(v) for k, v in value.items()}
            elif isinstance(value, str) and key in PALETTE_KEYS:
                continue

        raw_components = raw.get("components") or {}
        components = {cid: _as_bool(raw_components.get(cid, True)) for cid in COMPONENT_IDS}

        layout = dict(raw.get("layout") or {})
        eww_table = raw.get("eww") or {}
        widgets = list(layout.get("widgets") or eww_table.get("default_widgets") or [])
        layout.setdefault("bar", "waybar")
        layout.setdefault("launcher", "rofi")
        layout["widgets"] = widgets

        defaults = {
            "file_manager": "nautilus",
            "terminal": "kitty",
            "browser": "firefox",
        }
        defaults.update({k: str(v) for k, v in (raw.get("defaults") or {}).items()})
        hypr = _int_map(raw.get("hypr"), HYPR_DEFAULTS)
        identity = _identity_map(raw.get("identity"))

        misc = raw.get("misc") or {}
        name = str(raw.get("name") or theme_dir.name)
        display_name = str(raw.get("display_name") or name)
        author = str(raw.get("author") or "")
        version = str(raw.get("version") or "")
        if not raw.get("name"):
            errors.append("missing name")
        if not raw.get("display_name"):
            errors.append("missing display_name")
        if not author:
            errors.append("missing author")
        if not version:
            errors.append("missing version")

        pkg = cls(
            root=theme_dir,
            data=raw,
            palette=palette,
            colors=colors,
            components=components,
            layout=layout,
            defaults=defaults,
            widgets=[str(w) for w in widgets],
            name=name,
            display_name=display_name,
            author=author,
            version=version,
            description=str(raw.get("description") or ""),
            license=str(raw.get("license") or "MIT"),
            min_hypraesthetic=str(raw.get("min_hypraesthetic") or "0.2.0"),
            schema=int(raw.get("schema") or (2 if "palette" in raw else 1)),
            wallpaper=str(misc.get("wallpaper") or ""),
            hw_theme=str(misc.get("hw_theme") or ""),
            source=str(raw.get("source") or ""),
            preview=str(raw.get("preview") or "preview.png"),
            quotes=_quote_list(raw, misc),
            errors=errors,
            hypr=hypr,
            identity=identity,
        )
        if errors:
            raise ThemeError("; ".join(errors))
        return pkg

    def enabled(self, component: str) -> bool:
        return self.components.get(component, True)

    def flatten(self) -> dict[str, str]:
        data: dict[str, Any] = {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "schema": self.schema,
            "license": self.license,
            "min_hypraesthetic": self.min_hypraesthetic,
            "preview": self.preview,
            "source": self.source,
            "palette": self.palette,
            "colors": {
                **self.palette,
                **self.colors,
            },
            "misc": {"wallpaper": self.wallpaper, "hw_theme": self.hw_theme},
            "layout": {k: v for k, v in self.layout.items() if not isinstance(v, list)},
            "hypr": self.hypr,
            "identity": self.identity,
            "defaults": self.defaults,
            "components": self.components,
        }
        return _flatten(data)

    def flatten_shell(self) -> str:
        lines = [f'{key}="{value}"' for key, value in sorted(self.flatten().items())]
        return "\n".join(lines) + "\n"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.name != self.root.name:
            problems.append(f"name {self.name!r} does not match folder {self.root.name!r}")
        for group in ("waybar", "eww"):
            for key, value in self.colors.get(group, {}).items():
                if not HEX_RE.match(value):
                    problems.append(f"{group}.{key} is not hex: {value}")
        return problems

    def overlay_dir(self, component: str, *, layout_owned: bool = False) -> Path | None:
        overrides = self.root / "overrides" / component
        if overrides.exists():
            return overrides
        if layout_owned:
            return None
        legacy = self.root / component
        if legacy.exists():
            return legacy
        return None
