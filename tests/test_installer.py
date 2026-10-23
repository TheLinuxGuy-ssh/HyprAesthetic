#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hypraesthetic.installer import AUTOMATIC_SELECTION, Installer, _package_installed
from hypraesthetic.prefs import Prefs


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.commands: list[list[str]] = []

        def runner(cmd, **kwargs):
            self.commands.append(list(cmd))

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        self.runner = runner
        self.installer = Installer(
            repo_root=self.repo,
            distro_id="fedora-asahi-remix",
            runner=runner,
            assume_yes=True,
            euid=1000,
            apply_fn=lambda theme, **kwargs: None,
            backup_fn=lambda: "stamp",
            package_installed=lambda pkg: False,
            write_session=True,
        )

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        self.tmp.cleanup()

    def test_automatic_writes_default_prefs(self) -> None:
        result = self.installer.run(mode="automatic", theme="toji")
        prefs = Prefs.load()
        self.assertEqual(prefs.get("bar"), AUTOMATIC_SELECTION["bar"])
        self.assertEqual(prefs.get("file_manager"), "nautilus")
        self.assertEqual(result.mode, "automatic")

    def test_custom_selection_is_saved(self) -> None:
        self.installer.run(
            mode="custom",
            theme="a70",
            selection={"bar": "none", "file_manager": "thunar", "terminal": "foot"},
        )
        prefs = Prefs.load()
        self.assertEqual(prefs.get("bar"), "none")
        self.assertEqual(prefs.get("file_manager"), "thunar")
        self.assertEqual(prefs.get("terminal"), "foot")

    def test_writes_session_desktop_if_missing(self) -> None:
        self.installer.run(mode="automatic", theme="toji")
        desktop = self.home / ".local" / "share" / "applications" / "hyprland.desktop"
        self.assertTrue(desktop.is_file())
        self.assertIn("Exec=Hyprland", desktop.read_text(encoding="utf-8"))

    def test_custom_decline_records_skipped_packages_and_does_not_install(self) -> None:
        self.installer.assume_yes = False
        self.installer.confirm = lambda _packages: False
        result = self.installer.run(
            mode="custom",
            theme="toji",
            selection={"bar": "waybar", "file_manager": "nautilus", "terminal": "kitty"},
        )
        self.assertFalse(any(cmd and cmd[0] == "sudo" for cmd in self.commands))
        skipped = getattr(result, "packages_skipped", [])
        installed = getattr(result, "packages_installed", result.packages)
        self.assertTrue(skipped)
        self.assertEqual(installed, [])

    def test_custom_confirm_invokes_package_install(self) -> None:
        self.installer.assume_yes = False
        self.installer.euid = 1000
        self.installer.confirm = lambda _packages: True
        self.installer.run(
            mode="custom",
            theme="toji",
            selection={"bar": "waybar", "file_manager": "nautilus", "terminal": "kitty"},
        )
        self.assertTrue(any(cmd and cmd[0] == "sudo" for cmd in self.commands))

    def test_omitted_distro_id_id_like_arch_uses_pacman(self) -> None:
        release = "ID=unknown-arch-spin\nID_LIKE=arch\n"
        original_is_file = Path.is_file
        original_read_text = Path.read_text

        def is_file(path: Path, *args: object, **kwargs: object) -> bool:
            if path == Path("/etc/os-release"):
                return True
            return original_is_file(path, *args, **kwargs)

        def read_text(path: Path, *args: object, **kwargs: object) -> str:
            if path == Path("/etc/os-release"):
                return release
            return original_read_text(path, *args, **kwargs)

        commands: list[list[str]] = []

        def runner(cmd, **kwargs):
            commands.append(list(cmd))

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        with patch.object(Path, "is_file", is_file), patch.object(Path, "read_text", read_text):
            installer = Installer(
                repo_root=self.repo,
                runner=runner,
                assume_yes=True,
                euid=1000,
                apply_fn=lambda theme, **kwargs: None,
                backup_fn=lambda: "stamp",
                package_installed=lambda pkg: False,
                write_session=False,
                which=lambda name: "/usr/bin/paru" if name == "paru" else None,
            )
            result = installer.run(mode="automatic", theme="toji")
        self.assertTrue(any(cmd[:3] == ["sudo", "pacman", "-S"] for cmd in commands))
        self.assertIn("hyprland", result.packages)

    def test_root_pacman_command_omits_sudo(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **kwargs):
            commands.append(list(cmd))

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        installer = Installer(
            repo_root=self.repo,
            distro_id="cachyos",
            runner=runner,
            assume_yes=True,
            root_assume=True,
            euid=0,
            apply_fn=lambda theme, **kwargs: None,
            backup_fn=lambda: "stamp",
            package_installed=lambda pkg: False,
            write_session=False,
            which=lambda name: "/usr/bin/paru" if name == "paru" else None,
        )
        with redirect_stdout(StringIO()):
            installer.run(mode="automatic", theme="toji")
        pacman = [cmd for cmd in commands if cmd and "pacman" in cmd]
        self.assertTrue(pacman)
        self.assertEqual(pacman[0][:4], ["pacman", "-S", "--needed", "--noconfirm"])
        self.assertNotEqual(pacman[0][0], "sudo")

    def test_root_decline_raises_before_install(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **kwargs):
            commands.append(list(cmd))

        installer = Installer(
            repo_root=self.repo,
            distro_id="cachyos",
            runner=runner,
            assume_yes=False,
            euid=0,
            apply_fn=lambda theme, **kwargs: None,
            backup_fn=lambda: "stamp",
            package_installed=lambda pkg: False,
            write_session=True,
        )
        with patch("sys.stdin.isatty", return_value=False), redirect_stdout(StringIO()):
            with self.assertRaises(PermissionError) as caught:
                installer.run(mode="custom", theme="toji", selection={"bar": "waybar"})
        self.assertIn("root install declined", str(caught.exception))
        self.assertEqual(commands, [])
        desktop = self.home / ".local" / "share" / "applications" / "hyprland.desktop"
        self.assertFalse(desktop.exists())

    def test_root_assume_false_denies_even_when_packages_assume_yes(self) -> None:
        installer = Installer(
            repo_root=self.repo,
            distro_id="cachyos",
            assume_yes=True,
            root_assume=False,
            euid=0,
            root_confirm=lambda: False,
            write_session=False,
            package_installed=lambda _pkg: False,
        )
        with redirect_stdout(StringIO()):
            self.assertFalse(installer.allow_root())

    def test_repo_pacman_failure_skips_names_not_in_installed(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **_kwargs):
            commands.append(list(cmd))
            if cmd[:2] == ["paru", "--version"]:
                return SimpleNamespace(returncode=0)
            return SimpleNamespace(returncode=1)

        installer = self._arch_installer(runner, package_installed=lambda _pkg: False)
        ok = installer._install_packages(["hyprland", "waybar", "eww-git", "hyprwave-git"])
        self.assertFalse(ok)
        self.assertEqual(installer.packages_installed, [])
        self.assertEqual(installer.packages_skipped, ["hyprland", "waybar", "eww-git", "hyprwave-git"])
        pacman = [cmd for cmd in commands if "pacman" in cmd]
        self.assertEqual(pacman, [["sudo", "pacman", "-S", "--needed", "--noconfirm", "hyprland", "waybar"]])
        self.assertEqual(
            [cmd for cmd in commands if cmd and cmd[0] == "paru" and "-S" in cmd],
            [
                ["paru", "-S", "--needed", "--noconfirm", "eww-git"],
                ["paru", "-S", "--needed", "--noconfirm", "hyprwave-git"],
            ],
        )

    def test_aur_names_skip_sudo_for_user_and_root(self) -> None:
        for euid in (1000, 0):
            with self.subTest(euid=euid):
                commands: list[list[str]] = []

                def runner(cmd, **_kwargs):
                    commands.append(list(cmd))
                    return SimpleNamespace(returncode=0)

                installer = self._arch_installer(runner, euid=euid)
                installer._install_packages(["hyprland", "eww-git", "hyprwave-git", "waybar"])
                self.assertEqual(
                    [cmd for cmd in commands if cmd and cmd[0] in {"paru", "yay"} and "-S" in cmd],
                    [
                        ["paru", "-S", "--needed", "--noconfirm", "eww-git"],
                        ["paru", "-S", "--needed", "--noconfirm", "hyprwave-git"],
                    ],
                )
                repo = next(cmd for cmd in commands if "hyprland" in cmd)
                if euid == 0:
                    self.assertEqual(repo[:4], ["pacman", "-S", "--needed", "--noconfirm"])
                else:
                    self.assertEqual(repo[:5], ["sudo", "pacman", "-S", "--needed", "--noconfirm"])
                self.assertNotIn("eww-git", repo)
                self.assertNotIn("hyprwave-git", repo)

    def test_catalog_aur_name_uses_helper_not_pacman(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **_kwargs):
            commands.append(list(cmd))
            if cmd[:2] == ["paru", "--version"]:
                return SimpleNamespace(returncode=0)
            return SimpleNamespace(returncode=0)

        installer = self._arch_installer(
            runner,
            package_installed=lambda name: name not in {"hyprwave", "eww-git"},
        )
        installer._install_packages(["hyprland", "hyprwave", "eww-git"])
        self.assertIn(["paru", "-S", "--needed", "--noconfirm", "hyprwave"], commands)
        self.assertIn(["paru", "-S", "--needed", "--noconfirm", "eww-git"], commands)
        pacman = [cmd for cmd in commands if "pacman" in cmd]
        self.assertTrue(any("hyprland" in cmd for cmd in pacman))
        self.assertFalse(any("hyprwave" in cmd for cmd in pacman))

    def test_unrunnable_helper_is_rebuilt_before_aur_packages(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **_kwargs):
            commands.append(list(cmd))
            if cmd[:2] == ["paru", "--version"]:
                return SimpleNamespace(returncode=127)
            return SimpleNamespace(returncode=0)

        def ensure(name, **_kwargs):
            commands.append(["ensure", name])
            return name

        installer = self._arch_installer(runner, which=lambda name: "/usr/bin/paru" if name == "paru" else None)
        installer.ensure_helper = ensure
        installer._install_packages(["eww-git"])
        self.assertIn(["ensure", "paru"], commands)
        self.assertLess(commands.index(["ensure", "paru"]), commands.index(
            ["paru", "-S", "--needed", "--noconfirm", "eww-git"]
        ))

    def test_aur_assume_bootstraps_paru_before_aur_packages(self) -> None:
        commands: list[list[str]] = []
        state = {"have": False}

        def which(name: str) -> str | None:
            if name == "paru" and state["have"]:
                return "/usr/bin/paru"
            return None

        def runner(cmd, **_kwargs):
            commands.append(list(cmd))
            if "pacman" in cmd and "paru" in cmd:
                state["have"] = True
            return SimpleNamespace(returncode=0)

        installer = self._arch_installer(runner, which=which, euid=0)
        installer.aur_assume = True
        installer._install_packages(["waybar", "eww-git"])
        bootstrap = ["pacman", "-S", "--needed", "--noconfirm", "paru"]
        helper = ["paru", "-S", "--needed", "--noconfirm", "eww-git"]
        self.assertIn(bootstrap, commands)
        self.assertIn(helper, commands)
        self.assertLess(commands.index(bootstrap), commands.index(helper))
        self.assertFalse(any("clone" in cmd or "makepkg" in cmd for cmd in commands))
        self.assertNotIn("eww-git", next(cmd for cmd in commands if "waybar" in cmd))

    def test_run_reprobes_installed_and_skipped(self) -> None:
        present: set[str] = set()

        def runner(cmd, **_kwargs):
            if "waybar" in cmd and "pacman" in cmd:
                present.add("waybar")
            return SimpleNamespace(returncode=0)

        def probe(name: str) -> bool:
            if name == "waybar":
                return name in present
            if name == "eww-git":
                return False
            return True

        installer = self._arch_installer(runner, package_installed=probe)
        result = installer.run(mode="automatic", theme="toji")
        self.assertEqual(result.packages_installed, ["waybar"])
        self.assertEqual(result.packages_skipped, ["eww-git"])

    def test_aur_question_is_not_tied_to_package_assume_yes(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **_kwargs):
            commands.append(list(cmd))
            return SimpleNamespace(returncode=0)

        installer = self._arch_installer(runner, which=lambda _name: None)
        installer.assume_yes = True
        installer.aur_assume = False
        installer.aur_ask = lambda: "2"
        installer.ensure_helper = lambda name, **_kwargs: name
        with redirect_stdout(StringIO()):
            installer._install_packages(["eww-git"])
        self.assertEqual(commands, [["yay", "-S", "--needed", "--noconfirm", "eww-git"]])

    def test_user_nix_profile_install_is_unprefixed_and_success_is_not_a_skip(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **_kwargs):
            commands.append(list(cmd))
            return SimpleNamespace(returncode=0)

        installer = Installer(
            repo_root=self.repo,
            distro_id="nixos",
            runner=runner,
            assume_yes=True,
            euid=1000,
            write_session=False,
            package_installed=lambda _pkg: False,
            which=lambda _name: None,
        )
        ok = installer._install_packages(["hyprland", "waybar"])
        self.assertTrue(ok)
        self.assertEqual(commands, [["nix", "profile", "install", "hyprland", "waybar"]])
        self.assertEqual(installer.packages_installed, ["hyprland", "waybar"])
        self.assertEqual(installer.packages_skipped, [])

    def test_failed_nix_profile_install_stays_a_skip(self) -> None:
        commands: list[list[str]] = []

        def runner(cmd, **_kwargs):
            commands.append(list(cmd))
            return SimpleNamespace(returncode=1)

        installer = Installer(
            repo_root=self.repo,
            distro_id="nixos",
            runner=runner,
            assume_yes=True,
            euid=1000,
            write_session=False,
            package_installed=lambda _pkg: False,
            which=lambda _name: None,
        )
        self.assertFalse(installer._install_packages(["hyprland"]))
        self.assertEqual(commands, [["nix", "profile", "install", "hyprland"]])
        self.assertEqual(installer.packages_installed, [])
        self.assertEqual(installer.packages_skipped, ["hyprland"])

    def test_package_installed_recognizes_a_nix_profile_hit(self) -> None:
        listing = "0 - - nixpkgs#legacyPackages.x86_64-linux.hyprland\n"

        def which(name: str) -> str | None:
            return "/usr/bin/nix" if name == "nix" else None

        def run(cmd, **_kwargs):
            self.assertEqual(cmd[:3], ["nix", "profile", "list"])
            return SimpleNamespace(returncode=0, stdout=listing, stderr="")

        with (
            patch("hypraesthetic.installer.shutil.which", side_effect=which),
            patch("hypraesthetic.installer.subprocess.run", side_effect=run),
        ):
            self.assertTrue(_package_installed("hyprland"))
            self.assertFalse(_package_installed("waybar"))

    def _arch_installer(self, runner, *, euid: int = 1000, which=None, package_installed=None) -> Installer:
        return Installer(
            repo_root=self.repo,
            distro_id="cachyos",
            runner=runner,
            assume_yes=True,
            root_assume=True,
            euid=euid,
            apply_fn=lambda theme, **kwargs: None,
            backup_fn=lambda: "stamp",
            package_installed=package_installed or (lambda _pkg: False),
            write_session=False,
            which=which or (lambda name: "/usr/bin/paru" if name == "paru" else None),
        )


if __name__ == "__main__":
    unittest.main()
