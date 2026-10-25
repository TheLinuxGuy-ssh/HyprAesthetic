#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
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

    def test_explicit_aur_names_skip_the_repo_manager(self) -> None:
        repo, aur = split_repo_and_aur(
            ["hyprland", "hyprwave", "eww-git"],
            extra_aur={"hyprwave"},
        )
        self.assertEqual(repo, ["hyprland"])
        self.assertEqual(aur, ["hyprwave", "eww-git"])

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
        self.assertEqual(
            calls,
            [
                ["pacman", "-S", "--needed", "--noconfirm", "paru"],
                ["paru", "--version"],
            ],
        )

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

    def test_broken_bin_helper_is_replaced_with_source_build(self) -> None:
        """A prebuilt helper that cannot load libalpm must not count as installed."""
        calls: list[list[str]] = []
        source_built = {"ok": False}

        def which(name: str) -> str | None:
            if name == "paru":
                return "/usr/bin/paru"
            return None

        def runner(cmd, **kwargs):
            calls.append(list(cmd))
            cwd = kwargs.get("cwd")
            if cwd and "makepkg" in cmd:
                source_built["ok"] = True
                Path(cwd, "paru-1-1-x86_64.pkg.tar.zst").touch()
                return SimpleNamespace(returncode=0)
            if cmd[:1] == ["paru"] and "--version" in cmd:
                return SimpleNamespace(returncode=0 if source_built["ok"] else 127)
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=1000,
                which=which,
                privileged=privileged_command,
                environ={},
            )
        self.assertEqual(found, "paru")
        clones = [cmd for cmd in calls if "clone" in cmd]
        self.assertTrue(clones)
        self.assertIn("https://aur.archlinux.org/paru.git", clones[-1])
        self.assertNotIn("https://aur.archlinux.org/paru-bin.git", clones[-1])
        removes = [cmd for cmd in calls if any(tok.startswith("-R") for tok in cmd)]
        self.assertEqual(
            removes,
            [
                ["sudo", "pacman", "-R", "--noconfirm", "paru-bin-debug"],
                ["sudo", "pacman", "-R", "--noconfirm", "paru-bin"],
            ],
        )
        self.assertFalse(any("-Rcns" in cmd or "-c" in cmd or "-Rns" in cmd for cmd in calls))
        makepkg_at = next(i for i, cmd in enumerate(calls) if "makepkg" in cmd)
        debug_at = next(i for i, cmd in enumerate(calls) if cmd[-1:] == ["paru-bin-debug"])
        bin_at = next(i for i, cmd in enumerate(calls) if cmd[-1:] == ["paru-bin"] and "-R" in cmd)
        installs = [i for i, cmd in enumerate(calls) if "-U" in cmd]
        self.assertTrue(installs)
        install_at = installs[0]
        self.assertLess(makepkg_at, debug_at)
        self.assertLess(debug_at, bin_at)
        self.assertLess(bin_at, install_at)
        self.assertEqual(calls[makepkg_at], ["makepkg", "-s", "--noconfirm"])
        self.assertTrue(any(part.endswith(".pkg.tar.zst") for part in calls[install_at]))

    def test_root_broken_helper_builds_package_before_removing(self) -> None:
        """Root rebuilds with runuser, and the package file exists before -R."""
        calls: list[list[str]] = []
        installed = {"ok": False}
        built: dict[str, str] = {}
        present_at_remove: list[bool] = []
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="builder")

        def runner(cmd, **kwargs):
            calls.append(list(cmd))
            cwd = kwargs.get("cwd")
            if cwd and "makepkg" in cmd:
                path = Path(cwd, "paru-1-1-x86_64.pkg.tar.zst")
                path.touch()
                built["path"] = str(path)
                return SimpleNamespace(returncode=0)
            if any(tok.startswith("-R") for tok in cmd):
                present_at_remove.append(bool(built.get("path") and Path(built["path"]).is_file()))
            if "-U" in cmd:
                installed["ok"] = True
                return SimpleNamespace(returncode=0)
            if cmd[:1] == ["paru"] and "--version" in cmd:
                return SimpleNamespace(returncode=0 if installed["ok"] else 127)
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=lambda name: "/usr/bin/paru" if name == "paru" else None,
                privileged=privileged_command,
                environ={},
                users=[user],
            )
        self.assertEqual(found, "paru")
        self.assertEqual(
            [cmd for cmd in calls if any(tok.startswith("-R") for tok in cmd)],
            [
                ["pacman", "-R", "--noconfirm", "paru-bin-debug"],
                ["pacman", "-R", "--noconfirm", "paru-bin"],
            ],
        )
        self.assertFalse(any("-Rns" in cmd for cmd in calls))
        self.assertEqual(present_at_remove, [True, True])
        self.assertFalse(any("-Rcns" in cmd or "-c" in cmd for cmd in calls))
        self.assertFalse(any(cmd and cmd[0] in {"makepkg", "sudo"} for cmd in calls))
        clone = next(cmd for cmd in calls if "clone" in cmd)
        self.assertEqual(clone[:5], ["runuser", "-u", "builder", "--", "git"])
        self.assertIn("https://aur.archlinux.org/paru.git", clone)
        self.assertNotIn("https://aur.archlinux.org/paru-bin.git", clone)
        makepkg = [cmd for cmd in calls if "makepkg" in cmd]
        self.assertEqual(makepkg, [["runuser", "-u", "builder", "--", "makepkg", "-s", "--noconfirm"]])
        install = next(cmd for cmd in calls if "-U" in cmd)
        self.assertEqual(install[:3], ["pacman", "-U", "--noconfirm"])
        self.assertTrue(install[-1].endswith(".pkg.tar.zst"))
        makepkg_at = next(i for i, cmd in enumerate(calls) if "makepkg" in cmd)
        remove_at = next(i for i, cmd in enumerate(calls) if any(tok.startswith("-R") for tok in cmd))
        install_at = next(i for i, cmd in enumerate(calls) if "-U" in cmd)
        self.assertLess(makepkg_at, remove_at)
        self.assertLess(remove_at, install_at)

    def test_failed_makepkg_does_not_remove_broken_helper(self) -> None:
        calls: list[list[str]] = []

        def runner(cmd, **_kwargs):
            calls.append(list(cmd))
            if cmd[:1] == ["paru"] and "--version" in cmd:
                return SimpleNamespace(returncode=127)
            if "makepkg" in cmd:
                return SimpleNamespace(returncode=1)
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=1000,
                which=lambda name: "/usr/bin/paru" if name == "paru" else None,
                privileged=privileged_command,
                environ={},
            )
        self.assertIsNone(found)
        self.assertFalse(any(any(tok.startswith("-R") for tok in cmd) for cmd in calls))
        self.assertFalse(any("-U" in cmd for cmd in calls))

    def test_root_missing_package_file_does_not_remove_or_install(self) -> None:
        calls: list[list[str]] = []
        saw_makepkg = {"ok": False}
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="builder")

        def runner(cmd, **_kwargs):
            calls.append(list(cmd))
            if "makepkg" in cmd:
                saw_makepkg["ok"] = True
                return SimpleNamespace(returncode=0)
            if cmd[:1] == ["paru"] and "--version" in cmd:
                return SimpleNamespace(returncode=0 if saw_makepkg["ok"] else 127)
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=lambda name: "/usr/bin/paru" if name == "paru" else None,
                privileged=privileged_command,
                environ={},
                users=[user],
            )
        self.assertIsNone(found)
        self.assertFalse(any(any(tok.startswith("-R") for tok in cmd) for cmd in calls))
        self.assertFalse(any("-U" in cmd for cmd in calls))

    def _assert_failed_upgrade_keeps_archive(
        self,
        calls: list[list[str]],
        *,
        found,
        built: Path,
        present_at_remove: list[bool],
        install_paths: list[str],
        remove_prefix: list[str],
    ) -> None:
        self.assertIsNone(found)
        self.assertTrue(install_paths, "pacman -U did not run")
        self.assertTrue(all(path.endswith(".pkg.tar.zst") for path in install_paths))
        self.assertTrue(all(Path(path).is_file() for path in install_paths))
        self.assertTrue(built.is_file())
        self.assertEqual(present_at_remove, [True, True])
        removes = [cmd for cmd in calls if any(tok.startswith("-R") for tok in cmd)]
        self.assertEqual(
            removes,
            [
                [*remove_prefix, "paru-bin-debug"],
                [*remove_prefix, "paru-bin"],
            ],
        )
        self.assertFalse(any("-Rcns" in cmd or "-c" in cmd or "-Rns" in cmd or "-s" in cmd for cmd in removes))
        makepkg_at = next(i for i, cmd in enumerate(calls) if "makepkg" in cmd)
        remove_at = next(i for i, cmd in enumerate(calls) if any(tok.startswith("-R") for tok in cmd))
        install_at = next(i for i, cmd in enumerate(calls) if "-U" in cmd)
        self.assertLess(makepkg_at, remove_at)
        self.assertLess(remove_at, install_at)

    def test_pacman_u_failure_does_not_count_as_installed(self) -> None:
        calls: list[list[str]] = []
        saw_makepkg = {"ok": False}
        built: dict[str, Path] = {}
        present_at_remove: list[bool] = []
        install_paths: list[str] = []

        def runner(cmd, **kwargs):
            calls.append(list(cmd))
            cwd = kwargs.get("cwd")
            if cwd and "makepkg" in cmd:
                path = Path(cwd, "paru-1-1-x86_64.pkg.tar.zst")
                path.touch()
                built["path"] = path
                saw_makepkg["ok"] = True
                return SimpleNamespace(returncode=0)
            if any(tok.startswith("-R") for tok in cmd):
                present_at_remove.append(bool(built.get("path") and built["path"].is_file()))
            if "-U" in cmd:
                install_paths.extend(part for part in cmd if part.endswith(".pkg.tar.zst"))
                return SimpleNamespace(returncode=1)
            if cmd[:1] == ["paru"] and "--version" in cmd:
                return SimpleNamespace(returncode=0 if saw_makepkg["ok"] else 127)
            return SimpleNamespace(returncode=0)

        def cleanup() -> None:
            path = built.get("path")
            if path is not None:
                shutil.rmtree(path.parent, ignore_errors=True)

        self.addCleanup(cleanup)
        with redirect_stdout(StringIO()), patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=1000,
                which=lambda name: "/usr/bin/paru" if name == "paru" else None,
                privileged=privileged_command,
                environ={},
            )
        self._assert_failed_upgrade_keeps_archive(
            calls,
            found=found,
            built=built["path"],
            present_at_remove=present_at_remove,
            install_paths=install_paths,
            remove_prefix=["sudo", "pacman", "-R", "--noconfirm"],
        )

    def test_root_pacman_u_failure_keeps_archive_after_plain_remove(self) -> None:
        calls: list[list[str]] = []
        built: dict[str, Path] = {}
        present_at_remove: list[bool] = []
        install_paths: list[str] = []
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="builder")

        def runner(cmd, **kwargs):
            calls.append(list(cmd))
            cwd = kwargs.get("cwd")
            if cwd and "makepkg" in cmd:
                path = Path(cwd, "paru-1-1-x86_64.pkg.tar.zst")
                path.touch()
                built["path"] = path
                return SimpleNamespace(returncode=0)
            if any(tok.startswith("-R") for tok in cmd):
                present_at_remove.append(bool(built.get("path") and built["path"].is_file()))
            if "-U" in cmd:
                install_paths.extend(part for part in cmd if part.endswith(".pkg.tar.zst"))
                return SimpleNamespace(returncode=1)
            if cmd[:1] == ["paru"] and "--version" in cmd:
                return SimpleNamespace(returncode=127)
            return SimpleNamespace(returncode=0)

        def cleanup() -> None:
            path = built.get("path")
            if path is not None:
                shutil.rmtree(path.parent, ignore_errors=True)

        self.addCleanup(cleanup)
        with redirect_stdout(StringIO()), patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=lambda name: "/usr/bin/paru" if name == "paru" else None,
                privileged=privileged_command,
                environ={},
                users=[user],
            )
        self._assert_failed_upgrade_keeps_archive(
            calls,
            found=found,
            built=built["path"],
            present_at_remove=present_at_remove,
            install_paths=install_paths,
            remove_prefix=["pacman", "-R", "--noconfirm"],
        )
        self.assertFalse(any(cmd and cmd[0] in {"makepkg", "sudo"} for cmd in calls))
        clone = next(cmd for cmd in calls if "clone" in cmd)
        self.assertIn("https://aur.archlinux.org/paru.git", clone)
        self.assertNotIn("https://aur.archlinux.org/paru-bin.git", clone)

    def test_root_clone_failure_skips_makepkg_and_install(self) -> None:
        calls: list[list[str]] = []
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="builder")

        def runner(cmd, **_kwargs):
            calls.append(list(cmd))
            if "clone" in cmd:
                return SimpleNamespace(returncode=128)
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=lambda _name: None,
                privileged=privileged_command,
                environ={},
                users=[user],
            )
        self.assertIsNone(found)
        self.assertTrue(any("clone" in cmd for cmd in calls))
        self.assertFalse(any("makepkg" in cmd for cmd in calls))
        self.assertFalse(any("-U" in cmd for cmd in calls))

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

    def test_missing_git_or_runuser_does_not_raise(self) -> None:
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="builder")
        cases = (
            ("git", 1000, None),
            ("runuser", 0, [user]),
            ("makepkg", 1000, None),
        )
        for missing, euid, users in cases:
            with self.subTest(missing=missing):
                def runner(cmd, **_kwargs):
                    if missing == "makepkg" and "makepkg" in cmd:
                        raise FileNotFoundError("makepkg")
                    if missing == "git" and (cmd[0] == "git" or (len(cmd) >= 5 and cmd[4] == "git")):
                        raise FileNotFoundError("git")
                    if missing == "runuser" and cmd[0] == "runuser":
                        raise FileNotFoundError("runuser")
                    return SimpleNamespace(returncode=0 if "clone" in cmd or "makepkg" in cmd else 1)

                try:
                    found = ensure_helper(
                        "paru",
                        runner=runner,
                        euid=euid,
                        which=lambda _name: None,
                        privileged=privileged_command,
                        environ={"SUDO_USER": "builder"} if euid != 0 else {},
                        users=users,
                    )
                except OSError as exc:
                    self.fail(f"missing {missing} raised {exc!r}")
                self.assertIsNone(found)

    def test_pacman_u_failure_prints_archive_directory_and_packages(self) -> None:
        built: dict[str, Path] = {}
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid(), pw_name="builder")

        def runner(cmd, **kwargs):
            cwd = kwargs.get("cwd")
            if cwd and "makepkg" in cmd:
                first = Path(cwd, "paru-bin-1-1-x86_64.pkg.tar.zst")
                second = Path(cwd, "paru-bin-debug-1-1-x86_64.pkg.tar.zst")
                first.touch()
                second.touch()
                built["dir"] = Path(cwd)
                built["paths"] = [first, second]
                return SimpleNamespace(returncode=0)
            if "-U" in cmd:
                return SimpleNamespace(returncode=1)
            return SimpleNamespace(returncode=0)

        def cleanup() -> None:
            directory = built.get("dir")
            if directory is not None:
                shutil.rmtree(directory, ignore_errors=True)

        self.addCleanup(cleanup)
        buf = StringIO()
        with redirect_stdout(buf), patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=0,
                which=lambda _name: None,
                privileged=privileged_command,
                environ={},
                users=[user],
            )
        printed = buf.getvalue()
        self.assertIsNone(found)
        self.assertTrue(built["paths"])
        self.assertIn(str(built["dir"]), printed)
        for path in built["paths"]:
            self.assertIn(str(path), printed)
            self.assertTrue(path.is_file())

    def test_removed_bin_helper_prints_same_archive_paths_when_pacman_u_fails(self) -> None:
        calls: list[list[str]] = []
        built: dict[str, Path] = {}

        def runner(cmd, **kwargs):
            calls.append(list(cmd))
            cwd = kwargs.get("cwd")
            if cwd and "makepkg" in cmd:
                path = Path(cwd, "paru-1-1-x86_64.pkg.tar.zst")
                path.touch()
                built["path"] = path
                return SimpleNamespace(returncode=0)
            if any(tok.startswith("-R") for tok in cmd):
                return SimpleNamespace(returncode=0)
            if "-U" in cmd:
                return SimpleNamespace(returncode=1)
            if cmd[:1] == ["paru"] and "--version" in cmd:
                return SimpleNamespace(returncode=127)
            return SimpleNamespace(returncode=0)

        def cleanup() -> None:
            path = built.get("path")
            if path is not None:
                shutil.rmtree(path.parent, ignore_errors=True)

        self.addCleanup(cleanup)
        buf = StringIO()
        with redirect_stdout(buf), patch("subprocess.run", side_effect=AssertionError("real subprocess")):
            found = ensure_helper(
                "paru",
                runner=runner,
                euid=1000,
                which=lambda name: "/usr/bin/paru" if name == "paru" else None,
                privileged=privileged_command,
                environ={},
            )
        printed = buf.getvalue()
        self.assertIsNone(found)
        self.assertIn(str(built["path"].parent), printed)
        self.assertIn(str(built["path"]), printed)
        self.assertTrue(built["path"].is_file())
        removes = [cmd for cmd in calls if any(tok.startswith("-R") for tok in cmd)]
        self.assertEqual(removes[-1][-1], "paru-bin")
        self.assertEqual(
            [line for line in printed.splitlines() if line.endswith(".pkg.tar.zst")],
            [str(built["path"])],
        )

    def test_readme_installation_mentions_aur_helper(self) -> None:
        readme = Path(__file__).resolve().parents[1] / "README.md"
        install = readme.read_text(encoding="utf-8").split("## Quick start", 1)[1].split("\n## ", 1)[0]
        self.assertIn("paru", install)
        self.assertIn("yay", install)


if __name__ == "__main__":
    unittest.main()
