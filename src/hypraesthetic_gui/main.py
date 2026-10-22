"""GTK application entry."""

from __future__ import annotations

import sys


def run(argv: list[str] | None = None) -> int:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw

    from hypraesthetic_gui.window import HaWindow

    app = Adw.Application(application_id="dev.hypraesthetic.ControlCenter")

    def on_activate(application: Adw.Application) -> None:
        win = HaWindow(application=application)
        win.present()

    app.connect("activate", on_activate)
    # GApplication treats extra argv entries as files to open. `ha-theme gui`
    # leaves "gui" on sys.argv, which would exit with "can not open files".
    gtk_argv = [sys.argv[0]] if argv is None else (argv[:1] or [sys.argv[0]])
    return app.run(gtk_argv)
