#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
