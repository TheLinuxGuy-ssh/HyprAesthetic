#!/usr/bin/env python3

from __future__ import annotations

import unittest

from hypraesthetic.doctor import Doctor, DoctorCheck


class DoctorTests(unittest.TestCase):
    def test_reports_every_check_without_stopping(self) -> None:
        doctor = Doctor(
            catalog_commands={"hyprland": ["Hyprland"], "waybar": ["waybar"], "eww": ["eww"]},
            required={"hyprland", "waybar"},
            which=lambda cmd: "/usr/bin/Hyprland" if cmd == "Hyprland" else None,
        )
        report = doctor.run()
        self.assertGreaterEqual(len(report.checks), 3)
        missing = [c.id for c in report.checks if not c.ok]
        self.assertIn("waybar", missing)
        self.assertIn("eww", missing)
        self.assertFalse(report.ok)

    def test_optional_missing_does_not_fail_report(self) -> None:
        doctor = Doctor(
            catalog_commands={"hyprwave": ["hyprwave"]},
            required=set(),
            which=lambda cmd: None,
        )
        report = doctor.run()
        self.assertTrue(report.ok)
        self.assertFalse(report.checks[0].ok)
        self.assertFalse(report.checks[0].required)

    def test_check_dataclass(self) -> None:
        check = DoctorCheck(id="kitty", ok=True, required=True, detail="found")
        self.assertTrue(check.ok)


if __name__ == "__main__":
    unittest.main()
