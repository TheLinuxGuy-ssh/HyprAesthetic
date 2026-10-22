#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hypraesthetic.store import ThemeStore


INDEX = """
[[themes]]
name = "toji"
display_name = "Toji"
description = "Official Toji preset"
author = "HyprAesthetic"
source = "builtin"
preview = "preview.png"

[[themes]]
name = "community-dark"
display_name = "Community Dark"
description = "A ported rice"
author = "someone"
source = "https://github.com/example/community-dark.git"
preview = "https://example.com/preview.png"
"""


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.index = Path(self.tmp.name) / "store-index.toml"
        self.index.write_text(INDEX, encoding="utf-8")
        self.store = ThemeStore(index_path=self.index)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_lists_entries(self) -> None:
        names = [e.name for e in self.store.list()]
        self.assertEqual(names, ["toji", "community-dark"])

    def test_get_entry(self) -> None:
        entry = self.store.get("community-dark")
        self.assertTrue(entry.is_remote)
        self.assertEqual(entry.source, "https://github.com/example/community-dark.git")

    def test_builtin_is_not_remote(self) -> None:
        entry = self.store.get("toji")
        self.assertFalse(entry.is_remote)

    def test_search_matches_name_and_slash_slug(self) -> None:
        hits = self.store.search("hypraesthetic/toji")
        self.assertEqual(hits[0].name, "toji")
        hits = self.store.search("community")
        self.assertEqual(hits[0].name, "community-dark")

    def test_search_url_becomes_installable_entry(self) -> None:
        hits = self.store.search("https://github.com/example/night.git")
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].is_remote)
        self.assertEqual(hits[0].source, "https://github.com/example/night.git")


if __name__ == "__main__":
    unittest.main()
