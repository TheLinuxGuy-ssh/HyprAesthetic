from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def bind_dirty_apply(
    button: Gtk.Button,
    snapshot: dict,
    collect: Callable[[], dict],
) -> Callable[[], None]:
    button.set_label("Apply changes")
    button.set_sensitive(False)
    button.remove_css_class("suggested-action")
    button.set_tooltip_text("Applies the settings on this page.")

    def refresh(*_a: object) -> None:
        dirty = collect() != snapshot
        button.set_sensitive(dirty)
        if dirty:
            button.add_css_class("suggested-action")
        else:
            button.remove_css_class("suggested-action")

    refresh()
    return refresh
