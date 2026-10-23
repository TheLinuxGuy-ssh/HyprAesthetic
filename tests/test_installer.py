#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hypraesthetic.installer import AUTOMATIC_SELECTION, Installer
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

        self.installer = Installer(
            repo_root=self.repo,
            distro_id="fedora-asahi-remix",
            runner=runner,
            assume_yes=True,
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
                apply_fn=lambda theme, **kwargs: None,
                backup_fn=lambda: "stamp",
                package_installed=lambda pkg: False,
                write_session=False,
            )
            result = installer.run(mode="automatic", theme="toji")
        self.assertTrue(any(cmd[:3] == ["sudo", "pacman", "-S"] for cmd in commands))
        self.assertIn("hyprland", result.packages)


if __name__ == "__main__":
    unittest.main()
