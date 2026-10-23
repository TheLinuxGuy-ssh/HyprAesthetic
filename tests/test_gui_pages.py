#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hypraesthetic.doctor import DoctorCheck, DoctorReport
from hypraesthetic.paths import current_theme_file
from hypraesthetic.prefs import Prefs
from hypraesthetic.preset import prepare_preset_switch
from hypraesthetic.store import StoreEntry
from hypraesthetic_gui.pages import PAGES
from hypraesthetic.discover import geom_to_fraction
from hypraesthetic.paths import layouts_dir


def _gtk_ok() -> bool:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        gi.require_version("Pango", "1.0")
        from gi.repository import Adw, Gtk, Pango  # noqa: F401
    except (ValueError, ImportError):
        return False
    return True


if _gtk_ok():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Pango", "1.0")
    from gi.repository import Adw, Gtk, Pango
    from hypraesthetic_gui.widgets import (
        WidgetEditor,
        apps_page,
        bar_page,
        doctor_page,
        fonts_page,
        look_page,
        presets_page,
        store_page,
        widgets_page,
    )


class GtkTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not _gtk_ok():
            raise unittest.SkipTest("GTK 4 / libadwaita not available")


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


def _dropdown_values(dropdown: Gtk.DropDown) -> list[str]:
    model = dropdown.get_model()
    return [model.get_string(index) for index in range(model.get_n_items())]


def _row_dropdown(row: Adw.ActionRow) -> Gtk.DropDown:
    for widget in _descendants(row):
        if isinstance(widget, Gtk.DropDown):
            return widget
    raise AssertionError(f"no dropdown on {row.get_title()}")


class GuiPagesTests(unittest.TestCase):
    def test_required_tabs_exist(self) -> None:
        ids = [pid for pid, _title, _blurb in PAGES]
        for needed in ("presets", "bar", "widgets", "fonts", "apps", "look", "store", "doctor"):
            self.assertIn(needed, ids)


class DoctorPageTests(GtkTestCase):
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


class PresetsUndoTests(GtkTestCase):
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
            patch(
                "hypraesthetic.undo.undo",
                return_value=SimpleNamespace(theme="sample", errors=[]),
            ),
            patch("hypraesthetic_gui.widgets._toast") as toast,
        ):
            button.emit("clicked")
        self.assertIn("sample", toast.call_args.args[1])

    def test_preset_click_clears_wallpaper_override(self) -> None:
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
                self.assertEqual(Prefs.load().get("wallpaper"), "")
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

    def test_preset_tiles_do_not_use_wallpaper_as_the_card(self) -> None:
        from gi.repository import GdkPixbuf

        from hypraesthetic.discover import desktop_preview_image, theme_preview_image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "theme"
            root.mkdir()
            wall = root / "wallpaper.png"
            pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 8, 8)
            pixbuf.fill(0x336699FF)
            pixbuf.savev(str(wall), "png", [], [])
            (root / "preview.png").write_bytes(wall.read_bytes())
            pkg = SimpleNamespace(
                name="sample",
                display_name="Sample Theme",
                description="A quiet desktop",
                root=root,
                wallpaper="wallpaper.png",
                preview="preview.png",
                colors={"waybar": {"primary": "#112233"}},
                palette={"base0D": "#445566"},
            )
            self.assertEqual(theme_preview_image(pkg), wall)
            self.assertIsNone(desktop_preview_image(pkg))
            with patch("hypraesthetic_gui.widgets.ThemeCatalog") as catalog:
                catalog.return_value.list_visible.return_value = [pkg]
                page = presets_page()
        pictures = [
            widget for widget in _descendants(page) if isinstance(widget, Gtk.Picture)
        ]
        self.assertFalse(any(picture.get_paintable() is not None for picture in pictures))
        labels = [
            widget.get_label()
            for widget in _descendants(page)
            if isinstance(widget, Gtk.Label)
        ]
        self.assertIn("Desktop screenshot not added yet", labels)
        self.assertIn("Sample Theme", labels)
        self.assertIn("A quiet desktop", labels)
        sized = [
            widget.get_size_request()
            for widget in _descendants(page)
        ]
        self.assertIn((420, 262), sized)


