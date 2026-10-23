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
    def _run3(self, args: list[str]) -> tuple[int, str, str]:
        os.environ["HYPRAESTHETIC_ROOT"] = str(REPO_ROOT)
        from io import StringIO
        import sys

        out_buf = StringIO()
        err_buf = StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = out_buf
        sys.stderr = err_buf
        try:
            code = main(args)
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
        return code, out_buf.getvalue(), err_buf.getvalue()

    def _run(self, args: list[str]) -> tuple[int, str]:
        code, out, _err = self._run3(args)
        return code, out

    def test_help_exits_zero(self) -> None:
        code, out = self._run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("ha-theme", out)
        self.assertIn("undo", out)

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

            def allow_root(self) -> bool:
                return True

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

    def test_install_root_declined_returns_1_without_run(self) -> None:
        ran = {"n": 0}

        class FakeInstaller:
            def __init__(self, **_kwargs) -> None:
                pass

            def allow_root(self) -> bool:
                return False

            def run(self, **_kwargs):
                ran["n"] += 1
                raise AssertionError("run should not be called")

        with patch("hypraesthetic.cli.Installer", FakeInstaller):
            code, out = self._run(["install", "--mode", "automatic", "--theme", "toji"])
        self.assertEqual(code, 1)
        self.assertEqual(ran["n"], 0)
        self.assertIn("Root install declined. Re-run as your user.", out)
        self.assertNotIn("Installation complete", out)

    def test_install_root_and_aur_assume_follow_yes_not_automatic_mode(self) -> None:
        captured: list[dict] = []

        class FakeInstaller:
            def __init__(self, **kwargs) -> None:
                captured.append(kwargs)

            def allow_root(self) -> bool:
                return True

            def run(self, **_kwargs):
                return SimpleNamespace(
                    mode="automatic",
                    theme="toji",
                    packages=[],
                    packages_installed=[],
                    packages_skipped=[],
                )

        with patch("hypraesthetic.cli.Installer", FakeInstaller), patch("sys.stdin.isatty", return_value=True):
            code, _out = self._run(["install", "--mode", "automatic", "--theme", "toji"])
        self.assertEqual(code, 0)
        self.assertTrue(captured[-1]["assume_yes"])
        self.assertFalse(captured[-1]["root_assume"])
        self.assertFalse(captured[-1]["aur_assume"])

        with patch("hypraesthetic.cli.Installer", FakeInstaller), patch("sys.stdin.isatty", return_value=False):
            code, _out = self._run(["install", "--mode", "automatic", "--theme", "toji"])
        self.assertEqual(code, 0)
        self.assertFalse(captured[-1]["root_assume"])
        self.assertTrue(captured[-1]["aur_assume"])

        with patch("hypraesthetic.cli.Installer", FakeInstaller), patch("sys.stdin.isatty", return_value=True):
            code, _out = self._run(["install", "--mode", "automatic", "--theme", "toji", "--yes"])
        self.assertEqual(code, 0)
        self.assertTrue(captured[-1]["root_assume"])
        self.assertTrue(captured[-1]["aur_assume"])

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

    def test_switch_unknown_theme_says_not_found(self) -> None:
        code, out, err = self._run3(["switch", "does-not-exist"])
        self.assertEqual(code, 1)
        self.assertIn("theme not found", (out + err).lower())
        self.assertNotIn("KeyError", out + err)

    def test_switch_waybar_dry_run_does_not_apply(self) -> None:
        with patch("hypraesthetic.cli.ApplyEngine") as eng:
            inst = eng.return_value
            inst.apply.return_value = SimpleNamespace(applied=["waybar"], errors=[], theme="sky")
            code, out, err = self._run3(["switch-waybar", "sky", "--dry-run"])
        self.assertEqual(code, 0)
        inst.apply.assert_called()
        kwargs = inst.apply.call_args.kwargs
        self.assertTrue(kwargs.get("dry_run") or inst.apply.call_args.args)
        # Prefer kwargs dry_run=True; also accept ApplyEngine(live=False) if that is how dry-run is wired.
        self.assertTrue(
            kwargs.get("dry_run") is True
            or (eng.call_args and eng.call_args.kwargs.get("live") is False)
        )

    def test_switch_component_usage_includes_dry_run(self) -> None:
        code, out, _err = self._run3(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("switch-<component> <theme> [--dry-run] [--restart]", out)

    def test_switch_component_apply_errors_exit_nonzero(self) -> None:
        with patch("hypraesthetic.cli.ApplyEngine") as eng:
            inst = eng.return_value
            inst.apply.return_value = SimpleNamespace(
                applied=[], errors=["waybar: boom"], theme="sky"
            )
            code, out, err = self._run3(["switch-waybar", "sky"])
        self.assertEqual(code, 1)
        self.assertIn("error: waybar: boom", err)
        self.assertIn("1 error", out)
        self.assertNotIn("configured", out)

    def test_restore_without_timestamp_lists_and_exits_zero(self) -> None:
        with patch("hypraesthetic.cli._bash", return_value=0) as bash:
            code, out, err = self._run3(["restore"])
        self.assertEqual(code, 0)
        bash.assert_called_once()
        args = bash.call_args.args
        self.assertEqual(args[0], "backup-configs.sh")
        self.assertEqual(list(args[1]), ["list"])

    def test_undo_without_snapshot_says_nothing_to_undo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                code, out, err = self._run3(["undo"])
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home
        self.assertEqual(code, 1)
        self.assertIn("Nothing to undo", err)
        self.assertNotIn("Traceback", err)

    def test_undo_prints_restored_theme(self) -> None:
        with patch(
            "hypraesthetic.undo.undo",
            return_value=SimpleNamespace(theme="sample", errors=[]),
        ) as undo:
            code, out, err = self._run3(["undo"])
        self.assertEqual(code, 0)
        self.assertIn("Restored sample", out)
        self.assertEqual(err, "")
        undo.assert_called_once()

    def test_undo_prints_apply_errors(self) -> None:
        with patch(
            "hypraesthetic.undo.undo",
            return_value=SimpleNamespace(theme="sky", errors=["hyprland: nope"]),
        ):
            code, out, err = self._run3(["undo"])
        self.assertEqual(code, 1)
        self.assertIn("error: hyprland: nope", err)
        self.assertIn("1 error", out)
        self.assertNotIn("Restored", out)

    def test_export_theme_requires_a_name(self) -> None:
        code, _out, err = self._run3(["export-theme"])
        self.assertEqual(code, 2)
        self.assertIn("export-theme <name>", err)

    def test_prefs_get_unknown_is_unset(self) -> None:
        code, out, err = self._run3(["prefs", "get", "no_such_pref"])
        self.assertEqual(code, 0)
        self.assertNotIn("None", out.strip())
        self.assertIn("unset", out.lower())


if __name__ == "__main__":
    unittest.main()
