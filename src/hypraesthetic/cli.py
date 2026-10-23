"""ha-theme / hat command line."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from hypraesthetic import __version__
from hypraesthetic.apply import ApplyEngine
from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.doctor import Doctor
from hypraesthetic.export_theme import export_theme
from hypraesthetic.install_theme import ThemeInstaller
from hypraesthetic.installer import Installer
from hypraesthetic.paths import current_theme_file, repo_root
from hypraesthetic.prefs import Prefs
from hypraesthetic.preset import prepare_preset_switch
from hypraesthetic.store import ThemeStore, user_store_index
from hypraesthetic.theme import ThemeError


USAGE = """\
Usage: ha-theme <command>

  list                         List installed themes
  current                      Show the active theme
  switch <theme> [--dry-run] [--restart]
  switch-<component> <theme> [--dry-run] [--restart]
  undo                         Restore the last full apply
  export-theme <name>          Copy the current look into your theme folder
  validate [theme]
  doctor
  backup | restore [timestamp]
  menu [--restart] | wallpaper-menu
  session-start
  install [--mode automatic|custom] [--theme NAME] [--yes]
  install-theme <path-or-git-url>
  store list | store search <query> | store install <name-or-url> | store refresh [url]
  prefs get [key] | prefs set <key> <value>
  gui
  version
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(USAGE.strip())
        return 0
    cmd = args[0]
    rest = args[1:]
    try:
        return dispatch(cmd, rest)
    except (ThemeError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def dispatch(cmd: str, rest: list[str]) -> int:
    if cmd == "list":
        return cmd_list()
    if cmd == "current":
        return cmd_current()
    if cmd == "switch":
        return cmd_switch(rest)
    if cmd == "undo":
        return cmd_undo()
    if cmd == "export-theme":
        return cmd_export_theme(rest)
    if cmd.startswith("switch-"):
        return cmd_switch_one(cmd.split("-", 1)[1], rest)
    if cmd == "validate":
        return cmd_validate(rest[0] if rest else None)
    if cmd == "doctor":
        return cmd_doctor()
    if cmd == "backup":
        return _bash("backup-configs.sh", ["backup"])
    if cmd == "restore":
        if not rest:
            return _bash("backup-configs.sh", ["list"])
        return _bash("backup-configs.sh", ["restore", *rest])
    if cmd == "menu":
        extra = ["--restart"] if rest[:1] == ["--restart"] else []
        return _bash("rofi-theme-menu.sh", extra)
    if cmd == "wallpaper-menu":
        return _bash("rofi-wallpaper-menu.sh", [])
    if cmd in {"validate-rofi"}:
        return _bash("validate-rofi-contrast.sh", rest)
    if cmd == "session-start":
        return cmd_session_start()
    if cmd == "install":
        return cmd_install(rest)
    if cmd in {"install-theme", "theme-install"}:
        if not rest:
            print("Usage: ha-theme install-theme <path-or-git-url>", file=sys.stderr)
            return 2
        pkg = ThemeInstaller().install(rest[0])
        print(f"Installed theme {pkg.display_name} ({pkg.name})")
        return 0
    if cmd == "store":
        return cmd_store(rest)
    if cmd == "prefs":
        return cmd_prefs(rest)
    if cmd == "gui":
        return cmd_gui()
    if cmd in {"version", "--version"}:
        print(__version__)
        return 0
    print(USAGE.strip(), file=sys.stderr)
    return 2


def cmd_list() -> int:
    for pkg in ThemeCatalog().list():
        print(f"{pkg.name}\t{pkg.display_name}")
    return 0


def cmd_current() -> int:
    path = current_theme_file()
    if path.is_file():
        print(f"Current theme: {path.read_text(encoding='utf-8').strip()}")
        return 0
    print("No theme set")
    return 0


def cmd_switch(rest: list[str]) -> int:
    if not rest:
        print("Usage: ha-theme switch <theme> [--dry-run] [--restart]", file=sys.stderr)
        return 2
    theme = rest[0]
    dry = "--dry-run" in rest
    restart = "--restart" in rest
    if not dry:
        prefs = prepare_preset_switch(Prefs.load())
        prefs.save()
    try:
        result = ApplyEngine(live=not dry).apply(theme, dry_run=dry, restart=restart)
    except KeyError:
        print(f"error: theme not found: {theme}", file=sys.stderr)
        return 1
    if dry:
        print("DRY RUN - would switch:")
        for item in result.applied:
            print(f"  - {item}")
        return 0
    for err in result.errors:
        print(f"error: {err}", file=sys.stderr)
    if result.errors:
        print(f"Theme switch finished with {len(result.errors)} error(s): {result.theme}")
        return 1
    print(f"Theme switch complete: {result.theme}")
    return 0


def cmd_export_theme(rest: list[str]) -> int:
    if not rest or not rest[0].strip():
        print("Usage: ha-theme export-theme <name>", file=sys.stderr)
        return 2
    dest = export_theme(rest[0])
    print(f"Exported {rest[0]} -> {dest}")
    return 0


def cmd_undo() -> int:
    from hypraesthetic import undo as undo_mod

    try:
        result = undo_mod.undo(ApplyEngine())
    except FileNotFoundError:
        print("Nothing to undo", file=sys.stderr)
        return 1
    for err in result.errors:
        print(f"error: {err}", file=sys.stderr)
    if result.errors:
        print(f"Theme switch finished with {len(result.errors)} error(s): {result.theme}")
        return 1
    print(f"Restored {result.theme}")
    return 0


def cmd_switch_one(component: str, rest: list[str]) -> int:
    theme = rest[0] if rest and not rest[0].startswith("-") else _current_or_die()
    dry = "--dry-run" in rest
    restart = "--restart" in rest
    try:
        result = ApplyEngine(live=not dry).apply(
            theme,
            dry_run=dry,
            restart=restart,
            components=[component],
        )
    except KeyError:
        print(f"error: theme not found: {theme}", file=sys.stderr)
        return 1
    if dry:
        print("DRY RUN - would switch:")
        print(f"  - {component}")
        return 0
    for err in result.errors:
        print(f"error: {err}", file=sys.stderr)
    if result.errors:
        print(f"Theme switch finished with {len(result.errors)} error(s): {result.theme}")
        return 1
    print(f"{component} configured")
    return 0


def cmd_validate(name: str | None) -> int:
    catalog = ThemeCatalog()
    targets = [catalog.get(name)] if name else catalog.list()
    failed = 0
    for pkg in targets:
        extra = pkg.validate()
        if extra:
            failed += 1
            print(f"FAIL {pkg.name}: {'; '.join(extra)}")
        else:
            print(f"OK   {pkg.name} ({pkg.display_name})")
    return 1 if failed else 0


def cmd_doctor() -> int:
    report = Doctor().run()
    for check in report.checks:
        flag = "OK  " if check.ok else ("MISS" if check.required else "opt ")
        print(f"{flag}  {check.friendly or check.id}: {check.detail}")
    if report.missing_required:
        print(f"{len(report.missing_required)} required check(s) failed")
        return 1
    print("Doctor complete")
    return 0


def cmd_install(rest: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ha-theme install")
    parser.add_argument("--mode", choices=("automatic", "custom"), default=None)
    parser.add_argument("--theme", default=None)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--preset", default=None)
    ns = parser.parse_args(rest)
    mode = ns.mode or _ask_mode()
    selection = None
    if ns.preset:
        selection = Prefs.load(Path(ns.preset)).data
        mode = selection.get("mode", "custom")
    elif mode == "custom":
        selection = _ask_selection()
    theme = ns.theme or _ask_theme()
    installer = Installer(
        assume_yes=ns.yes or mode == "automatic",
        root_assume=ns.yes,
        aur_assume=ns.yes or not sys.stdin.isatty(),
        apply_fn=lambda name: ApplyEngine().apply(name),
        backup_fn=lambda: _bash("backup-configs.sh", ["backup"]),
    )
    if not installer.allow_root():
        print("Root install declined. Re-run as your user.")
        return 1
    try:
        result = installer.run(mode=mode, theme=theme, selection=selection)
    except PermissionError as err:
        if str(err) != "root install declined":
            raise
        print("Root install declined. Re-run as your user.")
        return 1
    if result.packages_skipped:
        print("Packages were skipped:")
        for pkg in result.packages_skipped:
            print(f"  - {pkg}")
        print(
            f"Install incomplete ({result.mode}, theme={result.theme}). "
            "Required packages were not installed."
        )
        print("Re-run with --yes to install packages, or install them yourself.")
        return 1
    print(f"Installation complete ({result.mode}, theme={result.theme})")
    print("Log out and select Hyprland from your display manager if this is a first install.")
    return 0


def cmd_store(rest: list[str]) -> int:
    if not rest or rest[0] in {"list", "ls"}:
        store = ThemeStore()
        for entry in store.list():
            kind = "remote" if entry.is_remote else "builtin"
            print(f"{entry.name}\t{entry.display_name}\t{kind}")
        return 0
    if rest[0] == "search":
        query = " ".join(rest[1:]).strip()
        store = ThemeStore()
        hits = store.search(query)
        if not hits:
            print(f"No store matches for {query!r}")
            return 1
        for entry in hits:
            kind = "remote" if entry.is_remote else "builtin"
            print(f"{entry.name}\t{entry.display_name}\t{kind}\t{entry.source}")
        return 0
    if rest[0] == "install":
        if len(rest) < 2:
            print("Usage: ha-theme store install <name-or-url>", file=sys.stderr)
            return 2
        store = ThemeStore()
        entry = store.resolve(rest[1])
        if entry.is_remote:
            pkg = ThemeInstaller().install(entry.source)
            print(f"Installed {pkg.display_name}")
            return 0
        ApplyEngine().apply(entry.name)
        print(f"Applied {entry.display_name}")
        return 0
    if rest[0] == "refresh":
        url = rest[1] if len(rest) > 1 else Prefs.load().get("store_url")
        if not url:
            print("No store URL configured (prefs.store_url)", file=sys.stderr)
            return 2
        dest = user_store_index()
        ThemeStore().refresh(url, dest)
        print(f"Refreshed store index -> {dest}")
        return 0
    print("Usage: ha-theme store {list|search|install|refresh}", file=sys.stderr)
    return 2


def cmd_prefs(rest: list[str]) -> int:
    prefs = Prefs.load()
    if not rest or rest[0] == "get":
        key = rest[1] if len(rest) > 1 else None
        if key:
            value = prefs.get(key)
            print("unset" if value is None else value)
        else:
            for key, value in sorted(prefs.data.items()):
                print(f"{key} = {value}")
        return 0
    if rest[0] == "set" and len(rest) >= 3:
        value: object = rest[2]
        if value in {"true", "false"}:
            value = value == "true"
        prefs.set(rest[1], value)
        prefs.save()
        return 0
    print("Usage: ha-theme prefs get [key] | prefs set <key> <value>", file=sys.stderr)
    return 2


def cmd_gui() -> int:
    try:
        from hypraesthetic_gui.main import run
    except ImportError as exc:
        print(
            "GTK4/libadwaita GUI is unavailable. Install python3-gobject, gtk4, and libadwaita.\n"
            f"({exc})",
            file=sys.stderr,
        )
        return 1
    return run()


def cmd_session_start() -> int:
    from hypraesthetic.session import session_start

    return session_start()


def _current_or_die() -> str:
    path = current_theme_file()
    if path.is_file():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    raise ValueError("No theme set (run ha-theme switch <theme> first)")


def _bash(script: str, args: list[str]) -> int:
    path = repo_root() / "scripts" / script
    result = subprocess.run([str(path), *args], check=False)
    return result.returncode


def _ask_mode() -> str:
    if not sys.stdin.isatty():
        return "automatic"
    print("Install mode:")
    print("  1) Automatic  — Hyprland, Waybar, widgets, Kitty, Nautilus, our fonts")
    print("  2) Custom     — pick bar, widgets, file manager, terminal")
    choice = input("Select [1-2]: ").strip() or "1"
    return "custom" if choice == "2" else "automatic"


def _ask_theme() -> str:
    names = ThemeCatalog().names()
    if not names:
        return "toji"
    if not sys.stdin.isatty():
        return names[0]
    for i, name in enumerate(names, 1):
        print(f"  {i}) {name}")
    raw = input(f"Select theme [1-{len(names)}]: ").strip() or "1"
    try:
        return names[int(raw) - 1]
    except (ValueError, IndexError):
        return names[0]


def _ask_selection() -> dict:
    def pick(label: str, options: list[str], default: str) -> str:
        print(f"{label}: " + ", ".join(options) + f" [{default}]")
        if not sys.stdin.isatty():
            return default
        value = input("> ").strip() or default
        return value if value in options else default

    widgets_on = pick("Desktop widgets (eww)", ["yes", "no"], "yes") == "yes"
    return {
        "bar": pick("Status bar", ["waybar", "none"], "waybar"),
        "file_manager": pick("File manager", ["nautilus", "thunar", "nemo"], "nautilus"),
        "terminal": pick("Terminal", ["kitty", "alacritty", "foot"], "kitty"),
        "launcher": pick("Launcher", ["rofi", "hyprlauncher"], "rofi"),
        "notifications": "dunst",
        "widgets": ["clock", "system", "matrix", "wakatime", "toji"] if widgets_on else [],
        "extras": ["wallpaper", "gtk", "gui", "neovim"] + (["eww"] if widgets_on else []),
    }
