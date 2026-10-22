#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from hypraesthetic.apply import ApplyEngine
from hypraesthetic.prefs import Prefs
from tests.test_theme import V2_TOML


class ApplyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        self.repo = Path(self.tmp.name) / "repo"
        theme = self.repo / "themes" / "sample"
        theme.mkdir(parents=True)
        (theme / "theme.toml").write_text(V2_TOML.lstrip(), encoding="utf-8")
        layout = self.repo / "layouts" / "default"
        (layout / "waybar").mkdir(parents=True)
        (layout / "waybar" / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (layout / "eww").mkdir(parents=True)
        (layout / "eww" / "eww.yuck").write_text("(defwindow clock [])\n", encoding="utf-8")
        (layout / "hypr").mkdir(parents=True)
        (layout / "hypr" / "hyprland.lua").write_text('require("appearences")\n', encoding="utf-8")
        (layout / "hypr" / "custom.lua").write_text("-- user overlay\n", encoding="utf-8")
        templates = self.repo / "themes" / "_template"
        (templates / "waybar").mkdir(parents=True)
        (templates / "waybar" / "colors.css.template").write_text(
            "@define-color background {{colors.waybar.background}};\n",
            encoding="utf-8",
        )
        (templates / "eww").mkdir(parents=True)
        (templates / "eww" / "eww.scss.template").write_text(
            "$background: {{colors.eww.background}};\n", encoding="utf-8"
        )
        (templates / "hypr").mkdir(parents=True)
        (templates / "hypr" / "appearences.lua.template").write_text(
            'active_border = "{{colors.hyprland.border_active}}"\n', encoding="utf-8"
        )
        (templates / "hypr" / "autostart.lua").write_text("-- autostart\n", encoding="utf-8")
        self.engine = ApplyEngine(repo_root=self.repo, live=False)

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        self.tmp.cleanup()

    def test_skips_disabled_components(self) -> None:
        result = self.engine.apply("sample")
        self.assertNotIn("waybar", result.applied)
        self.assertFalse((self.home / ".config" / "waybar").exists())
        self.assertIn("eww", result.applied)
        self.assertTrue((self.home / ".config" / "eww" / "eww.yuck").exists())

    def test_renders_palette_into_eww_scss(self) -> None:
        self.engine.apply("sample")
        scss = (self.home / ".config" / "eww" / "eww.scss").read_text(encoding="utf-8")
        self.assertIn("#0d0d0d", scss)

    def test_does_not_overwrite_existing_hypr_custom(self) -> None:
        custom = self.home / ".config" / "hypr" / "custom.lua"
        custom.parent.mkdir(parents=True)
        custom.write_text("-- mine\n", encoding="utf-8")
        self.engine.apply("sample")
        self.assertEqual(custom.read_text(encoding="utf-8"), "-- mine\n")

    def test_seeds_custom_overlay_on_first_apply(self) -> None:
        self.engine.apply("sample")
        custom = self.home / ".config" / "hypr" / "custom.lua"
        self.assertTrue(custom.is_file())
        self.assertIn("user overlay", custom.read_text(encoding="utf-8"))

    def test_theme_override_wins_over_layout(self) -> None:
        override = self.repo / "themes" / "sample" / "overrides" / "eww"
        override.mkdir(parents=True)
        (override / "eww.yuck").write_text("(defwindow matrix [])\n", encoding="utf-8")
        self.engine.apply("sample")
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn("matrix", yuck)

    def test_dry_run_lists_without_writing(self) -> None:
        result = self.engine.apply("sample", dry_run=True)
        self.assertTrue(result.dry_run)
        self.assertFalse((self.home / ".config" / "eww").exists())

    def test_writes_apps_overlay_from_prefs(self) -> None:
        prefs = Prefs.load()
        prefs.set("file_manager", "thunar")
        prefs.set("terminal", "foot")
        prefs.save()
        self.engine.apply("sample")
        apps = (self.home / ".config" / "hypr" / "hypraesthetic-apps.lua").read_text(
            encoding="utf-8"
        )
        self.assertIn("thunar", apps)
        self.assertIn("foot", apps)

    def test_layout_owned_waybar_ignores_theme_copy(self) -> None:
        enabled = self.repo / "themes" / "barred"
        enabled.mkdir(parents=True)
        (enabled / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "barred"').replace(
                "waybar = false", "waybar = true"
            ),
            encoding="utf-8",
        )
        (enabled / "waybar").mkdir()
        (enabled / "waybar" / "config.jsonc").write_text("FROM_THEME\n", encoding="utf-8")
        (self.repo / "layouts" / "default" / "waybar" / "config.jsonc").write_text(
            "FROM_LAYOUT\n", encoding="utf-8"
        )
        engine = ApplyEngine(repo_root=self.repo, live=False)
        engine.apply("barred")
        deployed = (self.home / ".config" / "waybar" / "config.jsonc").read_text(
            encoding="utf-8"
        )
        self.assertEqual(deployed, "FROM_LAYOUT\n")
        self.assertNotIn("FROM_THEME", deployed)

    def test_live_apply_starts_waybar_and_opens_eww_on_a_screen(self) -> None:
        enabled = self.repo / "themes" / "barred"
        enabled.mkdir(parents=True)
        (enabled / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "barred"').replace(
                "waybar = false", "waybar = true"
            ),
            encoding="utf-8",
        )
        calls: list[list[str]] = []
        ping_ok = {"value": True}

        def runner(cmd, **kwargs):
            calls.append([str(part) for part in cmd])
            name = [str(part) for part in cmd]

            class Result:
                returncode = 0
                stdout = '[{"id": 0, "focused": true}]'
                stderr = ""

            if name[:2] == ["eww", "kill"] or name[:3] == ["pkill", "-x", "eww"]:
                ping_ok["value"] = False
            if name[:2] == ["eww", "ping"]:
                Result.returncode = 0 if ping_ok["value"] else 1
            return Result()

        def popen(cmd, **kwargs):
            calls.append([str(part) for part in cmd])
            if [str(part) for part in cmd][:2] == ["eww", "daemon"]:
                ping_ok["value"] = True

            class Proc:
                pid = 1

            return Proc()

        engine = ApplyEngine(
            repo_root=self.repo,
            live=True,
            runner=runner,
            popen=popen,
            which=lambda name: f"/usr/bin/{name}",
        )
        result = engine.apply("barred")
        flat = [" ".join(cmd) for cmd in calls]
        self.assertEqual(result.errors, [])
        self.assertIn(["waybar"], calls)
        self.assertFalse(any(cmd[:3] == ["hyprctl", "dispatch", "exec"] for cmd in calls))
        self.assertTrue(
            any(line.startswith("eww open clock") and "--screen" in line for line in flat)
        )
        self.assertFalse(any("eww open system" in line for line in flat))

    def test_live_eww_reloads_after_kill_before_open(self) -> None:
        enabled = self.repo / "themes" / "barred"
        enabled.mkdir(parents=True)
        (enabled / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "barred"').replace(
                "waybar = false", "waybar = true"
            ),
            encoding="utf-8",
        )
        calls: list[list[str]] = []
        ping_ok = {"value": True}

        def runner(cmd, **kwargs):
            calls.append([str(part) for part in cmd])
            name = [str(part) for part in cmd]

            class Result:
                returncode = 0
                stdout = '[{"id": 0, "focused": true}]'
                stderr = ""

            if name[:2] == ["eww", "kill"] or name[:3] == ["pkill", "-x", "eww"]:
                ping_ok["value"] = False
            if name[:2] == ["eww", "ping"]:
                Result.returncode = 0 if ping_ok["value"] else 1
            return Result()

        def popen(cmd, **kwargs):
            calls.append([str(part) for part in cmd])
            if [str(part) for part in cmd][:2] == ["eww", "daemon"]:
                ping_ok["value"] = True

            class Proc:
                pid = 1

            return Proc()

        engine = ApplyEngine(
            repo_root=self.repo,
            live=True,
            runner=runner,
            popen=popen,
            which=lambda name: f"/usr/bin/{name}",
        )
        result = engine.apply("barred", components=["eww"])
        self.assertEqual(result.errors, [])
        flat = [" ".join(cmd) for cmd in calls]
        kill_at = next(i for i, line in enumerate(flat) if line.startswith("eww kill") or line.startswith("pkill -x eww"))
        reload_at = next(i for i, line in enumerate(flat) if line.startswith("eww reload"))
        open_at = next(i for i, line in enumerate(flat) if line.startswith("eww open clock"))
        self.assertLess(kill_at, reload_at)
        self.assertLess(reload_at, open_at)

    def test_replaces_symlink_dest_without_same_file_error(self) -> None:
        gtk_src = self.repo / "themes" / "sample" / "gtk" / "gtk-3.0"
        gtk_src.mkdir(parents=True)
        ini = gtk_src / "settings.ini"
        ini.write_text("gtk-theme-name=Sample\n", encoding="utf-8")
        gtk_dest = self.home / ".config" / "gtk-3.0"
        gtk_dest.mkdir(parents=True)
        (gtk_dest / "settings.ini").symlink_to(ini)

        nvim_src = self.repo / "themes" / "sample" / "nvim" / "lua" / "themes"
        nvim_src.mkdir(parents=True)
        lua = nvim_src / "sample.lua"
        lua.write_text("-- sample\n", encoding="utf-8")
        nvim_dest = self.home / ".config" / "nvim" / "lua" / "themes"
        nvim_dest.mkdir(parents=True)
        (nvim_dest / "current_theme.lua").symlink_to(lua)

        dunst_src = self.repo / "themes" / "sample" / "dunst"
        dunst_src.mkdir()
        original = dunst_src / "dunst.conf"
        original.write_text("ORIGINAL\n", encoding="utf-8")
        dunst_dest = self.home / ".config" / "dunst"
        dunst_dest.mkdir(parents=True)
        (dunst_dest / "dunst.conf").symlink_to(original)
        (self.repo / "themes" / "_template" / "dunst").mkdir(parents=True, exist_ok=True)
        (self.repo / "themes" / "_template" / "dunst" / "dunst.conf.template").write_text(
            "bg={{colors.waybar.background}}\n", encoding="utf-8"
        )

        result = self.engine.apply("sample")
        self.assertEqual(result.errors, [])
        gtk = gtk_dest / "settings.ini"
        self.assertTrue(gtk.is_file())
        self.assertFalse(gtk.is_symlink())
        nvim = nvim_dest / "current_theme.lua"
        self.assertTrue(nvim.is_file())
        self.assertFalse(nvim.is_symlink())
        self.assertEqual(original.read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertFalse((dunst_dest / "dunst.conf").is_symlink())
        self.assertIn("#0d0d0d", (dunst_dest / "dunst.conf").read_text(encoding="utf-8"))

    def test_bar_style_layout_is_copied(self) -> None:
        enabled = self.repo / "themes" / "barred"
        enabled.mkdir(parents=True)
        (enabled / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "barred"').replace(
                "waybar = false", "waybar = true"
            ),
            encoding="utf-8",
        )
        compact = self.repo / "layouts" / "bars" / "compact"
        compact.mkdir(parents=True)
        (compact / "config.jsonc").write_text('{"id":"compact"}\n', encoding="utf-8")
        prefs = Prefs.load()
        prefs.set("bar_style", "compact")
        prefs.save()
        ApplyEngine(repo_root=self.repo, live=False).apply("barred")
        deployed = (self.home / ".config" / "waybar" / "config.jsonc").read_text(encoding="utf-8")
        self.assertIn("compact", deployed)

    def test_waybar_style_accents_follow_primary(self) -> None:
        enabled = self.repo / "themes" / "barred"
        enabled.mkdir(parents=True)
        (enabled / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "barred"').replace(
                "waybar = false", "waybar = true"
            ),
            encoding="utf-8",
        )
        bar = self.repo / "layouts" / "bars" / "default"
        bar.mkdir(parents=True)
        (bar / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (bar / "style.css").write_text(
            '* { font-family: \'CaskaydiaMono Nerd Font Propo\'; }\n'
            '#workspaces button.active { background-color: #fabd2f; color: #282828; }\n',
            encoding="utf-8",
        )
        prefs = Prefs.load()
        prefs.set("bar_style", "default")
        prefs.save()
        ApplyEngine(repo_root=self.repo, live=False).apply("barred")
        css = (self.home / ".config" / "waybar" / "style.css").read_text(encoding="utf-8")
        self.assertIn("background-color: @primary", css)
        self.assertIn("@import \"colors.css\"", css)
        self.assertIn('font-family: "JetBrainsMono Nerd Font"', css)
        self.assertNotIn("CaskaydiaMono", css)

    def test_theme_bar_style_is_used_on_full_apply(self) -> None:
        enabled = self.repo / "themes" / "barred"
        enabled.mkdir(parents=True)
        body = V2_TOML.replace('name = "sample"', 'name = "barred"').replace(
            "waybar = false", "waybar = true"
        ).replace('bar = "waybar"', 'bar = "waybar"\nbar_style = "compact"')
        (enabled / "theme.toml").write_text(body, encoding="utf-8")
        compact = self.repo / "layouts" / "bars" / "compact"
        compact.mkdir(parents=True)
        (compact / "config.jsonc").write_text('{"id":"theme-compact"}\n', encoding="utf-8")
        ApplyEngine(repo_root=self.repo, live=False).apply("barred")
        deployed = (self.home / ".config" / "waybar" / "config.jsonc").read_text(encoding="utf-8")
        self.assertIn("theme-compact", deployed)

    def test_writes_quotes_and_honors_widget_geometry(self) -> None:
        theme = self.repo / "themes" / "sample"
        text = (theme / "theme.toml").read_text(encoding="utf-8")
        (theme / "theme.toml").write_text(text + '\nquotes = ["Stay hungry."]\n', encoding="utf-8")
        (self.repo / "layouts" / "default" / "eww" / "eww.yuck").write_text(
            '(defwindow toji :geometry (geometry :x "1%" :y "1%" :width 480 :height 50) (toji))\n',
            encoding="utf-8",
        )
        prefs = Prefs.load()
        prefs.set("widget_geometry", {"quote": {"x": '"40%"', "y": '"70%"', "width": "480", "height": "50"}})
        prefs.save()
        self.engine.apply("sample")
        quotes = (self.home / ".config" / "eww" / "quotes").read_text(encoding="utf-8")
        self.assertIn("Stay hungry.", quotes)
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "40%"', yuck)

    def test_widget_geometry_stays_on_its_theme(self) -> None:
        enabled = self.repo / "themes" / "other"
        enabled.mkdir(parents=True)
        (enabled / "theme.toml").write_text(
            V2_TOML.replace('name = "sample"', 'name = "other"'),
            encoding="utf-8",
        )
        (enabled / "eww").mkdir()
        (enabled / "eww" / "eww.yuck").write_text(
            '(defwindow toji :geometry (geometry :x "90%" :y "90%" :width 480 :height 50) (toji))\n',
            encoding="utf-8",
        )
        (self.repo / "layouts" / "default" / "eww" / "eww.yuck").write_text(
            '(defwindow toji :geometry (geometry :x "1%" :y "1%" :width 480 :height 50) (toji))\n',
            encoding="utf-8",
        )
        prefs = Prefs.load()
        prefs.set_geometry_for(
            "sample",
            {"quote": {"x": "40%", "y": "70%", "width": "480", "height": "50"}},
        )
        prefs.save()
        ApplyEngine(repo_root=self.repo, live=False).apply("other")
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "90%"', yuck)
        self.assertNotIn(':x "40%"', yuck)
        ApplyEngine(repo_root=self.repo, live=False).apply("sample")
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "40%"', yuck)

    def test_clearing_geometry_restores_theme_yuck(self) -> None:
        theme = self.repo / "themes" / "sample"
        (theme / "eww").mkdir()
        (theme / "eww" / "eww.yuck").write_text(
            '(defwindow toji :geometry (geometry :x "22%" :y "22%" :width 480 :height 50) (toji))\n',
            encoding="utf-8",
        )
        prefs = Prefs.load()
        prefs.set_geometry_for(
            "sample",
            {"quote": {"x": "40%", "y": "70%", "width": "480", "height": "50"}},
        )
        prefs.save()
        ApplyEngine(repo_root=self.repo, live=False).apply("sample")
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "40%"', yuck)
        prefs = Prefs.load()
        prefs.clear_geometry_for("sample")
        prefs.save()
        ApplyEngine(repo_root=self.repo, live=False).apply("sample")
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "22%"', yuck)
        self.assertNotIn(':x "40%"', yuck)

    def test_gtk_settings_use_prefs(self) -> None:
        gtk = self.repo / "layouts" / "default" / "gtk" / "gtk-3.0"
        gtk.mkdir(parents=True)
        (gtk / "settings.ini").write_text("[Settings]\ngtk-theme-name=Old\n", encoding="utf-8")
        prefs = Prefs.load()
        prefs.set("gtk_theme", "New-Dark")
        prefs.set("icon_theme", "Papirus")
        prefs.set("fonts.ui", "Adwaita Sans 12")
        prefs.save()
        self.engine.apply("sample")
        text = (self.home / ".config" / "gtk-3.0" / "settings.ini").read_text(encoding="utf-8")
        self.assertIn("gtk-theme-name=New-Dark", text)
        self.assertIn("gtk-icon-theme-name=Papirus", text)
        self.assertIn("gtk-font-name=Adwaita Sans 12", text)

    def test_legacy_eww_yuck_does_not_replace_layout_windows(self) -> None:
        theme = self.repo / "themes" / "sample"
        (theme / "eww").mkdir()
        (theme / "eww" / "eww.yuck").write_text("(defwidget bar [])\n", encoding="utf-8")
        (theme / "eww" / "scripts").mkdir()
        (theme / "eww" / "scripts" / "quote.sh").write_text("echo hi\n", encoding="utf-8")
        self.engine.apply("sample")
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn("defwindow clock", yuck)
        self.assertNotIn("defwidget bar", yuck)
        self.assertTrue((self.home / ".config" / "eww" / "scripts" / "quote.sh").is_file())

    def test_theme_eww_yuck_with_windows_is_used(self) -> None:
        theme = self.repo / "themes" / "sample"
        (theme / "eww").mkdir()
        (theme / "eww" / "eww.yuck").write_text(
            '(defwindow clock :geometry (geometry :x "12%" :y "8%" :width 450 :height 155) (clock))\n',
            encoding="utf-8",
        )
        self.engine.apply("sample")
        yuck = (self.home / ".config" / "eww" / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "12%"', yuck)

    def test_dirty_dest_yuck_is_replaced_by_theme_template(self) -> None:
        theme = self.repo / "themes" / "sample"
        (theme / "eww").mkdir(exist_ok=True)
        (theme / "eww" / "eww.yuck").write_text(
            '(defwindow clock :geometry (geometry :x "12%" :y "8%" :width 450 :height 155) (clock))\n',
            encoding="utf-8",
        )
        dest = self.home / ".config" / "eww"
        dest.mkdir(parents=True)
        (dest / "eww.yuck").write_text(
            '(defwindow clock :geometry (geometry :x "99%" :y "99%" :width 1 :height 1) (clock))\n',
            encoding="utf-8",
        )
        self.engine.apply("sample", components=["eww"])
        yuck = (dest / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "12%"', yuck)
        self.assertNotIn(':x "99%"', yuck)

    def test_switching_themes_uses_each_theme_clock_not_previous_dest(self) -> None:
        left = self.repo / "themes" / "lefty"
        right = self.repo / "themes" / "righty"
        for name, x in (("lefty", "3%"), ("righty", "62%")):
            root = self.repo / "themes" / name
            root.mkdir(parents=True)
            (root / "theme.toml").write_text(
                V2_TOML.replace('name = "sample"', f'name = "{name}"'),
                encoding="utf-8",
            )
            (root / "eww").mkdir()
            (root / "eww" / "eww.yuck").write_text(
                f'(defwindow clock :geometry (geometry :x "{x}" :y "8%" :width 450 :height 155) (clock))\n',
                encoding="utf-8",
            )
        dest = self.home / ".config" / "eww"
        ApplyEngine(repo_root=self.repo, live=False).apply("lefty", components=["eww"])
        self.assertIn(':x "3%"', (dest / "eww.yuck").read_text(encoding="utf-8"))
        prefs = Prefs.load()
        prefs.set_geometry_for(
            "lefty",
            {"clock": {"x": "11%", "y": "22%", "width": "450", "height": "155"}},
        )
        prefs.save()
        ApplyEngine(repo_root=self.repo, live=False).apply("lefty", components=["eww"])
        self.assertIn(':x "11%"', (dest / "eww.yuck").read_text(encoding="utf-8"))
        ApplyEngine(repo_root=self.repo, live=False).apply("righty", components=["eww"])
        text = (dest / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "62%"', text)
        self.assertNotIn(':x "11%"', text)
        prefs = Prefs.load()
        prefs.clear_geometry_for("lefty")
        prefs.save()
        ApplyEngine(repo_root=self.repo, live=False).apply("lefty", components=["eww"])
        text = (dest / "eww.yuck").read_text(encoding="utf-8")
        self.assertIn(':x "3%"', text)
        self.assertNotIn(':x "11%"', text)

    def test_eww_card_has_no_box_fill(self) -> None:
        scss = (
            Path(__file__).resolve().parents[1]
            / "themes"
            / "_template"
            / "eww"
            / "eww.scss.template"
        ).read_text(encoding="utf-8")
        self.assertRegex(scss, r"(?m)^\.card\s*\{[^}]*background-color:\s*transparent")
        self.assertRegex(scss, r"(?m)^\.card\s*\{[^}]*border:\s*none")
        self.assertRegex(scss, r"(?m)^\.panel\s*\{[^}]*background-color:\s*transparent")
        self.assertRegex(scss, r"(?m)^\.panel\s*\{[^}]*border:\s*none")


if __name__ == "__main__":
    unittest.main()
