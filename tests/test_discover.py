#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hypraesthetic.discover import (
    font_family_only,
    format_percent,
    geom_to_fraction,
    list_bar_styles,
    list_gtk_themes,
    list_icon_themes,
    list_wallpapers,
    parse_eww_geometry,
    parse_wallpaper_query,
    primary_screen_size,
    resolve_wallpaper,
    spec_to_fractions,
    theme_preview_image,
    visible_bar_ids,
    widget_window,
)


class DiscoverTests(unittest.TestCase):
    def test_widget_quote_maps_to_toji_window(self) -> None:
        self.assertEqual(widget_window("quote"), "toji")
        self.assertEqual(widget_window("clock"), "clock")

    def test_font_family_strips_size(self) -> None:
        self.assertEqual(font_family_only("Adwaita Sans 11"), "Adwaita Sans")
        self.assertEqual(font_family_only("JetBrainsMono Nerd Font"), "JetBrainsMono Nerd Font")

    def test_lists_gtk_and_icon_themes_from_roots(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        gtk = root / "themes" / "Fake-Dark"
        gtk.mkdir(parents=True)
        (gtk / "gtk-3.0").mkdir()
        icons = root / "icons" / "Fake-Icons"
        icons.mkdir(parents=True)
        (icons / "index.theme").write_text("[Icon Theme]\n", encoding="utf-8")
        self.assertEqual(list_gtk_themes([root / "themes"]), ["Fake-Dark"])
        self.assertEqual(list_icon_themes([root / "icons"]), ["Fake-Icons"])
        tmp.cleanup()

    def test_lists_wallpapers(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        folder = Path(tmp.name)
        (folder / "one.png").write_bytes(b"x")
        (folder / "two.gif").write_bytes(b"x")
        (folder / "notes.txt").write_text("nope", encoding="utf-8")
        found = list_wallpapers(roots=[], extra=[folder])
        self.assertEqual([p.name for p in found], ["one.png", "two.gif"])
        tmp.cleanup()

    def test_parse_eww_geometry_maps_quote_window(self) -> None:
        text = '(defwindow toji :geometry (geometry :x "62%" :y "88%" :width 520 :height 50) (toji))\n'
        geom = parse_eww_geometry(text)
        self.assertEqual(geom["quote"]["x"], "62%")
        self.assertEqual(geom["quote"]["y"], "88%")

    def test_lists_bar_styles(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        repo = Path(tmp.name)
        bar = repo / "layouts" / "bars" / "compact"
        bar.mkdir(parents=True)
        (bar / "config.jsonc").write_text("{}\n", encoding="utf-8")
        styles = list_bar_styles(repo)
        self.assertEqual(styles[0].id, "compact")
        self.assertEqual(styles[0].name, "Compact")
        tmp.cleanup()

    def test_geom_px_uses_axis_screen_size(self) -> None:
        screen = (1920, 1080)
        self.assertAlmostEqual(geom_to_fraction("10%", "x", screen), 0.1)
        self.assertAlmostEqual(geom_to_fraction("108", "y", screen), 0.1)
        self.assertAlmostEqual(geom_to_fraction("1920px", "x", screen), 1.0)
        self.assertAlmostEqual(geom_to_fraction("-5%", "y", screen), -0.05)

    def test_spec_to_fractions_and_percent_roundtrip(self) -> None:
        spec = {"x": "62%", "y": "8%", "width": "450", "height": "155"}
        x, y, width, height = spec_to_fractions(spec, (1600, 1000))
        self.assertAlmostEqual(x, 0.62)
        self.assertAlmostEqual(y, 0.08)
        self.assertAlmostEqual(width, 450 / 1600)
        self.assertAlmostEqual(height, 155 / 1000)
        self.assertEqual(format_percent(0.625), "62.5%")
        self.assertEqual(format_percent(0.62), "62%")

    def test_parse_swww_wallpaper_query(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        image = Path(tmp.name) / "choso.png"
        image.write_bytes(b"x")
        text = f": eDP-1: 1600x1000, scale: 1.6, currently displaying: image: {image}\n"
        self.assertEqual(parse_wallpaper_query(text), image)
        tmp.cleanup()

    def test_resolve_wallpaper_prefers_live_then_override(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        live = Path(tmp.name) / "live.png"
        pref = Path(tmp.name) / "pref.png"
        live.write_bytes(b"l")
        pref.write_bytes(b"p")

        class LiveRunner:
            def __call__(self, args, **_kwargs):
                class Result:
                    stdout = f"image: {live}\n"
                    returncode = 0

                return Result()

        found = resolve_wallpaper(override=str(pref), live=True, runner=LiveRunner())
        self.assertEqual(found, live)
        found = resolve_wallpaper(override=str(pref), live=False, runner=LiveRunner())
        self.assertEqual(found, pref)
        tmp.cleanup()

    def test_primary_screen_uses_logical_pixels(self) -> None:
        class MonitorRunner:
            def __call__(self, args, **_kwargs):
                class Result:
                    stdout = '[{"width": 2560, "height": 1600, "scale": 1.6, "focused": true}]'
                    returncode = 0

                return Result()

        self.assertEqual(primary_screen_size(runner=MonitorRunner()), (1600, 1000))

    def test_bar_toml_supplies_name_and_preview(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        repo = Path(tmp.name)
        bar = repo / "layouts" / "bars" / "v1.1"
        bar.mkdir(parents=True)
        (bar / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (bar / "bar.toml").write_text('name = "V1.1"\ndescription = "Island"\n', encoding="utf-8")
        (bar / "preview.png").write_bytes(b"x")
        styles = list_bar_styles(repo)
        self.assertEqual(styles[0].id, "v1.1")
        self.assertEqual(styles[0].name, "V1.1")
        self.assertEqual(styles[0].description, "Island")
        self.assertEqual(styles[0].preview.name, "preview.png")
        tmp.cleanup()

    def test_theme_preview_finds_gif_wallpaper(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        wall = root / "wallpaper"
        wall.mkdir()
        gif = wall / "ha-test-unique-batman.gif"
        gif.write_bytes(b"GIF89a")
        pkg = SimpleNamespace(root=root, wallpaper="ha-test-unique-batman.gif", preview="preview.png")
        self.assertEqual(theme_preview_image(pkg), gif)
        tmp.cleanup()

    def test_theme_preview_falls_back_to_preview_gif(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        gif = root / "preview.gif"
        gif.write_bytes(b"GIF89a")
        pkg = SimpleNamespace(root=root, wallpaper="", preview="preview.png")
        self.assertEqual(theme_preview_image(pkg), gif)
        tmp.cleanup()

    def test_theme_preview_prefers_named_wallpaper_over_preview_gif(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "wallpaper").mkdir()
        gif = root / "wallpaper" / "theme.gif"
        gif.write_bytes(b"GIF89a")
        (root / "preview.gif").write_bytes(b"GIF89a")
        pkg = SimpleNamespace(root=root, wallpaper="theme.gif", preview="preview.png")
        self.assertEqual(theme_preview_image(pkg), gif)
        tmp.cleanup()

    def test_bar_preview_accepts_gif(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        repo = Path(tmp.name)
        bar = repo / "layouts" / "bars" / "neon"
        bar.mkdir(parents=True)
        (bar / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (bar / "preview.gif").write_bytes(b"GIF89a")
        styles = list_bar_styles(repo)
        self.assertEqual(styles[0].preview.name, "preview.gif")
        tmp.cleanup()

    def test_first_party_bars_have_preview_files(self) -> None:
        styles = {s.id: s for s in list_bar_styles()}
        for sid in ("default", "compact", "a70", "cyberpunk"):
            self.assertIn(sid, styles)
            self.assertIsNotNone(styles[sid].preview, sid)
            self.assertTrue(styles[sid].preview.is_file(), sid)

    def test_bar_preview_finds_screenshot_and_v29e_png(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        repo = Path(tmp.name)
        shot = repo / "layouts" / "bars" / "compact"
        shot.mkdir(parents=True)
        (shot / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (shot / "screenshot-b.png").write_bytes(b"b")
        (shot / "screenshot-a.png").write_bytes(b"a")
        named = repo / "layouts" / "bars" / "a70"
        named.mkdir(parents=True)
        (named / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (named / "V2.9e.png").write_bytes(b"v")
        (named / "screenshot-z.png").write_bytes(b"s")
        jpg = repo / "layouts" / "bars" / "plain"
        jpg.mkdir(parents=True)
        (jpg / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (jpg / "screenshot-1.jpg").write_bytes(b"j")
        styles = {s.id: s for s in list_bar_styles(repo)}
        self.assertEqual(styles["compact"].preview.name, "screenshot-a.png")
        self.assertEqual(styles["a70"].preview.name, "V2.9e.png")
        self.assertEqual(styles["plain"].preview.name, "screenshot-1.jpg")
        tmp.cleanup()

    def test_named_preview_beats_screenshot_and_v29e(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        repo = Path(tmp.name)
        bar = repo / "layouts" / "bars" / "neon"
        bar.mkdir(parents=True)
        (bar / "config.jsonc").write_text("{}\n", encoding="utf-8")
        (bar / "preview.png").write_bytes(b"p")
        (bar / "V2.9e.png").write_bytes(b"v")
        (bar / "screenshot-a.png").write_bytes(b"s")
        styles = list_bar_styles(repo)
        self.assertEqual(styles[0].preview.name, "preview.png")
        tmp.cleanup()

    def test_imported_bars_stay_hidden_until_search(self) -> None:
        entries = [
            ("none", "none None Hide the status bar"),
            ("default", "default Capsule Rounded island bar"),
            ("compact", "compact Compact Workspaces"),
            ("a70", "a70 Dock Centered workspaces"),
            ("cyberpunk", "cyberpunk Night City Flat modules"),
            ("v1", "v1 V1 Waybar layout"),
            ("v2.9e", "v2.9e Island Waybar layout"),
        ]
        idle = visible_bar_ids(entries, "")
        self.assertEqual(idle, ["none", "default", "compact", "a70", "cyberpunk"])
        hit = visible_bar_ids(entries, "v2.9")
        self.assertIn("cyberpunk", hit)
        self.assertIn("none", hit)
        self.assertIn("v2.9e", hit)
        self.assertNotIn("v1", hit)
        blank = visible_bar_ids(entries, "   ")
        self.assertNotIn("v1", blank)
        self.assertIn("cyberpunk", blank)


if __name__ == "__main__":
    unittest.main()
