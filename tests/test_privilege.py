#!/usr/bin/env python3

from __future__ import annotations

import unittest

from hypraesthetic.privilege import ROOT_WARNING, allow_root_install, privileged_command


class PrivilegeTests(unittest.TestCase):
    def test_warning_mentions_root_and_sudo_user(self) -> None:
        self.assertIn("running as root", ROOT_WARNING)
        self.assertIn("sudo ./install.sh", ROOT_WARNING)
        self.assertIn("/root", ROOT_WARNING)

    def test_non_root_is_allowed(self) -> None:
        self.assertTrue(allow_root_install(euid=1000, assume_yes=False, confirm=lambda: False))

    def test_root_without_yes_defaults_to_denied(self) -> None:
        self.assertFalse(
            allow_root_install(
                euid=0,
                assume_yes=False,
                confirm=lambda: False,
                stdin_isatty=True,
                printer=lambda _msg: None,
            )
        )

    def test_root_yes_flag_allows_after_warning(self) -> None:
        printed: list[str] = []
        self.assertTrue(
            allow_root_install(euid=0, assume_yes=True, confirm=lambda: False, printer=printed.append)
        )
        self.assertEqual(printed, [ROOT_WARNING])

    def test_root_confirm_yes_allows(self) -> None:
        self.assertTrue(
            allow_root_install(
                euid=0,
                assume_yes=False,
                confirm=lambda: True,
                stdin_isatty=True,
                printer=lambda _msg: None,
            )
        )

    def test_root_prompt_uses_y_n_and_blank_denies(self) -> None:
        seen: list[str] = []

        def prompt(text: str) -> str:
            seen.append(text)
            return ""

        self.assertFalse(
            allow_root_install(euid=0, assume_yes=False, stdin_isatty=True, prompt=prompt, printer=lambda _msg: None)
        )
        self.assertEqual(seen, ["Continue as root anyway? [y/N]: "])

    def test_root_prompt_yes_allows(self) -> None:
        self.assertTrue(
            allow_root_install(
                euid=0,
                assume_yes=False,
                stdin_isatty=True,
                prompt=lambda _text: "yes",
                printer=lambda _msg: None,
            )
        )

    def test_root_non_tty_denies_without_prompt(self) -> None:
        def prompt(_text: str) -> str:
            raise AssertionError("prompted")

        self.assertFalse(
            allow_root_install(
                euid=0,
                assume_yes=False,
                stdin_isatty=False,
                prompt=prompt,
                printer=lambda _msg: None,
            )
        )

    def test_privileged_command_skips_sudo_when_root(self) -> None:
        self.assertEqual(
            privileged_command(["pacman", "-S", "hyprland"], euid=0),
            ["pacman", "-S", "hyprland"],
        )

    def test_privileged_command_prefixes_sudo_when_user(self) -> None:
        self.assertEqual(
            privileged_command(["pacman", "-S", "hyprland"], euid=1000),
            ["sudo", "pacman", "-S", "hyprland"],
        )

    def test_privileged_command_does_not_double_sudo(self) -> None:
        self.assertEqual(
            privileged_command(["sudo", "pacman", "-S", "hyprland"], euid=1000),
            ["sudo", "pacman", "-S", "hyprland"],
        )

    def test_privileged_command_leaves_nix_profile_install_unprefixed(self) -> None:
        argv = ["nix", "profile", "install", "hyprland", "waybar"]
        self.assertEqual(privileged_command(argv, euid=1000), argv)


if __name__ == "__main__":
    unittest.main()
