"""Install a theme package from a directory or git URL."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from hypraesthetic.paths import user_themes_dir
from hypraesthetic.theme import ThemeError, ThemePackage

Runner = Callable[..., Any]


class ThemeInstaller:
    def __init__(self, dest_root: Path | None = None, runner: Runner | None = None):
        self.dest_root = dest_root or user_themes_dir()
        self.runner = runner or subprocess.run

    def install(self, source: str) -> ThemePackage:
        if _looks_like_git(source):
            return self._from_git(source)
        return self._from_path(Path(source).expanduser().resolve())

    def _from_path(self, src: Path) -> ThemePackage:
        if src.is_file() and src.name == "theme.toml":
            src = src.parent
        if not (src / "theme.toml").is_file():
            raise ValueError(f"Not a theme package (missing theme.toml): {src}")
        pkg = ThemePackage.load(src)
        dest = self.dest_root / pkg.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return ThemePackage.load(dest)

    def _from_git(self, url: str) -> ThemePackage:
        self.dest_root.mkdir(parents=True, exist_ok=True)
        clone_name = _git_name(url)
        dest = self.dest_root / clone_name
        if dest.exists():
            shutil.rmtree(dest)
        result = self.runner(["git", "clone", "--depth", "1", url, str(dest)], check=False)
        if getattr(result, "returncode", 0) not in (0, None):
            raise RuntimeError(f"git clone failed: {url}")
        toml = dest / "theme.toml"
        if not toml.is_file():
            nested = next(dest.glob("*/theme.toml"), None)
            if nested is None:
                raise ThemeError(f"Cloned repo has no theme.toml: {url}")
            pkg = ThemePackage.load(nested.parent)
            final = self.dest_root / pkg.name
            if final.exists() and final != nested.parent:
                shutil.rmtree(final)
            if nested.parent != final:
                shutil.move(str(nested.parent), str(final))
            return ThemePackage.load(final)
        pkg = ThemePackage.load(dest)
        if dest.name != pkg.name:
            final = self.dest_root / pkg.name
            if final.exists():
                shutil.rmtree(final)
            dest.rename(final)
            return ThemePackage.load(final)
        return pkg


def _looks_like_git(source: str) -> bool:
    return source.endswith(".git") or source.startswith("https://") or source.startswith("git@")


def _git_name(url: str) -> str:
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or "theme"
