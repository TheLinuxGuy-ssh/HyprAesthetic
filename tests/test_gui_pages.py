#!/usr/bin/env python3

from __future__ import annotations

import unittest

from hypraesthetic_gui.pages import PAGES


class GuiPagesTests(unittest.TestCase):
    def test_required_tabs_exist(self) -> None:
        ids = [pid for pid, _title, _blurb in PAGES]
        for needed in ("presets", "bar", "widgets", "fonts", "apps", "look", "store", "doctor"):
            self.assertIn(needed, ids)


if __name__ == "__main__":
    unittest.main()
