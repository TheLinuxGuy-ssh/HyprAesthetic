#!/usr/bin/env python3

from __future__ import annotations

import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hypraesthetic.aur import (
    build_user,
    choose_helper,
    ensure_helper,
    find_helper,
    split_repo_and_aur,
)
from hypraesthetic.privilege import privileged_command


class AurTests(unittest.TestCase):
    def test_split_puts_git_packages_on_aur_side(self) -> None:
        repo, aur = split_repo_and_aur(["hyprland", "eww-git", "hyprwave-git", "waybar"])
        self.assertEqual(repo, ["hyprland", "waybar"])
        self.assertEqual(aur, ["eww-git", "hyprwave-git"])

    def test_find_helper_prefers_paru(self) -> None:
        self.assertEqual(find_helper(which=lambda n: "/usr/bin/paru" if n == "paru" else None), "paru")
        self.assertEqual(find_helper(which=lambda n: f"/usr/bin/{n}"), "paru")
        self.assertIsNone(find_helper(which=lambda _n: None))

    def test_choose_helper_yes_defaults_paru(self) -> None:
        self.assertEqual(choose_helper(assume_yes=True, which=lambda _n: None), "paru")

    def test_choose_helper_asks_when_interactive(self) -> None:
        with redirect_stdout(StringIO()):
            self.assertEqual(
                choose_helper(assume_yes=False, which=lambda _n: None, ask=lambda: "2"),
                "yay",
            )

    def test_choose_helper_prompt_text(self) -> None:
        lines: list[str] = []
        with patch("builtins.input", return_value="1") as mocked:
            chosen = choose_helper(assume_yes=False, which=lambda _n: None, printer=lines.append)
        self.assertEqual(chosen, "paru")
        mocked.assert_called_once_with("Install which helper? [1/2]: ")
        self.assertEqual(
            lines,
            [
                "No AUR helper found (paru or yay).",
                "  1) paru  (recommended)",
                "  2) yay",
            ],
        )

    def test_choose_helper_keeps_installed_helper(self) -> None:
        def ask() -> str:
            raise AssertionError("asked")

        self.assertEqual(
            choose_helper(
                assume_yes=False,
                which=lambda n: "/usr/bin/yay" if n == "yay" else None,
                ask=ask,
            ),
            "yay",
        )

    def test_build_user_uses_sudo_user_then_uid(self) -> None:
        self.assertEqual(build_user(euid=0, environ={"SUDO_USER": "anonymous"}), "anonymous")
        self.assertIsNone(build_user(euid=0, environ={}, users=[]))
        self.assertIsNone(build_user(euid=0, environ={"SUDO_USER": "root"}, users=[]))
        users = [
            SimpleNamespace(pw_uid=1001, pw_name="second"),
            SimpleNamespace(pw_uid=1000, pw_name="first"),
            SimpleNamespace(pw_uid=0, pw_name="root"),
            SimpleNamespace(pw_uid=65534, pw_name="nobody"),
        ]
        self.assertEqual(build_user(euid=0, environ={}, users=users), "first")

    def test_ensure_helper_pacman_installs_name_before_clone(self) -> None:
        calls: list[list[str]] = []

        def which(name: str) -> str | None:
            if name == "paru" and calls:
                return "/usr/bin/paru"
            return None

        def runner(cmd, **_kwargs):
            calls.append(list(cmd))
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=which,
                privileged=privileged_command,
                environ={},
                users=[],
            )
        self.assertEqual(found, "paru")
        self.assertEqual(calls, [["pacman", "-S", "--needed", "--noconfirm", "paru"]])

    def test_ensure_helper_skips_clone_without_build_user(self) -> None:
        calls: list[list[str]] = []

        def runner(cmd, **_kwargs):
            calls.append(list(cmd))
            return SimpleNamespace(returncode=1)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=lambda _n: None,
                privileged=privileged_command,
                environ={},
                users=[],
            )
        self.assertIsNone(found)
        self.assertEqual(calls, [["pacman", "-S", "--needed", "--noconfirm", "paru"]])
        self.assertFalse(any("makepkg" in cmd or "clone" in cmd for cmd in calls))

    def test_root_makepkg_uses_runuser_and_aur_bin(self) -> None:
        calls: list[tuple[list[str], str | None]] = []
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="builder")

        def runner(cmd, **kwargs):
            cwd = kwargs.get("cwd")
            calls.append((list(cmd), cwd))
            if cwd and "makepkg" in cmd:
                Path(cwd, "paru-bin-1-1-any.pkg.tar.zst").touch()
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=lambda _n: None,
                privileged=privileged_command,
                environ={},
                users=[user],
            )
        commands = [cmd for cmd, _cwd in calls]
        self.assertIsNone(found)
        self.assertIn(["pacman", "-S", "--needed", "--noconfirm", "paru"], commands)
        self.assertIn(["pacman", "-S", "--needed", "--noconfirm", "base-devel", "git"], commands)
        clone = next(cmd for cmd in commands if "clone" in cmd)
        self.assertEqual(clone[:5], ["runuser", "-u", "builder", "--", "git"])
        self.assertIn("https://aur.archlinux.org/paru-bin.git", clone)
        makepkg = [cmd for cmd in commands if "makepkg" in cmd]
        self.assertEqual(makepkg, [["runuser", "-u", "builder", "--", "makepkg", "-s", "--noconfirm"]])
        self.assertTrue(any(cmd[:3] == ["pacman", "-U", "--noconfirm"] for cmd in commands))
        self.assertFalse(any(cmd and cmd[0] == "makepkg" for cmd in commands))
        self.assertFalse(any(cmd and cmd[0] == "sudo" for cmd in commands))

    def test_user_makepkg_installs_with_si(self) -> None:
        calls: list[list[str]] = []

        def runner(cmd, **_kwargs):
            calls.append(list(cmd))
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            ensure_helper(
                "yay",
                runner=runner,
                euid=1000,
                which=lambda _n: None,
                privileged=privileged_command,
                environ={"SUDO_USER": "builder"},
            )
        self.assertIn(["sudo", "pacman", "-S", "--needed", "--noconfirm", "yay"], calls)
        clone = next(cmd for cmd in calls if "clone" in cmd)
        self.assertEqual(clone[0], "git")
        self.assertIn("https://aur.archlinux.org/yay-bin.git", clone)
        self.assertIn(["makepkg", "-si", "--noconfirm"], calls)
        self.assertFalse(any(cmd and cmd[0] == "runuser" for cmd in calls))
        self.assertFalse(any("-U" in cmd for cmd in calls))

    def test_readme_installation_mentions_aur_helper(self) -> None:
        readme = Path(__file__).resolve().parents[1] / "README.md"
        install = readme.read_text(encoding="utf-8").split("## Installation", 1)[1].split("\n## ", 1)[0]
        self.assertIn("paru", install)
        self.assertIn("yay", install)
        self.assertIn("-git", install)


if __name__ == "__main__":
    unittest.main()
