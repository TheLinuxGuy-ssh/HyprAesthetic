#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hypraesthetic.cli import main
from hypraesthetic.paths import REPO_ROOT


class CliTests(unittest.TestCase):
    def _run(self, args: list[str]) -> tuple[int, str]:
        os.environ["HYPRAESTHETIC_ROOT"] = str(REPO_ROOT)
        from io import StringIO
        import sys

        buf = StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = main(args)
        finally:
            sys.stdout = old
        return code, buf.getvalue()

    def test_help_exits_zero(self) -> None:
        code, out = self._run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("ha-theme", out)

    def test_list_includes_toji(self) -> None:
        code, out = self._run(["list"])
        self.assertEqual(code, 0)
        self.assertIn("toji", out)

    def test_validate_official_themes(self) -> None:
        code, out = self._run(["validate"])
        self.assertEqual(code, 0)
        self.assertIn("toji", out)

    def test_custom_install_does_not_claim_complete_when_packages_skipped(self) -> None:
        class FakeInstaller:
            def __init__(self, **_kwargs) -> None:
                pass

            def run(self, **_kwargs):
                return SimpleNamespace(
                    mode="custom",
                    theme="toji",
                    packages=["hyprland"],
                    packages_installed=[],
                    packages_skipped=["hyprland"],
                )

        with tempfile.TemporaryDirectory() as tmp:
            preset = Path(tmp) / "preset.toml"
            preset.write_text('mode = "custom"\n', encoding="utf-8")
            with patch("hypraesthetic.cli.Installer", FakeInstaller):
                code, out = self._run(
                    [
                        "install",
                        "--mode",
                        "custom",
                        "--theme",
                        "toji",
                        "--preset",
                        str(preset),
                    ]
                )
        self.assertNotEqual(code, 0)
        self.assertNotIn("Installation complete", out)
        self.assertIn("skipped", out.lower())

    def test_store_refresh_is_what_a_new_store_lists(self) -> None:
        payload = b"""
[[themes]]
name = "from-refresh"
display_name = "From Refresh"
description = "Catalog written by store refresh"
author = "tester"
source = "https://github.com/example/from-refresh.git"
"""

        class Response:
            def read(self) -> bytes:
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

        from hypraesthetic.store import ThemeStore

        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                with patch("hypraesthetic.store.urlopen", return_value=Response()):
                    code, _out = self._run(
                        ["store", "refresh", "https://example.invalid/index.toml"]
                    )
                self.assertEqual(code, 0)
                store = ThemeStore()
                self.assertEqual([entry.name for entry in store.list()], ["from-refresh"])
                self.assertEqual(store.search("from-refresh")[0].name, "from-refresh")
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home


if __name__ == "__main__":
    unittest.main()
