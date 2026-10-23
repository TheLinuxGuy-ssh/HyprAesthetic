"""HyprWave placement resolution."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hypraesthetic.apply import ApplyEngine
from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.hyprwave_cfg import (
    hyprwave_accent_pair,
    hyprwave_color_variables,
    hyprwave_themes_dir,
    resolve_hyprwave,
    sync_hyprwave_prefs,
)
from hypraesthetic.paths import current_theme_file
from hypraesthetic.prefs import Prefs
from hypraesthetic.theme import ThemePackage


class HyprwaveCfgTests(unittest.TestCase):
    def test_accent_pair_skips_base0c_cyan_slot(self) -> None:
        pkg = ThemePackage.load(Path(__file__).resolve().parents[1] / "themes" / "tanjiro")
        primary, accent = hyprwave_accent_pair(pkg.palette)
        self.assertEqual(primary.lower(), pkg.palette["base0D"].lower())
        self.assertNotEqual(accent.lower(), pkg.palette["base0C"].lower())

    def test_color_variables_use_palette_primary(self) -> None:
        pkg = ThemePackage.load(Path(__file__).resolve().parents[1] / "themes" / "spartan")
        colors = hyprwave_color_variables(pkg.palette)
        self.assertIn("rgba(255, 180, 180", colors["hw_viz_top"])

    def test_apply_deploys_css_and_uses_theme_name(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            old_home = __import__("os").environ.get("HOME")
            __import__("os").environ["HOME"] = tmp
            try:
                catalog = ThemeCatalog(official_root=root / "themes")
                engine = ApplyEngine(repo_root=root, live=False, catalog=catalog)
                prefs = Prefs.load()
                prefs.set("extras", ["hyprwave"])
                sync_hyprwave_prefs(prefs, catalog.get("spartan").data.get("hyprwave"))
                prefs.save()
                engine.apply("spartan", components=["hyprwave"])
                css = hyprwave_themes_dir() / "spartan.css"
                self.assertTrue(css.is_file())
                text = css.read_text(encoding="utf-8")
                self.assertIn(".visualizer-bar", text)
                self.assertNotIn("{{", text)
            finally:
                if old_home is None:
                    __import__("os").environ.pop("HOME", None)
                else:
                    __import__("os").environ["HOME"] = old_home

    def test_resolve_layer_and_exclusive_zone(self) -> None:
        pkg = ThemePackage.load(Path(__file__).resolve().parents[1] / "themes" / "sky")
        resolved = resolve_hyprwave(
            pkg.hyprwave,
            {"hyprwave": {"layer": "overlay", "exclusive_zone": -1}},
        )
        self.assertEqual(resolved["hyprwave_layer"], "overlay")
        self.assertEqual(resolved["hyprwave_exclusive_zone"], "-1")

    def test_apply_config_includes_layer(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            old_home = __import__("os").environ.get("HOME")
            __import__("os").environ["HOME"] = tmp
            try:
                catalog = ThemeCatalog(official_root=root / "themes")
                engine = ApplyEngine(repo_root=root, live=False, catalog=catalog)
                prefs = Prefs.load()
                prefs.set("extras", ["hyprwave"])
                prefs.set("hyprwave.layer", "overlay")
                prefs.set("hyprwave.exclusive_zone", -1)
                prefs.save()
                engine.apply("sky", components=["hyprwave"])
                conf = Path(tmp) / ".config" / "hyprwave" / "config.conf"
                text = conf.read_text(encoding="utf-8")
                self.assertIn("layer = overlay", text)
                self.assertIn("exclusive_zone = -1", text)
            finally:
                if old_home is None:
                    __import__("os").environ.pop("HOME", None)
                else:
                    __import__("os").environ["HOME"] = old_home

    def test_resolve_prefers_prefs_over_theme(self) -> None:
        pkg = ThemePackage.load(Path(__file__).resolve().parents[1] / "themes" / "spartan")
        self.assertEqual(pkg.hyprwave["edge"], "bottom")
        resolved = resolve_hyprwave(
            pkg.hyprwave,
            {"hyprwave": {"edge": "top", "margin": 12}},
        )
        self.assertEqual(resolved["hyprwave_edge"], "top")
        self.assertEqual(resolved["hyprwave_margin"], "12")

    def test_sync_on_preset_apply(self) -> None:
        pkg = ThemePackage.load(Path(__file__).resolve().parents[1] / "themes" / "sky")
        prefs = Prefs()
        sync_hyprwave_prefs(prefs, pkg.data.get("hyprwave"))
        self.assertEqual(prefs.get("hyprwave.edge"), "top")

    def test_apply_writes_config_conf_with_theme_edge(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            old_home = __import__("os").environ.get("HOME")
            __import__("os").environ["HOME"] = tmp
            try:
                catalog = ThemeCatalog(official_root=root / "themes")
                engine = ApplyEngine(repo_root=root, live=False, catalog=catalog)
                prefs = Prefs.load()
                prefs.set("extras", ["hyprwave"])
                pkg = catalog.get("jjk")
                sync_hyprwave_prefs(prefs, pkg.data.get("hyprwave"))
                prefs.save()
                engine.apply("jjk", components=["hyprwave"])
                conf = Path(tmp) / ".config" / "hyprwave" / "config.conf"
                self.assertTrue(conf.is_file())
                text = conf.read_text(encoding="utf-8")
                self.assertIn("edge = left", text)
                self.assertNotIn("config.toml", str(list(conf.parent.iterdir())))
            finally:
                if old_home is None:
                    __import__("os").environ.pop("HOME", None)
                else:
                    __import__("os").environ["HOME"] = old_home

    def test_full_apply_resets_edge_from_theme(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            old_home = __import__("os").environ.get("HOME")
            __import__("os").environ["HOME"] = tmp
            try:
                catalog = ThemeCatalog(official_root=root / "themes")
                engine = ApplyEngine(repo_root=root, live=False, catalog=catalog)
                prefs = Prefs.load()
                prefs.set("hyprwave.edge", "right")
                prefs.set("extras", ["hyprwave"])
                prefs.save()
                current_theme_file().parent.mkdir(parents=True, exist_ok=True)
                current_theme_file().write_text("toji\n", encoding="utf-8")
                with patch("hypraesthetic.undo.snapshot", lambda *a, **k: None):
                    engine.apply("sky", components=None)
                prefs = Prefs.load()
                self.assertEqual(prefs.get("hyprwave.edge"), "top")
            finally:
                if old_home is None:
                    __import__("os").environ.pop("HOME", None)
                else:
                    __import__("os").environ["HOME"] = old_home


if __name__ == "__main__":
    unittest.main()
