"""Discover fonts, GTK/icon themes, wallpapers, and bar layouts on the system."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from hypraesthetic.paths import current_theme_file, layouts_dir, repo_root

Runner = Callable[..., object]

WIDGET_CATALOG: list[dict[str, str]] = [
    {"id": "clock", "window": "clock", "title": "Clock", "blurb": "Large time on the desktop"},
    {"id": "system", "window": "system", "title": "System", "blurb": "CPU, memory, and disk meters"},
    {"id": "quote", "window": "toji", "title": "Quote", "blurb": "A line from the active theme"},
    {"id": "wakatime", "window": "wakatime", "title": "WakaTime", "blurb": "Coding time overlay"},
    {"id": "matrix", "window": "matrix", "title": "Matrix", "blurb": "Vertical glyph rain"},
    {"id": "music", "window": "music", "title": "Now playing", "blurb": "Current track and controls"},
    {"id": "weather", "window": "weather", "title": "Weather", "blurb": "Local conditions"},
    {"id": "uptime", "window": "uptime", "title": "Uptime", "blurb": "How long this session has been up"},
]

WIDGET_ID_TO_WINDOW = {item["id"]: item["window"] for item in WIDGET_CATALOG}
WIDGET_WINDOW_TO_ID = {item["window"]: item["id"] for item in WIDGET_CATALOG}

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

APP_CANDIDATES: dict[str, list[str]] = {
    "file_manager": ["nautilus", "thunar", "nemo", "dolphin", "pcmanfm", "nautilus"],
    "terminal": ["kitty", "alacritty", "foot", "ghostty", "wezterm", "gnome-terminal"],
    "launcher": ["rofi", "hyprlauncher", "fuzzel", "wofi"],
    "browser": [
        "firefox",
        "chromium",
        "brave",
        "brave-browser",
        "zen",
        "zen-browser",
        "google-chrome",
        "librewolf",
    ],
}

WIDGET_DEFAULT_GEOMETRY: dict[str, dict[str, str]] = {
    "clock": {"x": "4%", "y": "8%", "width": "450", "height": "155"},
    "system": {"x": "82%", "y": "80%", "width": "180", "height": "125"},
    "quote": {"x": "4%", "y": "86%", "width": "480", "height": "50"},
    "wakatime": {"x": "4%", "y": "26%", "width": "140", "height": "50"},
    "matrix": {"x": "98.5%", "y": "0%", "width": "30", "height": "100%"},
    "music": {"x": "62%", "y": "52%", "width": "360", "height": "88"},
    "weather": {"x": "62%", "y": "36%", "width": "300", "height": "170"},
    "uptime": {"x": "82%", "y": "64%", "width": "240", "height": "110"},
}

_GEOM_RE = re.compile(
    r"\(defwindow\s+(\S+)\b[\s\S]*?:geometry \(geometry :x (\S+) :y (\S+) :width (\S+) :height (\S+)\)"
)


@dataclass
class BarStyle:
    id: str
    name: str
    description: str
    path: Path
    preview: Path | None = None


def widget_window(widget_id: str) -> str:
    return WIDGET_ID_TO_WINDOW.get(widget_id, widget_id)


def widget_ids_from_prefs(raw: list[str] | None) -> list[str]:
    ids: list[str] = []
    for item in raw or []:
        if item in WIDGET_ID_TO_WINDOW:
            ids.append(item)
        elif item in WIDGET_WINDOW_TO_ID:
            ids.append(WIDGET_WINDOW_TO_ID[item])
        else:
            ids.append(item)
    return ids


def list_font_families(runner: Runner | None = None) -> list[str]:
    run = runner or subprocess.run
    result = run(
        ["fc-list", ":", "family"],
        check=False,
        capture_output=True,
        text=True,
    )
    families: set[str] = set()
    stdout = getattr(result, "stdout", "") or ""
    for line in stdout.splitlines():
        family = line.split(",")[0].strip()
        if family:
            families.add(family)
    return sorted(families)


def _theme_roots(kind: str) -> list[Path]:
    home = Path.home()
    if kind == "gtk":
        return [
            home / ".themes",
            home / ".local" / "share" / "themes",
            Path("/usr/share/themes"),
            Path("/usr/local/share/themes"),
        ]
    return [
        home / ".icons",
        home / ".local" / "share" / "icons",
        Path("/usr/share/icons"),
        Path("/usr/local/share/icons"),
    ]


def list_gtk_themes(roots: list[Path] | None = None) -> list[str]:
    names: set[str] = set()
    for root in roots or _theme_roots("gtk"):
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if (child / "gtk-3.0").is_dir() or (child / "gtk-4.0").is_dir():
                names.add(child.name)
    return sorted(names)


def list_icon_themes(roots: list[Path] | None = None) -> list[str]:
    names: set[str] = set()
    for root in roots or _theme_roots("icons"):
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and (child / "index.theme").is_file():
                names.add(child.name)
    return sorted(names)


def list_cursor_themes(roots: list[Path] | None = None) -> list[str]:
    """Cursor themes live beside icon themes. Names like Bibata do not say "cursor"."""
    return list_icon_themes(roots)


def current_theme_name(default: str = "toji") -> str:
    path = current_theme_file()
    if path.is_file():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    return default


_PREVIEW_FALLBACKS = ("preview.gif", "preview.png", "preview.jpg", "preview.jpeg", "preview.webp")
_BAR_PREVIEW_NAMES = ("preview.png", "preview.jpg", "preview.jpeg", "preview.gif", "preview.webp")
_BAR_SCREENSHOT_GLOBS = ("screenshot*.png", "screenshot*.jpg")
FIRST_PARTY_BAR_IDS = frozenset({"none", "default", "compact", "a70", "cyberpunk"})

_BAR_DISPLAY: dict[str, tuple[str, str]] = {
    "v1": ("Top split", "Workspaces left, tray right"),
    "v1.1": ("Toji thin", "Slim top bar"),
    "v1.2": ("Light clash", "Used with Toji vs Sukuna"),
    "v2": ("Red island", "Rounded modules"),
    "v2.9e": ("Capsule dock", "Centered workspaces with meters"),
    "v3": ("Violet modules", "Used with Choso"),
    "v4": ("Ember", "Used with Tanjiro"),
    "v5": ("Night City classic", "Flat modules with window title"),
    "v7": ("Sky slim", "Open-air bar"),
    "default": ("Capsule", "Rounded island bar"),
    "compact": ("Compact", "Workspaces, clock, and tray"),
    "a70": ("Dock", "Centered workspaces with meters"),
    "cyberpunk": ("Night City", "Flat modules with window title"),
    "none": ("Hide the bar", "No status bar"),
}


def bar_display_name(style_id: str, meta_name: str = "") -> tuple[str, str]:
    """(title, blurb). meta_name from bar.toml wins when non-empty."""
    mapped = _BAR_DISPLAY.get(style_id)
    if mapped is None:
        title, blurb = "Waybar layout", style_id
    else:
        title, blurb = mapped
    custom = (meta_name or "").strip()
    if custom:
        title = custom
    return title, blurb


def _preview_search_dirs(root: Path) -> list[Path]:
    return [
        Path.home() / ".wallpapers",
        root / "wallpaper",
        root / "wallpapers",
        root,
    ]


_DESKTOP_NAMES = ("desktop.png", "desktop.jpg", "desktop.webp")


def desktop_preview_image(pkg) -> Path | None:
    if pkg is None:
        return None
    root = Path(getattr(pkg, "root"))
    for directory in (root / "wallpaper", root / "wallpapers", root):
        for name in _DESKTOP_NAMES:
            path = directory / name
            if path.is_file():
                return path
    return None


def theme_preview_image(pkg) -> Path | None:
    if pkg is None:
        return None
    name = str(getattr(pkg, "wallpaper", "") or "")
    preview = str(getattr(pkg, "preview", "") or "")
    root = Path(getattr(pkg, "root"))
    candidates = []
    for item in (name, preview):
        if not item:
            continue
        candidates.extend(directory / item for directory in _preview_search_dirs(root))
    for path in candidates:
        if path.is_file():
            return path
    for directory in (root / "wallpaper", root / "wallpapers", root):
        for filename in _PREVIEW_FALLBACKS:
            path = directory / filename
            if path.is_file():
                return path
    return None


def parse_wallpaper_query(text: str) -> Path | None:
    for line in (text or "").splitlines():
        match = re.search(r"image:\s*(.+?)\s*$", line)
        if match is None:
            continue
        path = Path(match.group(1).strip())
        if path.is_file():
            return path
    return None


def live_wallpaper_path(runner: Runner | None = None) -> Path | None:
    run = runner or subprocess.run
    for cmd in (["swww", "query"], ["awww", "query"]):
        try:
            result = run(cmd, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            continue
        found = parse_wallpaper_query(getattr(result, "stdout", "") or "")
        if found is not None:
            return found
    return None


def wallpaper_candidates(pkg=None, override: str = "") -> list[Path]:
    paths: list[Path] = []
    text = (override or "").strip()
    if text:
        raw = Path(text).expanduser()
        paths.append(raw)
        paths.append(Path.home() / ".wallpapers" / text)
        paths.append(Path.home() / ".wallpapers" / Path(text).name)
    if pkg is None:
        return paths
    name = str(getattr(pkg, "wallpaper", "") or "")
    root = Path(getattr(pkg, "root"))
    if name:
        paths.extend(
            [
                Path.home() / ".wallpapers" / name,
                root / "wallpaper" / name,
                root / name,
                root / "wallpapers" / name,
            ]
        )
    return paths


def resolve_wallpaper(
    *,
    pkg=None,
    override: str = "",
    live: bool = False,
    runner: Runner | None = None,
) -> Path | None:
    if live:
        found = live_wallpaper_path(runner=runner)
        if found is not None:
            return found
    for path in wallpaper_candidates(pkg, override):
        if path.is_file():
            return path
    return theme_preview_image(pkg)


def primary_screen_size(runner: Runner | None = None) -> tuple[int, int]:
    run = runner or subprocess.run
    try:
        result = run(
            ["hyprctl", "monitors", "-j"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return 1920, 1080
    raw = getattr(result, "stdout", "") or ""
    try:
        monitors = json.loads(raw)
        focused = next((item for item in monitors if item.get("focused")), monitors[0])
        width = float(focused.get("width") or 1920)
        height = float(focused.get("height") or 1080)
        scale = float(focused.get("scale") or 1) or 1.0
        logical_w = max(1, int(round(width / scale)))
        logical_h = max(1, int(round(height / scale)))
        transform = focused.get("transform") or 0
        try:
            rotated = int(transform) in {1, 3}
        except (TypeError, ValueError):
            rotated = str(transform) in {"1", "3", "90", "270"}
        if rotated:
            logical_w, logical_h = logical_h, logical_w
        return logical_w, logical_h
    except (ValueError, TypeError, IndexError, AttributeError, json.JSONDecodeError):
        return 1920, 1080


def parse_geom_token(value: str) -> tuple[float, str]:
    text = str(value or "").strip().strip('"').strip()
    if not text:
        return 0.0, "pct"
    unit = "px"
    if text.endswith("px"):
        text = text[:-2].strip()
    elif text.endswith("%"):
        text = text[:-1].strip()
        unit = "pct"
    try:
        return float(text), unit
    except ValueError:
        return 0.0, unit


def geom_to_fraction(value: str, axis: str, screen: tuple[int, int]) -> float:
    amount, unit = parse_geom_token(value)
    if unit == "pct":
        return amount / 100.0
    dim = screen[0] if axis == "x" else screen[1]
    if dim <= 0:
        return 0.0
    return amount / float(dim)


def spec_to_fractions(spec: dict[str, str], screen: tuple[int, int]) -> tuple[float, float, float, float]:
    x = geom_to_fraction(spec.get("x") or "0%", "x", screen)
    y = geom_to_fraction(spec.get("y") or "0%", "y", screen)
    width = geom_to_fraction(spec.get("width") or "12%", "x", screen)
    height = geom_to_fraction(spec.get("height") or "10%", "y", screen)
    return x, y, max(width, 0.02), max(height, 0.02)


def format_percent(frac: float) -> str:
    pct = round(frac * 1000) / 10.0
    if pct == int(pct):
        return f"{int(pct)}%"
    return f"{pct:.1f}%"


def parse_eww_geometry(text: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for match in _GEOM_RE.finditer(text or ""):
        window, x, y, width, height = match.groups()
        widget_id = WIDGET_WINDOW_TO_ID.get(window, window)
        found[widget_id] = {
            "x": x.strip('"'),
            "y": y.strip('"'),
            "width": width.strip('"'),
            "height": height.strip('"'),
        }
    return found


def list_wallpapers(extra: list[Path] | None = None, roots: list[Path] | None = None) -> list[Path]:
    search = list(roots) if roots is not None else [
        Path.home() / ".wallpapers",
        Path.home() / "Pictures" / "Wallpapers",
    ]
    if extra:
        search.extend(extra)
    found: list[Path] = []
    seen: set[Path] = set()
    for root in search:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES and child.resolve() not in seen:
                seen.add(child.resolve())
                found.append(child)
    return found


def list_bar_styles(repo: Path | None = None) -> list[BarStyle]:
    base = layouts_dir(repo or repo_root()) / "bars"
    if not base.is_dir():
        default = layouts_dir(repo or repo_root()) / "default" / "waybar"
        if default.is_dir():
            return [BarStyle("default", "Capsule", "Rounded island bar", default)]
        return []
    labels = {
        "default": ("Capsule", "Rounded island bar"),
        "compact": ("Compact", "Workspaces, clock, and tray"),
        "a70": ("Dock", "Centered workspaces with meters"),
        "cyberpunk": ("Night City", "Flat modules with window title"),
    }
    styles: list[BarStyle] = []
    for child in base.iterdir():
        if not child.is_dir() or not (child / "config.jsonc").is_file():
            continue
        title, blurb, preview = _bar_meta(child)
        if child.name in labels:
            title, blurb = labels[child.name]
        styles.append(BarStyle(child.name, title, blurb, child, preview))
    styles.sort(key=lambda item: _bar_sort_key(item.id))
    return styles


def _bar_preview(path: Path) -> Path | None:
    for name in (*_BAR_PREVIEW_NAMES, "V2.9e.png"):
        candidate = path / name
        if candidate.is_file():
            return candidate
    for pattern in _BAR_SCREENSHOT_GLOBS:
        matches = sorted(candidate for candidate in path.glob(pattern) if candidate.is_file())
        if matches:
            return matches[0]
    return None


def visible_bar_ids(entries: list[tuple[str, str]], needle: str) -> list[str]:
    """First-party ids stay visible. Imported ids appear only when the needle hits."""
    text = (needle or "").strip().lower()
    shown: list[str] = []
    for style_id, haystack in entries:
        if style_id in FIRST_PARTY_BAR_IDS:
            shown.append(style_id)
            continue
        if text and text in (haystack or "").lower():
            shown.append(style_id)
    return shown


def _bar_meta(path: Path) -> tuple[str, str, Path | None]:
    title = path.name.replace("_", " ")
    blurb = "Waybar layout"
    preview = _bar_preview(path)
    meta = path / "bar.toml"
    if meta.is_file():
        raw = tomllib.loads(meta.read_text(encoding="utf-8"))
        title = str(raw.get("name") or title)
        blurb = str(raw.get("description") or blurb)
    return title, blurb, preview


def _bar_sort_key(name: str) -> tuple:
    builtin = {"default": 0, "compact": 1, "a70": 2, "cyberpunk": 3}
    if name in builtin:
        return (0, builtin[name], name)
    parts = tuple(int(part) if part.isdigit() else part for part in re.split(r"([0-9]+)", name.lower()))
    return (1, parts, name)


def font_family_only(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return text
    parts = text.split()
    if parts and parts[-1].replace(".", "", 1).isdigit():
        return " ".join(parts[:-1]).strip() or text
    return text


def pick_installed_font(
    candidates: str | list[str],
    families: list[str] | None = None,
    runner: Runner | None = None,
) -> str:
    raw = candidates if isinstance(candidates, list) else str(candidates).split(",")
    names = [item.strip() for item in raw if str(item).strip()]
    if not names:
        return "Sans"
    installed = families if families is not None else list_font_families(runner)
    lookup = {item.lower(): item for item in installed}
    for name in names:
        match = lookup.get(name.lower())
        if match:
            return match
    return names[-1]


def normalize_font(value: str, default_size: int = 11) -> str:
    text = (value or "").strip()
    if not text:
        return f"Sans {default_size}"
    parts = text.split()
    if parts and parts[-1].replace(".", "", 1).isdigit():
        size = float(parts[-1])
        if size > 0:
            return text
        return " ".join(parts[:-1] + [str(default_size)])
    return f"{text} {default_size}"


def list_on_path(
    candidates: list[str],
    which: Callable[[str], str | None] | None = None,
    current: str | None = None,
) -> list[str]:
    lookup = which or shutil.which
    found: list[str] = []
    if current:
        found.append(current)
    for name in candidates:
        if name in found:
            continue
        if lookup(name):
            found.append(name)
    return found