class FontsPageTests(GtkTestCase):
    def test_family_only_terminal_font_shows_size_11(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                prefs = Prefs.load()
                fonts = dict(prefs.get("fonts") or {})
                fonts["terminal"] = "Iosevka"
                prefs.set("fonts", fonts)
                prefs.save()
                page = fonts_page()
                shown = [
                    button.get_font_desc().to_string()
                    for button in _descendants(page)
                    if isinstance(button, Gtk.FontDialogButton) and button.get_font_desc() is not None
                ]
                self.assertIn("Iosevka 11", shown)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

    def test_save_fonts_rewrites_zero_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                Prefs.load().save()
                with patch("hypraesthetic_gui.widgets._apply", return_value=True):
                    page = fonts_page()
                    buttons = [
                        widget
                        for widget in _descendants(page)
                        if isinstance(widget, Gtk.FontDialogButton)
                    ]
                    buttons[0].set_font_desc(Pango.FontDescription.from_string("Cantarell 0"))
                    save = next(
                        button for button in _labeled_buttons(page) if button.get_label() == "Apply changes"
                    )
                    save.emit("clicked")
                self.assertEqual(Prefs.load().get("fonts.ui"), "Cantarell 11")
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

    def test_fonts_apply_is_disabled_until_a_font_changes(self) -> None:
        page = fonts_page()
        apply = next(b for b in _labeled_buttons(page) if b.get_label() == "Apply changes")
        self.assertFalse(apply.get_sensitive())
        self.assertIsInstance(apply.get_ancestor(Gtk.ActionBar) or apply.get_parent(), Gtk.Widget)

    def test_widgets_and_apps_use_apply_changes_not_save(self) -> None:
        for builder in (widgets_page, apps_page, fonts_page):
            labels = [b.get_label() for b in _labeled_buttons(builder())]
            self.assertIn("Apply changes", labels)
            self.assertNotIn("Save fonts", labels)
            self.assertNotIn("Save apps", labels)
            self.assertNotIn("Save widgets", labels)


STORE_EMPTY = (
    "Builtin presets are on the Presets page. Paste a git URL or type to search the index."
)
GTK_MISMATCH = "GTK and icons are picked independently of the preset palette."
PALETTE_TOAST = (
    "Install wallust to generate a palette; until then export copies the current preset colors."
)


def _page_marks(page: Gtk.Widget) -> list[str]:
    heading = next(
        widget
        for widget in _descendants(page)
        if isinstance(widget, Gtk.Label) and widget.has_css_class("title-1")
    )
    box = heading.get_parent()
    marks: list[str] = []

    def take(widget: Gtk.Widget) -> None:
        if isinstance(widget, (Gtk.Label, Gtk.Button)) and widget.get_label():
            marks.append(widget.get_label())
            return
        if isinstance(widget, Gtk.Box):
            nested = widget.get_first_child()
            while nested is not None:
                if isinstance(nested, (Gtk.Label, Gtk.Button)) and nested.get_label():
                    marks.append(nested.get_label())
                nested = nested.get_next_sibling()

    child = box.get_first_child()
    while child is not None:
        take(child)
        child = child.get_next_sibling()
    return marks


def _spin_by_title(root: Gtk.Widget, title: str) -> Gtk.SpinButton:
    for row in _rows(root):
        if row.get_title() != title:
            continue
        for widget in _descendants(row):
            if isinstance(widget, Gtk.SpinButton):
                return widget
    raise AssertionError(f"no spin for {title}")


class LookPageTests(GtkTestCase):
    def test_look_hero_filmstrip_and_one_apply(self) -> None:
        walls = [Path(f"/tmp/ha-look-walls/paper-{index:02d}.png") for index in range(8)]
        with patch("hypraesthetic_gui.widgets.list_wallpapers", return_value=walls):
            page = look_page()
        labels = [b.get_label() for b in _labeled_buttons(page)]
        self.assertEqual(labels.count("Apply changes"), 1)
        self.assertNotIn("Save look", labels)
        apply = next(b for b in _labeled_buttons(page) if b.get_label() == "Apply changes")
        self.assertFalse(apply.get_sensitive())
        marks = _page_marks(page)
        self.assertLess(marks.index("Wallpaper"), marks.index("GTK and icons"))
        self.assertLess(marks.index("GTK and icons"), marks.index("Hyprland"))
        self.assertIn("Browse wallpaper…", marks)
        panes = [w for w in _descendants(page) if isinstance(w, Gtk.ScrolledWindow)]
        film = next(
            p for p in panes
            if p.get_policy()[0] == Gtk.PolicyType.AUTOMATIC
            and p.get_policy()[1] == Gtk.PolicyType.NEVER
        )
        # Unset is -1 on this GTK. The old bug was a 280px cap.
        self.assertNotEqual(film.get_max_content_height(), 280)
        self.assertFalse(apply.get_ancestor(Gtk.ScrolledWindow) is film)

    def test_gtk_mismatch_hint_and_hypr_spins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                current = current_theme_file()
                current.parent.mkdir(parents=True, exist_ok=True)
                current.write_text("sky\n", encoding="utf-8")
                prefs = Prefs.load()
                prefs.set("gtk_theme", "Adwaita-Dark")
                prefs.save()
                with patch("hypraesthetic_gui.widgets.list_wallpapers", return_value=[]):
                    page = look_page()
                labels = [
                    widget.get_label()
                    for widget in _descendants(page)
                    if isinstance(widget, Gtk.Label)
                ]
                self.assertIn(GTK_MISMATCH, labels)
                hint = next(
                    widget
                    for widget in _descendants(page)
                    if isinstance(widget, Gtk.Label) and widget.get_label() == GTK_MISMATCH
                )
                self.assertTrue(hint.has_css_class("dim-label"))
                by_title = {row.get_title() for row in _rows(page)}
                self.assertIn("Cursor theme", by_title)
                self.assertIn("Visualizer edge", by_title)
                self.assertIn("Window layer", by_title)
                self.assertIn("Overlap reserved space", by_title)
                for title, value in (
                    ("Gaps in", 5),
                    ("Gaps out", 7),
                    ("Border", 1),
                    ("Rounding", 10),
                ):
                    self.assertEqual(int(_spin_by_title(page, title).get_value()), value)
                prefs.set("gtk_theme", "gtk-sky")
                prefs.save()
                with patch("hypraesthetic_gui.widgets.list_wallpapers", return_value=[]):
                    matched = look_page()
                matched_labels = [
                    widget.get_label()
                    for widget in _descendants(matched)
                    if isinstance(widget, Gtk.Label)
                ]
                self.assertNotIn(GTK_MISMATCH, matched_labels)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

    def test_save_look_persists_cursor_and_hypr_knobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                prefs = Prefs.load()
                prefs.set("gtk_theme", "Adwaita-Dark")
                prefs.set("icon_theme", "Papirus-Dark")
                prefs.save()
                with (
                    patch("hypraesthetic_gui.widgets.list_wallpapers", return_value=[]),
                    patch("hypraesthetic_gui.widgets.list_gtk_themes", return_value=["Adwaita-Dark"]),
                    patch(
                        "hypraesthetic_gui.widgets.list_icon_themes",
                        return_value=["Papirus-Dark"],
                    ),
                    patch(
                        "hypraesthetic_gui.widgets.list_cursor_themes",
                        return_value=["Bibata-Modern-Classic"],
                    ),
                    patch("hypraesthetic_gui.widgets._apply", return_value=True) as apply,
                ):
                    page = look_page()
                    _spin_by_title(page, "Gaps in").set_value(11)
                    apply_button = next(
                        button for button in _labeled_buttons(page) if button.get_label() == "Apply changes"
                    )
                    self.assertTrue(apply_button.get_sensitive())
                    _spin_by_title(page, "Gaps out").set_value(13)
                    _spin_by_title(page, "Border").set_value(2)
                    _spin_by_title(page, "Rounding").set_value(8)
                    cursor = _row_dropdown(
                        next(row for row in _rows(page) if row.get_title() == "Cursor theme")
                    )
                    cursor_values = _dropdown_values(cursor)
                    self.assertEqual(cursor_values[0], "")
                    self.assertIn("Bibata-Modern-Classic", cursor_values)
                    cursor.set_selected(cursor_values.index("Bibata-Modern-Classic"))
                    apply_button.emit("clicked")
                loaded = Prefs.load()
                self.assertEqual(loaded.get("cursor_theme"), "Bibata-Modern-Classic")
                self.assertEqual(loaded.get("hypr.gaps_in"), 11)
                self.assertEqual(loaded.get("hypr.gaps_out"), 13)
                self.assertEqual(loaded.get("hypr.border_size"), 2)
                self.assertEqual(loaded.get("hypr.rounding"), 8)
                self.assertEqual(loaded.get("gtk_theme"), "Adwaita-Dark")
                components = apply.call_args.kwargs["components"]
                self.assertIn("gtk", components)
                self.assertIn("hyprland", components)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

    def test_palette_button_hidden_without_wallust_or_matugen(self) -> None:
        with (
            patch("hypraesthetic_gui.widgets.list_wallpapers", return_value=[]),
            patch("hypraesthetic_gui.widgets.shutil.which", return_value=None),
        ):
            page = look_page()
        labels = [button.get_label() for button in _labeled_buttons(page)]
        self.assertNotIn("Generate palette from wallpaper", labels)

    def test_palette_button_runs_export_theme(self) -> None:
        calls: list[list[str]] = []

        def which(name: str) -> str | None:
            return "/usr/bin/wallust" if name == "wallust" else None

        with (
            patch("hypraesthetic_gui.widgets.list_wallpapers", return_value=[]),
            patch("hypraesthetic_gui.widgets.shutil.which", side_effect=which),
            patch("hypraesthetic_gui.widgets._toast") as toast,
            patch(
                "hypraesthetic_gui.widgets._palette_runner",
                side_effect=lambda cmd: calls.append(list(cmd)),
            ),
        ):
            page = look_page()
            button = next(
                item
                for item in _labeled_buttons(page)
                if item.get_label() == "Generate palette from wallpaper"
            )
            button.emit("clicked")
        self.assertEqual(calls[0][:2], ["hat", "export-theme"])
        self.assertEqual(toast.call_args.args[1], PALETTE_TOAST)


class StorePageTests(GtkTestCase):
    def test_first_paint_is_search_row_and_empty_copy(self) -> None:
        page = store_page()
        labels = [
            widget.get_label()
            for widget in _descendants(page)
            if isinstance(widget, Gtk.Label)
        ]
        self.assertIn(STORE_EMPTY, labels)
        self.assertTrue(any(isinstance(widget, Gtk.Entry) for widget in _descendants(page)))
        tiles = [
            widget
            for widget in _descendants(page)
            if isinstance(widget, Gtk.Button) and not widget.get_label()
        ]
        self.assertEqual(tiles, [])
        self.assertNotIn("Apply", [button.get_label() for button in _labeled_buttons(page)])

    def test_search_hits_use_apply_install_and_builtin_preview(self) -> None:
        builtin = StoreEntry(
            name="sky",
            display_name="Sky",
            description="Bright",
            author="HyprAesthetic",
            source="builtin",
        )
        remote = StoreEntry(
            name="rice",
            display_name="Rice",
            description="remote",
            author="",
            source="https://github.com/example/rice.git",
        )
        pkg = object()

        def search(query: str) -> list[StoreEntry]:
            if not query.strip():
                return []
            return [builtin, remote]

        with (
            patch("hypraesthetic_gui.widgets.ThemeStore") as store_cls,
            patch("hypraesthetic_gui.widgets.ThemeCatalog") as catalog_cls,
            patch("hypraesthetic_gui.widgets.theme_preview_image", return_value=None) as preview,
        ):
            store_cls.return_value.search.side_effect = search
            catalog_cls.return_value.get.return_value = pkg
            page = store_page()
            entry = next(widget for widget in _descendants(page) if isinstance(widget, Gtk.Entry))
            entry.set_text("sky")
            entry.emit("activate")
            labels = [button.get_label() for button in _labeled_buttons(page)]
            self.assertIn("Apply", labels)
            self.assertIn("Install", labels)
            catalog_cls.return_value.get.assert_called_with("sky")
            preview.assert_called_with(pkg)
            apply_button = next(
                button for button in _labeled_buttons(page) if button.get_label() == "Apply"
            )
            with patch("hypraesthetic_gui.widgets.ApplyEngine") as engine:
                apply_button.emit("clicked")
            engine.return_value.apply.assert_called_with("sky")
            entry.set_text("")
            entry.emit("activate")
        labels = [
            widget.get_label()
            for widget in _descendants(page)
            if isinstance(widget, Gtk.Label)
        ]
        self.assertIn(STORE_EMPTY, labels)
        self.assertNotIn("Apply", [button.get_label() for button in _labeled_buttons(page)])


class AppsPageTests(GtkTestCase):
    def test_apps_lists_binaries_on_path_and_names_super_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                prefs = Prefs.load()
                prefs.set("file_manager", "nautilus")
                prefs.set("terminal", "kitty")
                prefs.set("launcher", "rofi")
                prefs.set("browser", "firefox")
                prefs.save()
                installed = {
                    "nautilus",
                    "dolphin",
                    "kitty",
                    "ghostty",
                    "wofi",
                    "brave-browser",
                    "zen-browser",
                }

                def fake_which(name: str) -> str | None:
                    return f"/usr/bin/{name}" if name in installed else None

                with patch("shutil.which", side_effect=fake_which):
                    page = apps_page()
                blurbs = [
                    widget.get_label()
                    for widget in _descendants(page)
                    if isinstance(widget, Gtk.Label) and widget.has_css_class("dim-label")
                ]
                self.assertIn(
                    "Super+E file manager, Super+T terminal, Super+B browser.",
                    blurbs,
                )
                by_title = {row.get_title(): _dropdown_values(_row_dropdown(row)) for row in _rows(page)}
                self.assertEqual(by_title["File manager"], ["nautilus", "dolphin"])
                self.assertEqual(by_title["Terminal"], ["kitty", "ghostty"])
                self.assertEqual(by_title["Launcher"], ["rofi", "wofi"])
                self.assertEqual(by_title["Browser"], ["firefox", "brave-browser", "zen-browser"])
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home


def _header_side(widget: Gtk.Widget) -> str:
    node: Gtk.Widget | None = widget
    while node is not None:
        parent = node.get_parent()
        if parent is not None and type(parent).__name__ == "CenterBox":
            children: list[Gtk.Widget] = []
            child = parent.get_first_child()
            while child is not None:
                children.append(child)
                child = child.get_next_sibling()
            index = children.index(node)
            if index == 0:
                return "start"
            if index == len(children) - 1:
                return "end"
            return "center"
        node = parent
    raise AssertionError("widget is not packed in a header bar")


def _switch_by_title(root: Gtk.Widget, title: str) -> Gtk.Switch:
    for row in _rows(root):
        if row.get_title() != title:
            continue
        for widget in _descendants(row):
            if isinstance(widget, Gtk.Switch):
                return widget
    raise AssertionError(f"no switch for {title}")


class WidgetEditorTests(GtkTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = self.tmp.name
        current = current_theme_file()
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text("sample\n", encoding="utf-8")

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        self.tmp.cleanup()

    def _editor(self, widget_ids: list[str]) -> WidgetEditor:
        overlay = Adw.ToastOverlay()
        return WidgetEditor(None, widget_ids, overlay, lambda *_args: None)

    def test_axis_labels_sit_above_entries_and_save_is_not_on_close(self) -> None:
        editor = self._editor(["clock"])
        labels = []
        for widget in _descendants(editor):
            if not isinstance(widget, Gtk.Label) or widget.get_label() not in {"x", "y", "width", "height"}:
                continue
            parent: Gtk.Widget | None = widget
            inside_entry = False
            while parent is not None:
                if isinstance(parent, Gtk.Entry):
                    inside_entry = True
                    break
                parent = parent.get_parent()
            if not inside_entry:
                labels.append(widget)
        self.assertEqual([widget.get_label() for widget in labels], ["x", "y", "width", "height"])
        for widget in labels:
            self.assertTrue(widget.has_css_class("dim-label"))
        save = next(button for button in _labeled_buttons(editor) if button.get_label() == "Save layout")
        self.assertEqual(_header_side(save), "start")

    def test_save_clamps_y_onto_the_canvas(self) -> None:
        editor = self._editor(["matrix"])
        editor._entries["matrix"]["y"].set_text("-5%")
        editor._entries["matrix"]["height"].set_text("100%")
        editor._save()
        saved = Prefs.load().geometry_for("sample")["matrix"]
        y = geom_to_fraction(saved["y"], "y", editor._screen)
        height = geom_to_fraction(saved["height"], "y", editor._screen)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(y + height, 1)
        self.assertEqual(saved["y"], "0%")

        editor = self._editor(["clock"])
        editor._entries["clock"]["y"].set_text("90%")
        editor._entries["clock"]["height"].set_text("20%")
        editor._save()
        saved = Prefs.load().geometry_for("sample")["clock"]
        y = geom_to_fraction(saved["y"], "y", editor._screen)
        height = geom_to_fraction(saved["height"], "y", editor._screen)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(y + height, 1)
        self.assertEqual(saved["y"], "80%")

    def test_anchored_matrix_loads_on_the_right_and_stays_at_y_zero(self) -> None:
        editor = self._editor(["matrix", "clock"])
        matrix_x = geom_to_fraction(editor._raw["matrix"]["x"], "x", editor._screen)
        self.assertGreater(matrix_x, 0.9)
        self.assertEqual(editor._raw["matrix"]["y"], "0%")
        editor._drag = {"id": "matrix", "mode": "move", "start": list(editor._fracs["matrix"])}
        editor._on_update(None, 0, -400)
        self.assertEqual(editor._fracs["matrix"][1], 0.0)
        self.assertEqual(editor._entries["matrix"]["y"].get_text(), "0%")


class WidgetsPageTests(GtkTestCase):
    def test_save_widgets_writes_the_current_theme_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                current = current_theme_file()
                current.parent.mkdir(parents=True, exist_ok=True)
                current.write_text("sample\n", encoding="utf-8")
                prefs = Prefs.load()
                prefs.set_widgets_for("sample", ["clock"])
                prefs.set_widgets_for("other", ["matrix"])
                prefs.set("widgets", ["quote"])
                prefs.save()
                with patch("hypraesthetic_gui.widgets._apply", return_value=True) as apply:
                    page = widgets_page()
                    self.assertTrue(_switch_by_title(page, "Clock").get_active())
                    self.assertFalse(_switch_by_title(page, "Quote").get_active())
                    _switch_by_title(page, "Quote").set_active(True)
                    save = next(
                        button for button in _labeled_buttons(page) if button.get_label() == "Apply changes"
                    )
                    save.emit("clicked")
                loaded = Prefs.load()
                self.assertEqual(loaded.widgets_for("sample"), ["clock", "quote"])
                self.assertEqual(loaded.widgets_for("other"), ["matrix"])
                self.assertEqual(loaded.get("widgets"), ["clock", "quote"])
                apply.assert_called_once()
                self.assertEqual(apply.call_args.kwargs["components"], ["eww"])
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home


def _tile_title(button: Gtk.Button) -> str:
    for widget in _descendants(button):
        if isinstance(widget, Gtk.Label) and widget.has_css_class("ha-tile-title"):
            return widget.get_label() or ""
    return ""


def _tile_subtitle(button: Gtk.Button) -> str:
    for widget in _descendants(button):
        if isinstance(widget, Gtk.Label) and widget.has_css_class("ha-tile-sub"):
            return widget.get_label() or ""
    return ""


def _flow_children(flow: Gtk.FlowBox) -> list[Gtk.Widget]:
    children: list[Gtk.Widget] = []
    child = flow.get_first_child()
    while child is not None:
        children.append(child)
        child = child.get_next_sibling()
    return children


def _visible_flow_buttons(flow: Gtk.FlowBox) -> list[Gtk.Button]:
    buttons: list[Gtk.Button] = []
    for child in _flow_children(flow):
        if not child.get_child_visible():
            continue
        button = child.get_child()
        if isinstance(button, Gtk.Button):
            buttons.append(button)
    return buttons


class BarPageTests(GtkTestCase):
    def test_bar_page_has_no_imported_heading(self) -> None:
        page = bar_page()
        marks = _page_marks(page)
        self.assertNotIn("Imported (search to filter)", marks)
        self.assertNotIn("First-party", marks)
        self.assertIn("For this preset", marks)
        self.assertIn("Built-in styles", marks)
        self.assertIn("Type to browse extra Waybar layouts.", marks)
        titles = [
            widget.get_label()
            for widget in _descendants(page)
            if isinstance(widget, Gtk.Label) and widget.has_css_class("ha-tile-title")
        ]
        self.assertNotIn("v2.9e", titles)
        self.assertNotIn("v1.1", titles)

    def test_bar_page_bands_schematic_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                page = bar_page()
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home

        labels = [button.get_label() for button in _labeled_buttons(page)]
        self.assertNotIn("Apply changes", labels)
        hint = next(
            widget
            for widget in _descendants(page)
            if isinstance(widget, Gtk.Label)
            and widget.get_label() == "Type to browse extra Waybar layouts."
        )
        self.assertTrue(hint.has_css_class("dim-label"))
        heading = next(
            widget
            for widget in _descendants(page)
            if isinstance(widget, Gtk.Label) and widget.has_css_class("title-1")
        )
        kinds: list[str] = []
        child = heading.get_parent().get_first_child()
        while child is not None:
            if isinstance(child, Gtk.SearchEntry):
                kinds.append(child.get_placeholder_text() or "")
            elif isinstance(child, Gtk.Label) and child.get_label() in {
                "For this preset",
                "Built-in styles",
                "Type to browse extra Waybar layouts.",
            }:
                kinds.append(child.get_label())
            child = child.get_next_sibling()
        self.assertEqual(
            kinds,
            [
                "Search extra bar layouts",
                "For this preset",
                "Built-in styles",
                "Type to browse extra Waybar layouts.",
            ],
        )
        self.assertFalse(any(isinstance(widget, Gtk.Picture) for widget in _descendants(page)))

        flows = [widget for widget in _descendants(page) if isinstance(widget, Gtk.FlowBox)]
        self.assertGreaterEqual(len(flows), 3)
        preset = _visible_flow_buttons(flows[0])
        self.assertEqual(len(preset), 1)
        self.assertEqual(_tile_title(preset[0]), "Toji thin")
        self.assertEqual(_tile_subtitle(preset[0]), "Used by Toji")
        builtin = _visible_flow_buttons(flows[1])
        self.assertEqual(
            [_tile_title(button) for button in builtin],
            ["Hide the bar", "Capsule", "Compact", "Dock", "Night City"],
        )
        self.assertEqual(
            [_tile_subtitle(button) for button in builtin],
            [
                "No status bar",
                "Rounded island bar",
                "Workspaces, clock, and tray",
                "Centered workspaces with meters",
                "Flat modules with window title",
            ],
        )
        extra = flows[2]
        self.assertEqual(_visible_flow_buttons(extra), [])

        def schematic_of(button: Gtk.Button) -> Gtk.Widget:
            box = button.get_child()
            self.assertIsNotNone(box)
            drawn = box.get_first_child()
            self.assertIsNotNone(drawn)
            if isinstance(drawn, Gtk.ScrolledWindow):
                drawn = drawn.get_child()
                if isinstance(drawn, Gtk.Viewport):
                    drawn = drawn.get_first_child()
            width, height = drawn.get_size_request()
            self.assertEqual(height, 36)
            self.assertTrue(any(name.startswith("ha-swatch-") for name in drawn.get_css_classes()))
            return drawn

        for button in [preset[0], *builtin]:
            schematic_of(button)

        from hypraesthetic.bar_schematic import modules_for_bar

        text = (layouts_dir() / "bars" / "default" / "config.jsonc").read_text(encoding="utf-8")
        left, center, right = modules_for_bar(text)
        capsule = next(button for button in builtin if _tile_title(button) == "Capsule")
        drawn = schematic_of(capsule)
        groups: list[Gtk.Widget] = []
        group = drawn.get_first_child()
        while group is not None:
            groups.append(group)
            group = group.get_next_sibling()
        self.assertEqual(len(groups), 3)

        def pills(group: Gtk.Widget) -> list[str]:
            found: list[str] = []
            child = group.get_first_child()
            while child is not None:
                if isinstance(child, Gtk.Label):
                    found.append(child.get_label() or "")
                child = child.get_next_sibling()
            return found

        capsule_groups = (
            ["hyprland/workspaces", "custom/separator", "tray", "idle_inhibitor", "custom/separator2", "mpris"],
            ["custom/separator", "custom/clock", "custom/separator2"],
            [
                "custom/separator",
                "bluetooth",
                "custom/separator3",
                "backlight",
                "custom/separator4",
                "power-profiles-daemon",
                "custom/separator3",
                "pulseaudio",
                "custom/separator3",
                "cpu",
                "custom/separator3",
                "memory",
                "custom/separator4",
                "battery",
            ],
        )
        compact_groups = (
            ["hyprland/workspaces"],
            ["custom/clock"],
            ["pulseaudio", "battery", "tray"],
        )
        self.assertEqual((left, center, right), capsule_groups)

        def pill_names(group: Gtk.Widget) -> list[str]:
            found: list[str] = []
            child = group.get_first_child()
            while child is not None:
                if isinstance(child, Gtk.Label):
                    found.append(child.get_tooltip_text() or "")
                child = child.get_next_sibling()
            return found

        self.assertEqual(pills(groups[0]), [name.rsplit("/", 1)[-1] for name in capsule_groups[0]])
        self.assertEqual(pills(groups[1]), [name.rsplit("/", 1)[-1] for name in capsule_groups[1]])
        self.assertEqual(pills(groups[2]), [name.rsplit("/", 1)[-1] for name in capsule_groups[2]])
        self.assertEqual(pill_names(groups[0]), list(capsule_groups[0]))
        self.assertEqual(pill_names(groups[1]), list(capsule_groups[1]))
        self.assertEqual(pill_names(groups[2]), list(capsule_groups[2]))

        compact_tile = next(button for button in builtin if _tile_title(button) == "Compact")
        compact_drawn = schematic_of(compact_tile)
        compact_boxes: list[Gtk.Widget] = []
        compact_group = compact_drawn.get_first_child()
        while compact_group is not None:
            compact_boxes.append(compact_group)
            compact_group = compact_group.get_next_sibling()
        self.assertEqual(
            [pill_names(group) for group in compact_boxes],
            [list(names) for names in compact_groups],
        )

        search = next(widget for widget in _descendants(page) if isinstance(widget, Gtk.SearchEntry))
        search.set_text("v2.9e")
        search.emit("search-changed")
        shown = _visible_flow_buttons(extra)
        shown_titles = [_tile_title(button) for button in shown]
        self.assertIn("Capsule dock", shown_titles)
        self.assertNotIn("Top split", shown_titles)
        dock = next(button for button in shown if _tile_title(button) == "Capsule dock")
        self.assertEqual(_tile_subtitle(dock), "Centered workspaces with meters")
        search.set_text("v6.ab2")
        search.emit("search-changed")
        shown = _visible_flow_buttons(extra)
        self.assertTrue(any(_tile_title(button) == "Waybar layout" for button in shown))
        plain = next(button for button in shown if button.get_name().startswith("v6.ab2 "))
        self.assertEqual(_tile_title(plain), "Waybar layout")
        self.assertEqual(_tile_subtitle(plain), "v6.ab2")

    def test_bar_page_without_a_theme_still_paints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            old_root = os.environ.get("HYPRAESTHETIC_ROOT")
            os.environ["HOME"] = tmp
            os.environ["HYPRAESTHETIC_ROOT"] = tmp
            try:
                page = bar_page()
                self.assertIn("For this preset", _page_marks(page))
                flows = [widget for widget in _descendants(page) if isinstance(widget, Gtk.FlowBox)]
                preset = _visible_flow_buttons(flows[0])
                self.assertEqual(_tile_title(preset[0]), "Hide the bar")
                self.assertEqual(_tile_subtitle(preset[0]), "Used by toji")
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home
                if old_root is None:
                    os.environ.pop("HYPRAESTHETIC_ROOT", None)
                else:
                    os.environ["HYPRAESTHETIC_ROOT"] = old_root

    def test_bar_schematic_does_not_widen_the_page_past_the_window(self) -> None:
        page = bar_page()
        page_min, _page_natural, _min_baseline, _nat_baseline = page.measure(
            Gtk.Orientation.HORIZONTAL, -1
        )
        self.assertLessEqual(page_min, 1100)
        flows = [widget for widget in _descendants(page) if isinstance(widget, Gtk.FlowBox)]
        builtin_min, _builtin_natural, _, _ = flows[1].measure(Gtk.Orientation.HORIZONTAL, -1)
        self.assertLessEqual(builtin_min, 1100)
        for button in _visible_flow_buttons(flows[0]) + _visible_flow_buttons(flows[1]):
            holder = button.get_child().get_first_child()
            self.assertIsInstance(holder, Gtk.ScrolledWindow)
            self.assertFalse(holder.get_propagate_natural_width())
            horizontal, vertical = holder.get_policy()
            self.assertEqual(horizontal, Gtk.PolicyType.AUTOMATIC)
            self.assertEqual(vertical, Gtk.PolicyType.NEVER)
            self.assertLessEqual(holder.measure(Gtk.Orientation.HORIZONTAL, -1)[0], 1100)

    def test_bar_tile_click_applies_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                with patch("hypraesthetic_gui.widgets._apply", return_value=True) as apply:
                    page = bar_page()
                    flows = [widget for widget in _descendants(page) if isinstance(widget, Gtk.FlowBox)]
                    compact = next(
                        button
                        for button in _visible_flow_buttons(flows[1])
                        if _tile_title(button) == "Compact"
                    )
                    compact.emit("clicked")
                self.assertEqual(Prefs.load().get("bar"), "waybar")
                self.assertEqual(Prefs.load().get("bar_style"), "compact")
                apply.assert_called_once()
                self.assertEqual(apply.call_args.kwargs["components"], ["waybar"])
                self.assertNotIn("Apply changes", [button.get_label() for button in _labeled_buttons(page)])
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home


if __name__ == "__main__":
    unittest.main()
