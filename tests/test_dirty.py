#!/usr/bin/env python3

from __future__ import annotations

import unittest

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class DirtyApplyTests(unittest.TestCase):
    def test_button_is_insensitive_until_collect_differs(self) -> None:
        from hypraesthetic_gui.dirty import bind_dirty_apply

        state = {"v": 1}
        button = Gtk.Button(label="Apply changes")
        refresh = bind_dirty_apply(button, {"v": 1}, lambda: dict(state))
        self.assertFalse(button.get_sensitive())
        self.assertNotIn("suggested-action", list(button.get_css_classes()))
        state["v"] = 2
        refresh()
        self.assertTrue(button.get_sensitive())
        self.assertIn("suggested-action", list(button.get_css_classes()))


if __name__ == "__main__":
    unittest.main()
