"""Discover official and user-installed theme packages."""

from __future__ import annotations

from pathlib import Path

from hypraesthetic.paths import official_themes_dir, user_themes_dir
from hypraesthetic.theme import ThemeError, ThemePackage

SKIP_DIRS = {"_template", "_layouts"}


class ThemeCatalog:
    def __init__(self, official_root: Path | None = None, user_root: Path | None = None):
        self.official_root = official_root or official_themes_dir()
        self.user_root = user_root or user_themes_dir()

    def roots(self) -> list[Path]:
        roots = []
        if self.official_root.is_dir():
            roots.append(self.official_root)
        if self.user_root.is_dir():
            roots.append(self.user_root)
        return roots

    def list(self) -> list[ThemePackage]:
        found: dict[str, ThemePackage] = {}
        for root in self.roots():
            for child in sorted(root.iterdir()):
                if not child.is_dir() or child.name in SKIP_DIRS:
                    continue
                if not (child / "theme.toml").is_file():
                    continue
                try:
                    pkg = ThemePackage.load(child)
                except (ThemeError, OSError, ValueError):
                    continue
                found[pkg.name] = pkg
        return [found[name] for name in sorted(found)]

    def list_visible(self) -> list[ThemePackage]:
        """Presets/UI list: hide palette exports when the base preset is still installed."""
        packages = self.list()
        names = {pkg.name for pkg in packages}
        visible: list[ThemePackage] = []
        for pkg in packages:
            if pkg.name.endswith("-export"):
                base = pkg.name[: -len("-export")]
                if base in names:
                    continue
            visible.append(pkg)
        return visible

    def get(self, name: str) -> ThemePackage:
        for pkg in self.list():
            if pkg.name == name:
                return pkg
        raise KeyError(name)

    def names(self) -> list[str]:
        return [pkg.name for pkg in self.list()]
