"""One-shot Hyprland login startup."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from hypraesthetic.apply import ApplyEngine
from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.paths import current_theme_file
from hypraesthetic.prefs import Prefs


def session_start() -> int:
    cache = Path.home() / ".cache" / "HyprAesthetic"
    cache.mkdir(parents=True, exist_ok=True)
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "default")
    flag = cache / f"session-{signature}.flag"
    if flag.is_file():
        return 0
    theme = "a70"
    current = current_theme_file()
    if current.is_file():
        theme = current.read_text(encoding="utf-8").strip() or theme
    log = cache / "session-start.log"
    _log(log, f"Starting session for theme: {theme}")
    for _ in range(50):
        if subprocess.run(["hyprctl", "monitors"], capture_output=True).returncode == 0:
            break
        time.sleep(0.2)
    flag.touch()
    prefs = Prefs.load()
    engine = ApplyEngine(live=True)
    try:
        pkg = ThemeCatalog().get(theme)
    except KeyError:
        _log(log, f"theme not found: {theme}")
        return 0
    if prefs.get("widgets") and shutil_which("eww"):
        engine.apply(theme, components=["eww"])
        _log(log, "Started eww")
    engine._apply_wallpaper(pkg)
    if prefs.get("bar") == "waybar" and shutil_which("waybar") and not _running("waybar"):
        subprocess.Popen(["waybar"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _log(log, "Started waybar")
    if shutil_which("wl-paste") and shutil_which("cliphist") and not _running("cliphist"):
        subprocess.Popen(["wl-paste", "--watch", "cliphist", "store"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if "hyprwave" in (prefs.get("extras") or []) and shutil_which("hyprwave") and not _running("hyprwave"):
        subprocess.Popen(["hyprwave"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _log(log, "Session start complete")
    return 0


def shutil_which(cmd: str) -> str | None:
    import shutil

    return shutil.which(cmd)


def _running(name: str) -> bool:
    return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0


def _log(path: Path, message: str) -> None:
    from datetime import datetime

    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")
