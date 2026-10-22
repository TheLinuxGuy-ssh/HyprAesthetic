"""Export the active theme as a user package without copying the whole tree."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Callable

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore

from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.discover import resolve_wallpaper, theme_preview_image
from hypraesthetic.paths import current_theme_file, user_themes_dir
from hypraesthetic.prefs import Prefs, _dump_toml
from hypraesthetic.theme import ThemePackage

PALETTE_EXPORT_TOAST = (
    "Install wallust to generate a palette; until then export copies the current preset colors."
)
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
WhichFn = Callable[[str], str | None]
Runner = Callable[[list[str]], Any]


def export_theme(name: str, *, catalog: ThemeCatalog | None = None, prefs: Prefs | None = None) -> Path:
    cleaned = _theme_name(name)
    current = _current_theme()
    loaded = prefs or Prefs.load()
    packages = catalog or ThemeCatalog()
    pkg = packages.get(current)
    raw = _read_theme(pkg.root / "theme.toml")
    dest = user_themes_dir() / cleaned
    dest.mkdir(parents=True, exist_ok=True)

    raw["name"] = cleaned
    layout = dict(raw.get("layout") or {})
    layout["bar_style"] = str(loaded.get("bar_style") or "")
    layout["widgets"] = _widgets_for_export(loaded, current, pkg)
    raw["layout"] = layout

    wall = resolve_wallpaper(
        pkg=pkg,
        override=str(loaded.get("wallpaper") or ""),
        live=False,
    )
    misc = dict(raw.get("misc") or {})
    if wall is not None and wall.is_file():
        _copy_file(wall, dest / wall.name)
        misc["wallpaper"] = wall.name
    raw["misc"] = misc
    _copy_preview(pkg, raw, dest)

    (dest / "theme.toml").write_text(_dump_toml(raw).strip() + "\n", encoding="utf-8")
    return dest


def generate_from_wallpaper(name: str, *, which: WhichFn, runner: Runner) -> str:
    if which("wallust") is None and which("matugen") is None:
        raise RuntimeError("Install wallust or matugen to generate a palette")
    runner(["hat", "export-theme", name])
    return PALETTE_EXPORT_TOAST


def _theme_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not _NAME_RE.fullmatch(cleaned):
        raise ValueError(f"invalid theme name: {name}")
    return cleaned


def _current_theme() -> str:
    path = current_theme_file()
    if not path.is_file():
        raise ValueError("No theme set")
    current = path.read_text(encoding="utf-8").strip()
    if not current:
        raise ValueError("No theme set")
    return current


def _widgets_for_export(prefs: Prefs, theme: str, pkg: ThemePackage) -> list[str]:
    raw = prefs.get("widgets_by_theme") or {}
    if isinstance(raw, dict) and theme in raw:
        return prefs.widgets_for(theme)
    return [str(item) for item in pkg.widgets]


def _read_theme(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        loaded = tomllib.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"theme.toml is not a table: {path}")
    return loaded


def _copy_preview(pkg: ThemePackage, raw: dict[str, Any], dest: Path) -> None:
    preview_rel = str(raw.get("preview") or pkg.preview or "preview.png")
    preview_path = Path(preview_rel)
    if not preview_path.is_absolute():
        preview_path = pkg.root / preview_rel
    if not preview_path.is_file():
        found = theme_preview_image(pkg)
        if found is None or not found.is_file():
            return
        preview_path = found
    _copy_file(preview_path, dest / preview_path.name)
    raw["preview"] = preview_path.name


def _copy_file(src: Path, dest: Path) -> None:
    if src.resolve() == dest.resolve():
        return
    shutil.copy2(src, dest)
