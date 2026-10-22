"""User preferences persisted in ~/.config/HyprAesthetic/prefs.toml."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from hypraesthetic.paths import prefs_file, user_config_dir

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore

AUTOMATIC_SELECTION: dict[str, Any] = {
    "mode": "automatic",
    "bar": "waybar",
    "bar_style": "default",
    "bar_position": "top",
    "widgets": ["clock", "system", "matrix", "wakatime", "quote"],
    "widget_geometry": {},
    "wallpaper": "",
    "dashboard": False,
    "launcher": "rofi",
    "file_manager": "nautilus",
    "terminal": "kitty",
    "browser": "firefox",
    "notifications": "dunst",
    "extras": ["hyprwave", "wallpaper", "eww", "gtk", "gui", "neovim"],
    "fonts": {
        "ui": "Adwaita Sans 11",
        "bar": "JetBrainsMono Nerd Font 11",
        "terminal": "JetBrainsMono Nerd Font",
        "icons": "Papirus-Dark",
    },
    "gtk_theme": "Flat-Remix-GTK-Blue-Dark",
    "icon_theme": "Papirus-Dark",
    "cursor_theme": "",
    "hypr": {
        "gaps_in": 5,
        "gaps_out": 7,
        "border_size": 1,
        "rounding": 10,
    },
    "store_url": "",
}


def default_prefs() -> dict[str, Any]:
    return deepcopy(AUTOMATIC_SELECTION)


def _is_widget_spec(value: Any) -> bool:
    return isinstance(value, dict) and any(key in value for key in ("x", "y", "width", "height"))


def _copy_spec(value: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(item).strip().strip('"') for key, item in value.items()}


def _dump_toml(data: dict[str, Any], prefix: str = "") -> str:
    simple: list[str] = []
    tables: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            header = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            tables.append(f"\n[{header}]\n" + _dump_toml(value, header))
        elif isinstance(value, bool):
            simple.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            simple.append(f"{key} = {value}")
        elif isinstance(value, list):
            inner = ", ".join(_toml_scalar(item) for item in value)
            simple.append(f"{key} = [{inner}]")
        else:
            simple.append(f"{key} = {_toml_scalar(value)}")
    body = "\n".join(simple)
    return body + "".join(tables) + ("\n" if not body.endswith("\n") else "")


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class Prefs:
    def __init__(self, data: dict[str, Any] | None = None, path: Path | None = None):
        self.data = default_prefs()
        if data:
            self._merge(self.data, data)
        self.path = path or prefs_file()

    @classmethod
    def load(cls, path: Path | None = None) -> Prefs:
        prefs_path = path or prefs_file()
        if not prefs_path.is_file():
            return cls(path=prefs_path)
        with prefs_path.open("rb") as handle:
            loaded = tomllib.load(handle)
        return cls(data=loaded, path=prefs_path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(_dump_toml(self.data).strip() + "\n", encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, key: str, value: Any) -> None:
        cur = self.data
        parts = key.split(".")
        for part in parts[:-1]:
            nxt = cur.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[part] = nxt
            cur = nxt
        cur[parts[-1]] = value

    def widgets_for(self, theme: str) -> list[str]:
        raw = self.get("widgets_by_theme") or {}
        if not isinstance(raw, dict) or not theme:
            return []
        items = raw.get(theme)
        if not isinstance(items, list):
            return []
        return [str(item) for item in items]

    def set_widgets_for(self, theme: str, widgets: list[str]) -> None:
        raw = self.get("widgets_by_theme")
        stored: dict[str, list[str]] = {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, list):
                    stored[str(key)] = [str(item) for item in value]
        if theme:
            stored[str(theme)] = [str(item) for item in widgets]
        self.set("widgets_by_theme", stored)

    def adopt_legacy_widgets(self, theme: str) -> None:
        if not theme:
            return
        raw = self.get("widgets_by_theme") or {}
        if isinstance(raw, dict) and raw:
            return
        widgets = self.get("widgets") or []
        if not isinstance(widgets, list) or not widgets:
            return
        self.set_widgets_for(theme, [str(item) for item in widgets])

    def geometry_for(self, theme: str) -> dict[str, dict[str, str]]:
        raw = self.get("widget_geometry") or {}
        if not isinstance(raw, dict) or not theme:
            return {}
        nested = raw.get(theme)
        if isinstance(nested, dict) and nested and not _is_widget_spec(nested):
            return {
                str(key): _copy_spec(value)
                for key, value in nested.items()
                if isinstance(value, dict)
            }
        return {}

    def adopt_legacy_geometry(self, theme: str) -> None:
        raw = self.get("widget_geometry") or {}
        if not isinstance(raw, dict) or not theme:
            return
        if not any(_is_widget_spec(value) for value in raw.values()):
            return
        self.set("widget_geometry", self._nested_geometry(theme))

    def set_geometry_for(self, theme: str, geom: dict[str, dict[str, str]]) -> None:
        raw = self._nested_geometry(theme)
        raw[theme] = {
            str(key): dict(value)
            for key, value in geom.items()
            if isinstance(value, dict) and value
        }
        if not raw[theme]:
            raw.pop(theme, None)
        self.set("widget_geometry", raw)

    def clear_geometry_for(self, theme: str) -> None:
        raw = self._nested_geometry(theme)
        raw.pop(theme, None)
        self.set("widget_geometry", raw)

    def _nested_geometry(self, theme: str) -> dict[str, Any]:
        raw = self.get("widget_geometry") or {}
        if not isinstance(raw, dict):
            return {}
        nested: dict[str, Any] = {}
        legacy: dict[str, Any] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            if _is_widget_spec(value):
                legacy[str(key)] = _copy_spec(value)
            else:
                nested[str(key)] = {
                    str(child): _copy_spec(item)
                    for child, item in value.items()
                    if isinstance(item, dict)
                }
        if legacy and theme and theme not in nested:
            nested[theme] = legacy
        return nested

    def selection(self) -> dict[str, Any]:
        return {
            "bar": self.get("bar"),
            "file_manager": self.get("file_manager"),
            "terminal": self.get("terminal"),
            "launcher": self.get("launcher"),
            "notifications": self.get("notifications"),
            "widgets": self.get("widgets") or [],
            "extras": self.get("extras") or [],
        }

    @staticmethod
    def _merge(base: dict[str, Any], incoming: dict[str, Any]) -> None:
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                Prefs._merge(base[key], value)
            else:
                base[key] = value


def ensure_user_config() -> Path:
    path = user_config_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
