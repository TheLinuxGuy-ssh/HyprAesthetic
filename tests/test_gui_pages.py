#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from hypraesthetic.doctor import DoctorCheck, DoctorReport
from hypraesthetic.prefs import Prefs
from hypraesthetic.preset import prepare_preset_switch
from hypraesthetic_gui.pages import PAGES
from hypraesthetic_gui.widgets import doctor_page, presets_page


def _descendants(widget: Gtk.Widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from _descendants(child)
        child = child.get_next_sibling()


def _labeled_buttons(root: Gtk.Widget) -> list[Gtk.Button]:
    return [
        widget
        for widget in _descendants(root)
        if isinstance(widget, Gtk.Button) and widget.get_label()
    ]


def _rows(root: Gtk.Widget) -> list[Adw.ActionRow]:
    return [widget for widget in _descendants(root) if isinstance(widget, Adw.ActionRow)]


class GuiPagesTests(unittest.TestCase):
    def test_required_tabs_exist(self) -> None:
        ids = [pid for pid, _title, _blurb in PAGES]
        for needed in ("presets", "bar", "widgets", "fonts", "apps", "look", "store", "doctor"):
            self.assertIn(needed, ids)


class DoctorPageTests(unittest.TestCase):
    def test_repair_names_missing_ids_and_installs(self) -> None:
        report = DoctorReport(
            checks=[
                DoctorCheck(id="dunst", ok=False, required=True, detail="missing: dunst"),
                DoctorCheck(id="nvim", ok=False, required=False, detail="missing: nvim"),
            ]
        )
        with patch("hypraesthetic_gui.widgets.Doctor") as doctor_cls, patch("subprocess.Popen") as popen:
            doctor_cls.return_value.run.return_value = report
            page = doctor_page()
            button = _labeled_buttons(page)[0]
            self.assertEqual(button.get_label(), "Install missing (dunst, nvim)")
            button.emit("clicked")
            popen.assert_called_once_with(["ha-theme", "install", "--mode", "automatic", "--yes"])

    def test_repair_with_nothing_missing_toasts_and_skips_install(self) -> None:
        report = DoctorReport(
            checks=[DoctorCheck(id="portal", ok=True, required=False, detail="no extra binary to check")]
        )
        with (
            patch("hypraesthetic_gui.widgets.Doctor") as doctor_cls,
            patch("subprocess.Popen") as popen,
            patch("hypraesthetic_gui.widgets._toast") as toast,
        ):
            doctor_cls.return_value.run.return_value = report
            page = doctor_page()
            button = _labeled_buttons(page)[0]
            self.assertEqual(button.get_label(), "Nothing to install")
            button.emit("clicked")
            popen.assert_not_called()
            toast.assert_called_once()
            self.assertEqual(toast.call_args.args[1], "Nothing missing")

    def test_missing_rows_use_error_and_warning_css(self) -> None:
        report = DoctorReport(
            checks=[
                DoctorCheck(id="dunst", ok=False, required=True, detail="missing: dunst", friendly="Dunst"),
                DoctorCheck(id="nvim", ok=False, required=False, detail="missing: nvim", friendly="Neovim"),
                DoctorCheck(id="portal", ok=True, required=False, detail="no extra binary to check"),
            ]
        )
        with patch("hypraesthetic_gui.widgets.Doctor") as doctor_cls:
            doctor_cls.return_value.run.return_value = report
            page = doctor_page()
        by_title = {row.get_title(): row for row in _rows(page)}
        self.assertIn("required missing", by_title["Dunst"].get_subtitle())
        self.assertIn("optional missing", by_title["Neovim"].get_subtitle())
        self.assertTrue(by_title["Dunst"].get_subtitle().startswith("required missing"))
        self.assertTrue(by_title["portal"].has_css_class("success"))
        self.assertTrue(by_title["Dunst"].has_css_class("error"))
        self.assertFalse(by_title["Dunst"].has_css_class("warning"))
        self.assertTrue(by_title["Neovim"].has_css_class("warning"))
        self.assertFalse(by_title["Neovim"].has_css_class("error"))


class PresetsUndoTests(unittest.TestCase):
    def test_presets_page_has_undo_button(self) -> None:
        page = presets_page()
        labels = [button.get_label() for button in _labeled_buttons(page)]
        self.assertIn("Undo last apply", labels)

    def test_undo_button_toasts_nothing_or_restored_theme(self) -> None:
        page = presets_page()
        button = next(
            item for item in _labeled_buttons(page) if item.get_label() == "Undo last apply"
        )
        with (
            patch("hypraesthetic.undo.undo", side_effect=FileNotFoundError("last-apply.toml")),
            patch("hypraesthetic_gui.widgets._toast") as toast,
        ):
            button.emit("clicked")
        self.assertEqual(toast.call_args.args[1], "Nothing to undo")
        with (
            patch("hypraesthetic.undo.undo", return_value="sample"),
            patch("hypraesthetic_gui.widgets._toast") as toast,
        ):
            button.emit("clicked")
        self.assertIn("sample", toast.call_args.args[1])

    def test_preset_click_keeps_wallpaper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                prefs = Prefs.load()
                prefs.set("wallpaper", "/tmp/custom.png")
                prefs.save()
                with (
                    patch("hypraesthetic_gui.widgets._apply", return_value=True),
                    patch(
                        "hypraesthetic_gui.widgets.prepare_preset_switch",
                        wraps=prepare_preset_switch,
                    ) as prepare,
                ):
                    page = presets_page()
                    tiles = [
                        widget
                        for widget in _descendants(page)
                        if isinstance(widget, Gtk.Button) and not widget.get_label()
                    ]
                    self.assertTrue(tiles)
                    tiles[0].emit("clicked")
                prepare.assert_called()
                self.assertEqual(Prefs.load().get("wallpaper"), "/tmp/custom.png")
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home


if __name__ == "__main__":
    unittest.main()
