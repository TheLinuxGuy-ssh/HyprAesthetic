#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hypraesthetic.install_theme import ThemeInstaller
from tests.test_theme import V2_TOML, write_theme


class InstallThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dest = self.root / "installed"
        self.installer = ThemeInstaller(dest_root=self.dest)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_install_from_directory(self) -> None:
        src = write_theme(self.root / "src", V2_TOML)
        installed = self.installer.install(str(src))
        self.assertEqual(installed.name, "sample")
        self.assertTrue((self.dest / "sample" / "theme.toml").is_file())

    def test_rejects_missing_manifest(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(ValueError):
            self.installer.install(str(empty))

    def test_install_from_git_url_uses_runner(self) -> None:
        calls: list[list[str]] = []

        def runner(cmd, **kwargs):
            calls.append(cmd)
            dest = Path(cmd[-1])
            dest.mkdir(parents=True)
            (dest / "theme.toml").write_text(
                V2_TOML.replace('name = "sample"', 'name = "fromgit"'),
                encoding="utf-8",
            )

            class Result:
                returncode = 0

            return Result()

        installer = ThemeInstaller(dest_root=self.dest, runner=runner)
        pkg = installer.install("https://github.com/example/fromgit.git")
        self.assertEqual(pkg.name, "fromgit")
        self.assertTrue(calls)
        self.assertEqual(calls[0][0], "git")


if __name__ == "__main__":
    unittest.main()
