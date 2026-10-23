"""Bootstrap installer: packages, session file, backup, first theme, prefs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from hypraesthetic.aur import (
    choose_helper,
    ensure_helper as bootstrap_helper,
    find_helper,
    helper_runs,
    split_repo_and_aur,
)
from hypraesthetic.packages import PackageCatalog, os_release_ids
from hypraesthetic.privilege import allow_root_install, privileged_command
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
        euid: int | None = None,
        aur_assume: bool = False,
        root_assume: bool = False,
        root_confirm: Callable[[], bool] | None = None,
        which: Callable[[str], str | None] | None = None,
        ensure_helper: Callable[..., Any] | None = None,
        aur_ask: Callable[[], str] | None = None,
    ):
        self.repo_root = repo_root or detect_repo_root()
        if distro_id:
            self.distro_ids = [distro_id]
        else:
            self.distro_ids = os_release_ids(_os_release_text()) or ["unknown"]
        self.distro_id = self.distro_ids[0]
        self.runner = runner or subprocess.run
        self.assume_yes = assume_yes
        self.apply_fn = apply_fn
        self.backup_fn = backup_fn
        self.package_installed = package_installed or _package_installed
        self.write_session = write_session
        self.catalog = catalog or PackageCatalog.load()
        self.confirm = confirm
        self.euid = os.geteuid() if euid is None else euid
        self.aur_assume = aur_assume
        self.root_assume = root_assume
        self.root_confirm = root_confirm
        self.which = which or shutil.which
        self.ensure_helper = ensure_helper or bootstrap_helper
        self.aur_ask = aur_ask
        self.packages_installed: list[str] = []
        self.packages_skipped: list[str] = []
        self._root_allowed: bool | None = None

    def allow_root(self) -> bool:
        if self._root_allowed is not None:
            return self._root_allowed
        self._root_allowed = allow_root_install(
            euid=self.euid,
            assume_yes=self.root_assume,
            confirm=self.root_confirm,
            stdin_isatty=sys.stdin.isatty(),
        )
        return self._root_allowed

    def run(
        self,
        mode: str = "automatic",
        theme: str = "toji",
        selection: dict[str, Any] | None = None,
    ) -> InstallResult:
        if not self.allow_root():
            raise PermissionError("root install declined")
        selected = dict(AUTOMATIC_SELECTION)
        if mode == "custom" and selection:
            selected.update(selection)
        selected["mode"] = mode

        prefs = Prefs.load()
        for key, value in selected.items():
            prefs.set(key, value)
        prefs.save()

        family = self.catalog.family_for_ids(self.distro_ids)
        packages = self.catalog.packages_for_selection(family.name, selected)
        missing = [pkg for pkg in packages if not self.package_installed(pkg)]
        installed: list[str] = []
        skipped: list[str] = []
        if missing:
            self._install_packages(missing)
            installed = list(self.packages_installed)
            skipped = list(self.packages_skipped)

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
        family = self.catalog.family_for_ids(self.distro_ids)
        if not self.assume_yes and not self._confirm_packages(packages):
            self.packages_installed = []
            self.packages_skipped = list(packages)
            return False
        repo, aur = split_repo_and_aur(packages, extra_aur=self.catalog.aur_names(family.name))
        if repo:
            cmd = _install_command(family.manager, repo)
            if cmd:
                self.runner(privileged_command(cmd, euid=self.euid), check=False)
        if aur:
            helper = find_helper(which=self.which)
            if helper and not helper_runs(helper, self.runner):
                helper = None
            if not helper:
                helper = self.ensure_helper(
                    choose_helper(assume_yes=self.aur_assume, which=self.which, ask=self.aur_ask),
                    runner=self.runner,
                    euid=self.euid,
                    which=self.which,
                    privileged=privileged_command,
                )
            if helper:
                # One package per invocation so a missing AUR name does not
                # abort the rest of the transaction.
                for pkg in aur:
                    self.runner([helper, "-S", "--needed", "--noconfirm", pkg], check=False)
        installed: list[str] = []
        skipped: list[str] = []
        for name in packages:
            if self.package_installed(name):
                installed.append(name)
            else:
                skipped.append(name)
        self.packages_installed = installed
        self.packages_skipped = skipped
        return not skipped

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


def _os_release_text() -> str:
    path = Path("/etc/os-release")
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _read_distro_id() -> str:
    ids = os_release_ids(_os_release_text())
    return ids[0] if ids else "unknown"


def _install_command(manager: str, packages: list[str]) -> list[str] | None:
    if manager == "pacman":
        return ["pacman", "-S", "--needed", "--noconfirm", *packages]
    if manager == "dnf":
        return ["dnf", "install", "-y", *packages]
    if manager == "apt":
        return ["apt", "install", "-y", *packages]
    if manager == "zypper":
        return ["zypper", "install", "-y", *packages]
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
