#!/usr/bin/env python3

from __future__ import annotations

import unittest

from hypraesthetic.prefs import Prefs
from hypraesthetic.preset import prepare_preset_switch


class PreparePresetSwitchTests(unittest.TestCase):
    def test_prepare_preset_switch_keeps_wallpaper(self) -> None:
        prefs = Prefs.load()
        prefs.set("wallpaper", "/tmp/custom.png")
        prepare_preset_switch(prefs)
        self.assertEqual(prefs.get("wallpaper"), "/tmp/custom.png")


if __name__ == "__main__":
    unittest.main()
