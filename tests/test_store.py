#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hypraesthetic.paths import user_config_dir
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

    def test_refresh_user_index_is_what_list_and_search_read(self) -> None:
        payload = b"""
[[themes]]
name = "from-refresh"
display_name = "From Refresh"
description = "Catalog written by store refresh"
author = "tester"
source = "https://github.com/example/from-refresh.git"
"""
        home = Path(self.tmp.name) / "home"
        home.mkdir()
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)

        class Response:
            def read(self) -> bytes:
                return payload

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

        try:
            unused = Path(self.tmp.name) / "unused.toml"
            unused.write_text(INDEX, encoding="utf-8")
            dest = user_config_dir() / "store-index.toml"
            with patch("hypraesthetic.store.urlopen", return_value=Response()):
                written = ThemeStore(index_path=unused).refresh(
                    "https://example.invalid/store-index.toml",
                    dest,
                )
            self.assertEqual(written, dest)
            store = ThemeStore()
            self.assertEqual([entry.name for entry in store.list()], ["from-refresh"])
            hits = store.search("from-refresh")
            self.assertEqual(hits[0].name, "from-refresh")
            self.assertEqual(hits[0].source, "https://github.com/example/from-refresh.git")
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home


if __name__ == "__main__":
    unittest.main()
