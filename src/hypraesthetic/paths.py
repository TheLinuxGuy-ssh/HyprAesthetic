"""Filesystem locations for the HyprAesthetic repo, user config, and layouts."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
REPO_ROOT = SRC_DIR.parent


def repo_root() -> Path:
    env = os.environ.get("HYPRAESTHETIC_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    root_file = user_config_dir() / "root"
    if root_file.is_file():
        value = root_file.read_text(encoding="utf-8").strip()
        if value:
            return Path(value)
    return REPO_ROOT


def user_config_dir() -> Path:
    return Path.home() / ".config" / "HyprAesthetic"


def user_themes_dir() -> Path:
    return Path.home() / ".local" / "share" / "hypraesthetic" / "themes"


def current_theme_file() -> Path:
    return user_config_dir() / "current_theme"


def prefs_file() -> Path:
    return user_config_dir() / "prefs.toml"


def layouts_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "layouts"


def templates_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "themes" / "_template"


def data_dir() -> Path:
    bundled = PACKAGE_DIR / "data"
    if bundled.is_dir():
        return bundled
    return repo_root() / "data"


def official_themes_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "themes"
