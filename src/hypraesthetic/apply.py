"""Apply a theme package onto ~/.config without clobbering user overlays."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.discover import (
    font_family_only,
    resolve_wallpaper,
    widget_ids_from_prefs,
    widget_window,
)
from hypraesthetic.paths import current_theme_file, layouts_dir, templates_dir
from hypraesthetic.prefs import Prefs
from hypraesthetic.render import VAR_RE, render_file, render_string
from hypraesthetic.theme import ThemePackage
from hypraesthetic.waybar_config import sanitize_waybar_config
from hypraesthetic.waybar_css import set_bar_font, theme_waybar_css

MANAGED_HYPR_SKIP = {"custom.lua", "custom"}
LAYOUT_OWNED = frozenset({"waybar", "hypr", "rofi"})
# Shared widget chrome. Theme overlays may ship scripts/images, but a legacy
# eww.yuck (cyberpunk's bar-only file) must not replace layout windows.
EWW_LAYOUT_FILES = frozenset({"eww.yuck"})
WINDOW_RE = re.compile(r"\(defwindow\s+([A-Za-z0-9_-]+)")
Runner = Callable[..., Any]
WhichFn = Callable[[str], str | None]


GEOM_TOKEN_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:%|px)?$")


def _eww_token(value: str) -> str:
    text = value.strip().strip('"')
    if not text:
        return ""
    if not GEOM_TOKEN_RE.fullmatch(text):
        return ""
    if text.endswith("%"):
        return f'"{text}"'
    return text


@dataclass
class ApplyResult:
    theme: str
    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False


def prepare_dest(dest: Path | str) -> Path:
    """Make dest safe to overwrite. Old apply used symlinks into the theme repo."""
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        path.unlink()
    return path


def copy_file(src: Path | str, dest: Path | str) -> None:
    src_path = Path(src)
    dest_path = prepare_dest(dest)
    if dest_path.exists() and dest_path.resolve() == src_path.resolve():
        return
    shutil.copy2(src_path, dest_path)


def copy_tree(src: Path, dest: Path, skip: set[str] | None = None) -> None:
    if not src.exists():
        return
    skip = skip or set()
    dest.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        if src.name not in skip:
            copy_file(src, dest / src.name)
        return
    for item in src.iterdir():
        if item.name in skip:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True, copy_function=copy_file)
        else:
            copy_file(item, target)


class ApplyEngine:
    def __init__(
        self,
        repo_root: Path | None = None,
        live: bool = True,
        catalog: ThemeCatalog | None = None,
        runner: Runner | None = None,
        popen: Runner | None = None,
        which: WhichFn | None = None,
    ):
        self.repo_root = Path(repo_root) if repo_root else None
        self.live = live
        self._catalog = catalog
        self.runner = runner or subprocess.run
        self.popen = popen or subprocess.Popen
        self.which = which or shutil.which
        self._errors: list[str] = []

    @property
    def catalog(self) -> ThemeCatalog:
        if self._catalog is None:
            root = self.repo_root
            self._catalog = ThemeCatalog(
                official_root=(root / "themes") if root else None,
            )
        return self._catalog

    def layout_root(self, name: str = "default") -> Path:
        base = layouts_dir(self.repo_root)
        return base / name

    def templates(self) -> Path:
        return templates_dir(self.repo_root)

    def apply(
        self,
        name: str,
        dry_run: bool = False,
        restart: bool = False,
        components: list[str] | None = None,
    ) -> ApplyResult:
        pkg = self.catalog.get(name)
        result = ApplyResult(theme=name, dry_run=dry_run)
        self._errors = []
        if components is None:
            wanted = [cid for cid, enabled in pkg.components.items() if enabled]
        else:
            wanted = list(components)
        if dry_run:
            result.applied = wanted
            return result

        prefs = Prefs.load()
        prefs.adopt_legacy_geometry(name)
        if components is None:
            theme_bar = str(pkg.layout.get("bar_style") or "").strip()
            if theme_bar:
                prefs.set("bar_style", theme_bar)
        prefs.save()
        variables = pkg.flatten()
        for cid in pkg.components:
            if cid not in wanted or not pkg.enabled(cid):
                result.skipped.append(cid)
                continue
            handler = getattr(self, f"_apply_{cid}", None)
            if handler is None:
                result.skipped.append(cid)
                continue
            try:
                handler(pkg, prefs, variables, restart=restart)
            except OSError as exc:
                self._errors.append(f"{cid}: {exc}")
                continue
            result.applied.append(cid)

        if components is None:
            try:
                self._apply_wallpaper(pkg)
            except OSError as exc:
                self._errors.append(f"wallpaper: {exc}")
        current = current_theme_file()
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text(name + "\n", encoding="utf-8")
        if self.live:
            # Hypr reload drops layer-shell clients. Only reload the compositor
            # when Hyprland files changed; otherwise just restart the bar/widgets.
            reloaded = False
            if "hyprland" in result.applied:
                self._reload_hypr()
                reloaded = True
            bar_on = prefs.get("bar") != "none"
            if bar_on and ("waybar" in result.applied or reloaded):
                self._restart_process("waybar")
            if "eww" in result.applied or reloaded:
                self._open_eww_widgets(pkg, prefs)
        result.errors = list(self._errors)
        return result

    def reapply(self, components: list[str] | None = None) -> ApplyResult:
        path = current_theme_file()
        name = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
        if not name:
            names = self.catalog.names()
            if not names:
                raise ValueError("No theme is installed")
            name = names[0]
        return self.apply(name, components=components)

    def _config(self, *parts: str) -> Path:
        return Path.home() / ".config" / Path(*parts)

    def _merge_component(
        self,
        pkg: ThemePackage,
        component: str,
        dest: Path,
        skip: set[str] | None = None,
        overlay_skip: set[str] | None = None,
    ) -> None:
        layout = self.layout_root() / component
        if layout.exists():
            copy_tree(layout, dest, skip=skip)
        overlay = pkg.overlay_dir(component, layout_owned=component in LAYOUT_OWNED)
        if overlay is not None:
            merged_skip = set(skip or ())
            is_override = overlay.parent.name == "overrides"
            if overlay_skip and not is_override:
                merged_skip.update(overlay_skip)
            copy_tree(overlay, dest, skip=merged_skip or None)

    def _render_template(self, rel: str, dest: Path, variables: dict[str, str]) -> None:
        template = self.templates() / f"{rel}.template"
        if template.is_file():
            prepare_dest(dest)
            render_file(template, dest, variables)
            text = dest.read_text(encoding="utf-8") if dest.is_file() else ""
            leftover = VAR_RE.findall(text) if text else []
            if leftover:
                self._errors.append(f"unresolved templates in {rel}: {', '.join(leftover)}")

    def _apply_hyprland(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        dest = self._config("hypr")
        dest.mkdir(parents=True, exist_ok=True)
        custom_dest = dest / "custom.lua"
        existed = custom_dest.exists() or (dest / "custom").exists()
        self._merge_component(pkg, "hypr", dest, skip=MANAGED_HYPR_SKIP)
        autostart_src = self.templates() / "hypr" / "autostart.lua"
        if autostart_src.is_file():
            copy_file(autostart_src, dest / "autostart.lua")
        self._render_template("hypr/appearences.lua", dest / "appearences.lua", variables)
        self._render_template("hypr/colors.conf", dest / "colors.conf", variables)
        self._write_apps_overlay(dest, prefs)
        self._ensure_hypr_entry(dest)
        if not existed:
            layout_custom = self.layout_root() / "hypr" / "custom.lua"
            if layout_custom.is_file() and not custom_dest.exists():
                copy_file(layout_custom, custom_dest)

    def _ensure_hypr_entry(self, dest: Path) -> None:
        entry = dest / "hyprland.lua"
        text = entry.read_text(encoding="utf-8") if entry.is_file() else ""
        if 'require("hypraesthetic-apps")' not in text:
            text += '\npcall(require, "hypraesthetic-apps")\n'
        if 'require("custom")' not in text and "pcall(require, \"custom\")" not in text:
            text += 'pcall(require, "custom")\n'
        prepare_dest(entry).write_text(text, encoding="utf-8")

    def _write_apps_overlay(self, dest: Path, prefs: Prefs) -> None:
        terminal = prefs.get("terminal") or "kitty"
        file_manager = prefs.get("file_manager") or "nautilus"
        browser = prefs.get("browser") or "firefox"
        prepare_dest(dest / "hypraesthetic-apps.lua").write_text(
            "\n".join(
                [
                    "-- Managed by HyprAesthetic. Edit prefs or the Apps page instead.",
                    "---@module 'hl'",
                    'local mainMod = "SUPER"',
                    f'hl.bind(mainMod .. " + " .. "T", hl.dsp.exec_cmd("{terminal}"))',
                    f'hl.bind(mainMod .. " + " .. "E", hl.dsp.exec_cmd("{file_manager}"))',
                    f'hl.bind(mainMod .. " + " .. "F11", hl.dsp.exec_cmd("{browser}"))',
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def _bar_dir(self, prefs: Prefs, pkg: ThemePackage | None = None) -> Path | None:
        style = str(prefs.get("bar_style") or "").strip()
        if not style and pkg is not None:
            style = str(pkg.layout.get("bar_style") or "").strip()
        if not style:
            style = "default"
        path = layouts_dir(self.repo_root) / "bars" / style
        if (path / "config.jsonc").is_file():
            return path
        fallback = self.layout_root() / "waybar"
        return fallback if fallback.exists() else None

    def _apply_waybar(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        if prefs.get("bar") == "none":
            if self.live:
                self.runner(["pkill", "-x", "waybar"], check=False, capture_output=True)
            return
        if self.live:
            self.runner(["pkill", "-x", "waybar"], check=False, capture_output=True)
        dest = self._config("waybar")
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        bar_dir = self._bar_dir(prefs, pkg)
        if bar_dir is not None:
            copy_tree(bar_dir, dest)
            overlay = pkg.overlay_dir("waybar", layout_owned=True)
            if overlay is not None:
                copy_tree(overlay, dest)
        else:
            self._merge_component(pkg, "waybar", dest)
        self._render_template("waybar/colors.css", dest / "colors.css", variables)
        config = dest / "config.jsonc"
        if config.is_file():
            config.write_text(sanitize_waybar_config(config.read_text(encoding="utf-8")), encoding="utf-8")
        style = dest / "style.css"
        if style.is_file():
            style.write_text(theme_waybar_css(style.read_text(encoding="utf-8")), encoding="utf-8")
        self._apply_bar_font(dest, prefs)

    def _eww_source_yuck(self, pkg: ThemePackage) -> Path | None:
        overlay = pkg.overlay_dir("eww")
        if overlay is not None:
            yuck = overlay / "eww.yuck"
            if yuck.is_file() and WINDOW_RE.search(yuck.read_text(encoding="utf-8")):
                return yuck
        fallback = self.layout_root() / "eww" / "eww.yuck"
        return fallback if fallback.is_file() else None

    def _apply_eww(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        dest = self._config("eww")
        dest.mkdir(parents=True, exist_ok=True)
        self._merge_component(pkg, "eww", dest, overlay_skip=self._eww_overlay_skip(pkg))
        self._render_template("eww/eww.scss", dest / "eww.scss", variables)
        self._write_quotes(pkg, dest)
        source = self._eww_source_yuck(pkg)
        if source is not None:
            copy_file(source, dest / "eww.yuck")
        self._apply_widget_geometry(dest, prefs, pkg.name)
        self._write_open_folders(dest, prefs)

    def _eww_overlay_skip(self, pkg: ThemePackage) -> set[str]:
        overlay = pkg.overlay_dir("eww")
        if overlay is None:
            return set(EWW_LAYOUT_FILES)
        yuck = overlay / "eww.yuck"
        if yuck.is_file() and WINDOW_RE.search(yuck.read_text(encoding="utf-8")):
            return set()
        return set(EWW_LAYOUT_FILES)

    def _eww_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["GDK_BACKEND"] = "wayland"
        return env

    def _primary_screen(self) -> str:
        if not self.which("hyprctl"):
            return "0"
        result = self.runner(
            ["hyprctl", "monitors", "-j"],
            check=False,
            capture_output=True,
            text=True,
        )
        raw = getattr(result, "stdout", "") or ""
        try:
            monitors = json.loads(raw)
            focused = next((m for m in monitors if m.get("focused")), monitors[0])
            return str(focused.get("id", 0))
        except (ValueError, TypeError, IndexError, AttributeError):
            return "0"

    def _eww_ping(self) -> bool:
        result = self.runner(
            ["eww", "ping"],
            check=False,
            capture_output=True,
            env=self._eww_env(),
        )
        return getattr(result, "returncode", 1) == 0

    def _ensure_eww_daemon(self, *, restart: bool = False) -> bool:
        env = self._eww_env()
        if restart:
            self.runner(["eww", "kill"], check=False, capture_output=True, env=env)
            self.runner(["pkill", "-x", "eww"], check=False, capture_output=True)
            for _ in range(40):
                if not self._eww_ping():
                    break
                time.sleep(0.05)
        elif self._eww_ping():
            return True
        if not self.which("eww"):
            self._errors.append("eww not found")
            return False
        self.popen(
            ["eww", "daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        ready = False
        for _ in range(40):
            if self._eww_ping():
                ready = True
                break
            time.sleep(0.05)
        if not ready:
            self._errors.append("eww daemon did not start")
            return False
        if restart:
            self.runner(["eww", "reload"], check=False, capture_output=True, env=env)
        return True

    def _eww_windows(self) -> set[str]:
        yuck = self._config("eww") / "eww.yuck"
        if not yuck.is_file():
            return set()
        return set(WINDOW_RE.findall(yuck.read_text(encoding="utf-8")))

    def _open_eww_widgets(self, pkg: ThemePackage, prefs: Prefs) -> None:
        if not self.which("eww"):
            self._errors.append("eww not found")
            return
        widgets = [widget_window(item) for item in widget_ids_from_prefs(prefs.get("widgets") or pkg.widgets)]
        if prefs.get("dashboard"):
            for extra in ("background", "profile"):
                if extra not in widgets:
                    widgets.append(extra)
        if not widgets:
            return
        env = self._eww_env()
        if not self._ensure_eww_daemon(restart=True):
            return
        defined = self._eww_windows()
        screen = self._primary_screen()
        time.sleep(0.1)
        for name in widgets:
            if defined and name not in defined:
                continue
            result = self._eww_open(name, screen, env)
            if getattr(result, "returncode", 0) != 0:
                time.sleep(0.2)
                result = self._eww_open(name, screen, env)
            if getattr(result, "returncode", 0) != 0:
                err = (
                    (getattr(result, "stderr", "") or "").strip()
                    or (getattr(result, "stdout", "") or "").strip()
                    or "failed"
                )
                self._errors.append(f"eww open {name}: {err}")

    def _eww_open(self, name: str, screen: str, env: dict[str, str]):
        return self.runner(
            ["eww", "open", name, "--screen", screen],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def _spawn_detached(self, args: list[str]) -> None:
        env = os.environ.copy()
        env.setdefault("GDK_BACKEND", "wayland")
        self.popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )

    def _restart_process(self, name: str) -> None:
        # Hyprland lua configs reject `hyprctl dispatch exec NAME`.
        self.runner(["pkill", "-x", name], check=False, capture_output=True)
        if not self.which(name):
            self._errors.append(f"{name} not found")
            return
        self._spawn_detached([name])

    def _write_open_folders(self, dest: Path, prefs: Prefs) -> None:
        script = dest / "scripts" / "open_folders"
        if not script.is_file():
            return
        fm = prefs.get("file_manager") or "nautilus"
        text = script.read_text(encoding="utf-8")
        script.write_text(text.replace("thunar", fm).replace("nautilus", fm), encoding="utf-8")

    def _apply_hyprwave(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        extras = prefs.get("extras") or []
        if "hyprwave" not in extras:
            return
        dest = self._config("hyprwave")
        dest.mkdir(parents=True, exist_ok=True)
        for leftover in ("config.toml", "config.conf"):
            path = dest / leftover
            if path.is_file():
                path.unlink()
        overlay = pkg.overlay_dir("hyprwave")
        if overlay and (overlay / "config.toml").is_file():
            copy_file(overlay / "config.toml", dest / "config.toml")
        elif overlay and (overlay / "config.conf").is_file():
            copy_file(overlay / "config.conf", dest / "config.conf")
        else:
            self._render_template("hyprwave/config.toml", dest / "config.toml", variables)

    def _apply_rofi(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        dest = self._config("rofi")
        dest.mkdir(parents=True, exist_ok=True)
        self._merge_component(pkg, "rofi", dest)
        self._render_template("rofi/colors.rasi", dest / "colors" / "hypraesthetic.rasi", variables)
        self._render_template("rofi/wallpaper.rasi", dest / "wallpaper.rasi", variables)

    def _apply_kitty(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        dest = self._config("kitty")
        dest.mkdir(parents=True, exist_ok=True)
        rendered = self.templates() / "kitty" / "kitty.conf.template"
        parts: list[str] = []
        if rendered.is_file():
            parts.append(render_string(rendered.read_text(encoding="utf-8"), variables))
        extra = pkg.overlay_dir("kitty")
        extra_conf = extra / "kitty.conf" if extra else None
        if extra_conf and extra_conf.is_file():
            parts.append(extra_conf.read_text(encoding="utf-8"))
        text = "\n".join(parts) + "\n"
        family = font_family_only(str(prefs.get("fonts.terminal") or ""))
        if family:
            if re.search(r"^font_family\s+", text, re.M):
                text = re.sub(r"^font_family\s+.*$", f"font_family {family}", text, count=1, flags=re.M)
            else:
                text = f"font_family {family}\n" + text
        prepare_dest(dest / "kitty.conf").write_text(text, encoding="utf-8")

    def _apply_gtk(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        for ver in ("gtk-3.0", "gtk-4.0"):
            dest = self._config(ver)
            dest.mkdir(parents=True, exist_ok=True)
            src = None
            overlay = pkg.overlay_dir("gtk")
            if overlay and (overlay / ver / "settings.ini").is_file():
                src = overlay / ver / "settings.ini"
            else:
                layout = self.layout_root() / "gtk" / ver / "settings.ini"
                if layout.is_file():
                    src = layout
            if src:
                copy_file(src, dest / "settings.ini")
            self._write_gtk_settings(dest / "settings.ini", prefs)
        if self.live:
            self._apply_gsettings(prefs)

    def _apply_dunst(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        dest = self._config("dunst")
        dest.mkdir(parents=True, exist_ok=True)
        overlay = pkg.overlay_dir("dunst")
        if overlay and (overlay / "dunst.conf").is_file() and not (self.templates() / "dunst" / "dunst.conf.template").is_file():
            copy_file(overlay / "dunst.conf", dest / "dunst.conf")
        else:
            self._render_template("dunst/dunst.conf", dest / "dunst.conf", variables)
        if self.live and restart:
            self.runner(["pkill", "-x", "dunst"], check=False, capture_output=True)

    def _apply_nvim(
        self, pkg: ThemePackage, prefs: Prefs, variables: dict[str, str], restart: bool = False
    ) -> None:
        dest = self._config("nvim", "lua", "themes")
        dest.mkdir(parents=True, exist_ok=True)
        named = pkg.root / "nvim" / "lua" / "themes" / f"{pkg.name}.lua"
        if named.is_file():
            copy_file(named, dest / "current_theme.lua")
        else:
            self._render_template("nvim/current_theme.lua", dest / "current_theme.lua", variables)

    def _apply_wallpaper(self, pkg: ThemePackage) -> None:
        prefs = Prefs.load()
        path = resolve_wallpaper(
            pkg=pkg,
            override=str(prefs.get("wallpaper") or ""),
            live=False,
        )
        if path is None or not self.live:
            return
        tool = self.which("awww") or self.which("swww")
        if not tool:
            return
        self.runner([tool, "img", str(path), "--transition-type", "none"], check=False)

    def _apply_bar_font(self, dest: Path, prefs: Prefs) -> None:
        family = font_family_only(str(prefs.get("fonts.bar") or ""))
        style = dest / "style.css"
        if not family or not style.is_file():
            return
        text = style.read_text(encoding="utf-8")
        updated = set_bar_font(text, family)
        if updated != text:
            style.write_text(updated, encoding="utf-8")

    def _write_gtk_settings(self, dest: Path, prefs: Prefs) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = dest.read_text(encoding="utf-8") if dest.is_file() else "[Settings]\n"
        mapping = {
            "gtk-theme-name": prefs.get("gtk_theme"),
            "gtk-icon-theme-name": prefs.get("icon_theme"),
            "gtk-font-name": prefs.get("fonts.ui"),
        }
        for key, value in mapping.items():
            if not value:
                continue
            line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", text, re.M):
                text = re.sub(rf"^{re.escape(key)}=.*$", line, text, flags=re.M)
            else:
                if not text.endswith("\n"):
                    text += "\n"
                text += line + "\n"
        prepare_dest(dest).write_text(text, encoding="utf-8")

    def _apply_gsettings(self, prefs: Prefs) -> None:
        gset = self.which("gsettings")
        if not gset:
            return
        pairs = [
            ("gtk-theme", prefs.get("gtk_theme")),
            ("icon-theme", prefs.get("icon_theme")),
            ("font-name", prefs.get("fonts.ui")),
            ("monospace-font-name", prefs.get("fonts.terminal")),
        ]
        for key, value in pairs:
            if not value:
                continue
            self.runner(
                [gset, "set", "org.gnome.desktop.interface", key, str(value)],
                check=False,
                capture_output=True,
            )

    def _write_quotes(self, pkg: ThemePackage, dest: Path) -> None:
        lines = [item.strip() for item in pkg.quotes if str(item).strip()]
        prepare_dest(dest / "quotes").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _apply_widget_geometry(self, dest: Path, prefs: Prefs, theme: str = "") -> None:
        geom = prefs.geometry_for(theme)
        if not geom:
            return
        yuck = dest / "eww.yuck"
        if not yuck.is_file():
            return
        text = yuck.read_text(encoding="utf-8")
        for raw_name, values in geom.items():
            if not isinstance(values, dict):
                continue
            window = widget_window(str(raw_name))
            x = _eww_token(str(values.get("x") or ""))
            y = _eww_token(str(values.get("y") or ""))
            width = _eww_token(str(values.get("width") or ""))
            height = _eww_token(str(values.get("height") or ""))
            if not all((x, y, width, height)):
                continue
            pattern = (
                rf"(\(defwindow {re.escape(window)}\b[\s\S]*?:geometry \(geometry :x )"
                rf"\S+( :y )\S+( :width )\S+( :height )\S+(\))"
            )
            repl = rf"\g<1>{x}\g<2>{y}\g<3>{width}\g<4>{height}\g<5>"
            text, _count = re.subn(pattern, repl, text, count=1)
        yuck.write_text(text, encoding="utf-8")

    def _reload_hypr(self) -> None:
        if not self.which("hyprctl"):
            return
        result = self.runner(
            ["hyprctl", "reload"],
            check=False,
            capture_output=True,
            text=True,
        )
        if getattr(result, "returncode", 0) != 0:
            err = (
                (getattr(result, "stderr", "") or "").strip()
                or (getattr(result, "stdout", "") or "").strip()
                or "failed"
            )
            self._errors.append(f"hyprctl reload: {err}")
