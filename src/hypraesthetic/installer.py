"""Bootstrap installer: packages, session file, backup, first theme, prefs."""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from hypraesthetic.packages import PackageCatalog
from hypraesthetic.paths import repo_root as detect_repo_root
from hypraesthetic.prefs import AUTOMATIC_SELECTION, Prefs

Runner = Callable[..., Any]
ApplyFn = Callable[..., Any]
BackupFn = Callable[..., Any]
InstalledFn = Callable[[str], bool]


@dataclass
class InstallResult:
    mode: str
    theme: str
    packages: list[str]
    packages_installed: list[str] = field(default_factory=list)
    packages_skipped: list[str] = field(default_factory=list)


HYPRLAND_DESKTOP = """[Desktop Entry]
Name=Hyprland
Comment=Hyprland Wayland compositor
Exec=Hyprland
Type=Application
DesktopNames=Hyprland
Keywords=tiling;wayland;compositor;
"""

GUI_DESKTOP = """[Desktop Entry]
Name=HyprAesthetic
Comment=Hyprland made easy
Exec=ha-theme gui
Icon=preferences-desktop-theme
Terminal=false
Type=Application
Categories=Settings;DesktopSettings;
"""


class Installer:
    def __init__(
        self,
        repo_root: Path | None = None,
        distro_id: str | None = None,
        runner: Runner | None = None,
        assume_yes: bool = False,
        apply_fn: ApplyFn | None = None,
        backup_fn: BackupFn | None = None,
        package_installed: InstalledFn | None = None,
        write_session: bool = True,
        catalog: PackageCatalog | None = None,
        confirm: Callable[[list[str]], bool] | None = None,
    ):
        self.repo_root = repo_root or detect_repo_root()
        self.distro_id = distro_id or _read_distro_id()
        self.runner = runner or subprocess.run
        self.assume_yes = assume_yes
        self.apply_fn = apply_fn
        self.backup_fn = backup_fn
        self.package_installed = package_installed or _package_installed
        self.write_session = write_session
        self.catalog = catalog or PackageCatalog.load()
        self.confirm = confirm

    def run(
        self,
        mode: str = "automatic",
        theme: str = "toji",
        selection: dict[str, Any] | None = None,
    ) -> InstallResult:
        selected = dict(AUTOMATIC_SELECTION)
        if mode == "custom" and selection:
            selected.update(selection)
        selected["mode"] = mode

        prefs = Prefs.load()
        for key, value in selected.items():
            prefs.set(key, value)
        prefs.save()

        packages = self.catalog.packages_for_selection(self.distro_id, selected)
        missing = [pkg for pkg in packages if not self.package_installed(pkg)]
        installed: list[str] = []
        skipped: list[str] = []
        if missing:
            if self._install_packages(missing):
                installed = list(missing)
            else:
                skipped = list(missing)

        self._install_cli()
        if self.write_session:
            _write_session_files()

        if self.backup_fn:
            self.backup_fn()
        if self.apply_fn:
            self.apply_fn(theme)

        return InstallResult(
            mode=mode,
            theme=theme,
            packages=packages,
            packages_installed=installed,
            packages_skipped=skipped,
        )

    def _install_packages(self, packages: list[str]) -> bool:
        family = self.catalog.family_for(self.distro_id)
        if not self.assume_yes and not self._confirm_packages(packages):
            return False
        cmd = _install_command(family.manager, packages)
        if not cmd:
            return False
        self.runner(cmd, check=False)
        return True

    def _confirm_packages(self, packages: list[str]) -> bool:
        if self.confirm is not None:
            return bool(self.confirm(packages))
        if not sys.stdin.isatty():
            return False
        print("Packages to install:")
        for pkg in packages:
            print(f"  - {pkg}")
        answer = input("Install packages? [Y/n]: ").strip().lower()
        return answer in {"", "y", "yes"}

    def _install_cli(self) -> None:
        bin_dir = Path.home() / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        ha = self.repo_root / "ha-theme"
        if ha.is_file():
            dest = bin_dir / "ha-theme"
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            dest.symlink_to(ha)
            hat = bin_dir / "hat"
            hat.write_text("#!/usr/bin/env bash\nexec ha-theme \"$@\"\n", encoding="utf-8")
            hat.chmod(0o755)
        root_file = Path.home() / ".config" / "HyprAesthetic" / "root"
        root_file.parent.mkdir(parents=True, exist_ok=True)
        root_file.write_text(str(self.repo_root) + "\n", encoding="utf-8")
        wall = self.repo_root / "scripts" / "rofi-wallpaper-menu.sh"
        if wall.is_file():
            hyprwall = bin_dir / "hyprwall"
            if hyprwall.exists() or hyprwall.is_symlink():
                hyprwall.unlink()
            hyprwall.symlink_to(wall)


def _write_session_files() -> None:
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    desktop = apps / "hyprland.desktop"
    if not desktop.is_file():
        desktop.write_text(HYPRLAND_DESKTOP, encoding="utf-8")
    (apps / "hypraesthetic.desktop").write_text(GUI_DESKTOP, encoding="utf-8")
    sessions = Path.home() / ".local" / "share" / "wayland-sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    session = sessions / "hyprland.desktop"
    if not session.is_file():
        session.write_text(HYPRLAND_DESKTOP, encoding="utf-8")


def _read_distro_id() -> str:
    path = Path("/etc/os-release")
    if not path.is_file():
        return "unknown"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ID="):
            return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def _install_command(manager: str, packages: list[str]) -> list[str] | None:
    if manager == "pacman":
        return ["sudo", "pacman", "-S", "--needed", "--noconfirm", *packages]
    if manager == "dnf":
        return ["sudo", "dnf", "install", "-y", *packages]
    if manager == "apt":
        return ["sudo", "apt", "install", "-y", *packages]
    if manager == "zypper":
        return ["sudo", "zypper", "install", "-y", *packages]
    if manager == "nix":
        return ["nix", "profile", "install", *packages]
    return None


def _package_installed(pkg: str) -> bool:
    probes = [
        ["rpm", "-q", pkg],
        ["pacman", "-Q", pkg],
        ["dpkg", "-s", pkg],
    ]
    for cmd in probes:
        if shutil.which(cmd[0]) and subprocess.run(cmd, capture_output=True).returncode == 0:
            return True
    return False
