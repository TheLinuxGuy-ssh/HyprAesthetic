"""Main control-center window."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from hypraesthetic_gui import widgets as pages
from hypraesthetic_gui.pages import PAGES


class HaWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application):
        super().__init__(application=application, title="HyprAesthetic")
        self.set_default_size(1100, 720)
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        sidebar = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["navigation-sidebar"])
        builders = {
            "presets": pages.presets_page,
            "bar": pages.bar_page,
            "widgets": pages.widgets_page,
            "fonts": pages.fonts_page,
            "apps": pages.apps_page,
            "look": pages.look_page,
            "store": pages.store_page,
            "doctor": pages.doctor_page,
        }
        for pid, title, subtitle in PAGES:
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            sidebar.append(row)
            self._stack.add_named(builders[pid](), pid)

        split = Adw.NavigationSplitView()
        side_page = Adw.NavigationPage(title="HyprAesthetic")
        side_toolbar = Adw.ToolbarView()
        side_toolbar.add_top_bar(Adw.HeaderBar())
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(sidebar)
        side_toolbar.set_content(scrolled)
        side_page.set_child(side_toolbar)

        content_page = Adw.NavigationPage(title="Presets")
        content_toolbar = Adw.ToolbarView()
        content_toolbar.add_top_bar(Adw.HeaderBar())
        content_toolbar.set_content(self._stack)
        content_page.set_child(content_toolbar)
        self._content_page = content_page

        split.set_sidebar(side_page)
        split.set_content(content_page)
        self.set_content(split)

        sidebar.connect("row-selected", self._on_select)
        sidebar.select_row(sidebar.get_row_at_index(0))

    def _on_select(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        index = row.get_index()
        pid, title, _subtitle = PAGES[index]
        self._stack.set_visible_child_name(pid)
        self._content_page.set_title(title)
