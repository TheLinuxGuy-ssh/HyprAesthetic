#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CommunityFilesTests(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        for name in (
            "README.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "SECURITY.md",
            "CHANGELOG.md",
            "SUPPORT.md",
            ".editorconfig",
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/ISSUE_TEMPLATE/config.yml",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            "docs/store.md",
            "data/store-index.toml",
            "data/packages.toml",
        ):
            path = ROOT / name
            self.assertTrue(path.is_file(), f"missing {name}")

    def test_no_placeholder_contacts(self) -> None:
        hits: list[str] = []
        for path in (*ROOT.glob("*.md"), ROOT / "CODE_OF_CONDUCT.md"):
            if path.is_file() and "your-email@example.com" in path.read_text(encoding="utf-8"):
                hits.append(path.name)
        self.assertEqual(hits, [], f"placeholder email in {hits}")

    def test_security_points_at_advisories_and_maintainer(self) -> None:
        text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("mr.linux.0@protonmail.com", text)
        self.assertIn("security/advisories/new", text)
        self.assertIn("0.2", text)
        self.assertNotIn("Hypraesthetic-theme", text)

    def test_license_is_mit(self) -> None:
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", text)
        self.assertIn("Permission is hereby granted", text)

    def test_readme_has_required_headings(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for heading in (
            "## Quick start",
            "## Themes: proof, not promises",
            "## Bars",
            "## Control center",
            "## How it works",
            "## Everything in the box",
            "## Cheat sheet",
            "## Keybinds",
            "## Make your own theme",
            "## Your settings",
            "## FAQ",
            "## Join in",
            "## Thanks",
            "## License",
        ):
            self.assertIn(heading, text, heading)

    def test_readme_leads_with_banner_and_bar_shots(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/assets/banner.png", text)
        self.assertIn("themes/a70/bar.png", text)
        self.assertIn("themes/choso/bar.png", text)
        self.assertIn("themes/jjk/bar.png", text)
        self.assertIn("themes/sky/bar.png", text)
        self.assertIn("themes/spartan/bar.png", text)
        self.assertIn("themes/tanjiro/bar.png", text)
        self.assertIn("themes/toji/bar.png", text)
        self.assertIn("themes/toji_2/bar.png", text)
        self.assertLess(text.find("docs/assets/banner.png"), text.find("## Quick start"))
