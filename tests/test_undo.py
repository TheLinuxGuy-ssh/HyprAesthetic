#!/usr/bin/env python3

from __future__ import annotations

import unittest

from hypraesthetic.paths import user_config_dir
from hypraesthetic.prefs import Prefs
from hypraesthetic.undo import load_snapshot, undo
from tests.test_theme import V2_TOML


def _write_theme(root, name: str, *, bar_style: str = "") -> None:
    theme = root / "themes" / name
    theme.mkdir(parents=True, exist_ok=True)
    body = V2_TOML.replace('name = "sample"', f'name = "{name}"')
    if bar_style:
        body = body.replace('bar = "waybar"', f'bar = "waybar"\nbar_style = "{bar_style}"')
    (theme / "theme.toml").write_text(body.lstrip(), encoding="utf-8")


class UndoTests(unittest.TestCase):
    def setUp(self) -> None:
        from tests.test_apply import ApplyEngineTests

        self._fixture = ApplyEngineTests(methodName="test_skips_disabled_components")
        self._fixture.setUp()
        self.engine = self._fixture.engine
        self.repo = self._fixture.repo
        self.home = self._fixture.home

    def tearDown(self) -> None:
        self._fixture.tearDown()

    def _current(self):
        return user_config_dir() / "current_theme"

    def _mark_current(self, name: str) -> None:
        path = self._current()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name + "\n", encoding="utf-8")

    def test_undo_restores_previous_theme_name(self) -> None:
        _write_theme(self.repo, "other", bar_style="compact")
        self._mark_current("sample")
        prefs = Prefs.load()
        prefs.set("wallpaper", "/tmp/custom.png")
        prefs.set("bar_style", "default")
        prefs.set("bar", "waybar")
        prefs.set("widgets", ["clock"])
        prefs.set_geometry_for(
            "sample",
            {"quote": {"x": "40%", "y": "70%", "width": "480", "height": "50"}},
        )
        prefs.save()

        self.engine.apply("other")
        self.assertEqual(self._current().read_text(encoding="utf-8").strip(), "other")
        self.assertEqual(Prefs.load().get("bar_style"), "compact")

        drifted = Prefs.load()
        drifted.set("wallpaper", "/tmp/other.png")
        drifted.set("widgets", ["matrix"])
        drifted.set("bar", "none")
        drifted.clear_geometry_for("sample")
        drifted.save()
        self._current().write_text("other\n", encoding="utf-8")

        restored = undo(self.engine)
        self.assertEqual(restored, "sample")
        self.assertEqual(self._current().read_text(encoding="utf-8").strip(), "sample")
        loaded = Prefs.load()
        self.assertEqual(loaded.get("wallpaper"), "/tmp/custom.png")
        self.assertEqual(loaded.get("bar"), "waybar")
        self.assertEqual(loaded.get("widgets"), ["clock"])
        self.assertEqual(loaded.geometry_for("sample")["quote"]["x"], "40%")

    def test_snapshot_records_prefs_before_theme_bar_style(self) -> None:
        _write_theme(self.repo, "other", bar_style="compact")
        self._mark_current("sample")
        prefs = Prefs.load()
        prefs.set("wallpaper", "/tmp/custom.png")
        prefs.set("bar_style", "default")
        prefs.set("widgets", ["clock", "system"])
        prefs.set(
            "widget_geometry",
            {"clock": {"x": "12%", "y": "8%", "width": "450", "height": "155"}},
        )
        prefs.save()
        self.engine.apply("other")
        saved = load_snapshot()
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(saved["theme"], "sample")
        self.assertEqual(saved["wallpaper"], "/tmp/custom.png")
        self.assertEqual(saved["bar_style"], "default")
        self.assertEqual(saved["bar"], "waybar")
        self.assertEqual(saved["widgets"], ["clock", "system"])
        self.assertEqual(saved["widget_geometry"]["clock"]["x"], "12%")
        self.assertNotIn("widgets_by_theme", saved)
        self.assertEqual(Prefs.load().get("bar_style"), "compact")

    def test_snapshot_includes_widgets_by_theme_only_when_present(self) -> None:
        _write_theme(self.repo, "other")
        self._mark_current("sample")
        prefs = Prefs.load()
        prefs.set("widgets_by_theme", {"sample": ["clock"]})
        prefs.save()
        self.engine.apply("other")
        saved = load_snapshot()
        assert saved is not None
        self.assertEqual(saved["widgets_by_theme"], {"sample": ["clock"]})

    def test_dry_run_does_not_write_snapshot(self) -> None:
        path = user_config_dir() / "last-apply.toml"
        self.engine.apply("sample", dry_run=True)
        self.assertFalse(path.exists())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('theme = "keep"\n', encoding="utf-8")
        self.engine.apply("sample", dry_run=True)
        self.assertEqual(path.read_text(encoding="utf-8"), 'theme = "keep"\n')

    def test_component_apply_does_not_overwrite_snapshot(self) -> None:
        self._mark_current("sample")
        prefs = Prefs.load()
        prefs.set("wallpaper", "/tmp/custom.png")
        prefs.save()
        self.engine.apply("sample")
        path = user_config_dir() / "last-apply.toml"
        before = path.read_text(encoding="utf-8")
        self.assertIn("/tmp/custom.png", before)
        changed = Prefs.load()
        changed.set("wallpaper", "/tmp/other.png")
        changed.save()
        self.engine.apply("sample", components=["eww"])
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertEqual(load_snapshot()["wallpaper"], "/tmp/custom.png")

    def test_undo_puts_back_bar_style_the_theme_would_overwrite(self) -> None:
        sample_toml = self.repo / "themes" / "sample" / "theme.toml"
        sample_toml.write_text(
            sample_toml.read_text(encoding="utf-8")
            .replace("waybar = false", "waybar = true")
            .replace('bar = "waybar"', 'bar = "waybar"\nbar_style = "v1"'),
            encoding="utf-8",
        )
        _write_theme(self.repo, "other", bar_style="v2")
        other_toml = self.repo / "themes" / "other" / "theme.toml"
        other_toml.write_text(
            other_toml.read_text(encoding="utf-8").replace("waybar = false", "waybar = true"),
            encoding="utf-8",
        )
        for style, marker in (("compact", "COMPACT"), ("v1", "FROM-V1"), ("v2", "FROM-V2")):
            bar = self.repo / "layouts" / "bars" / style
            bar.mkdir(parents=True)
            (bar / "config.jsonc").write_text(marker + "\n", encoding="utf-8")
        self._mark_current("sample")
        prefs = Prefs.load()
        prefs.set("bar_style", "compact")
        prefs.set("bar", "waybar")
        prefs.save()
        self.engine.apply("other")
        deployed = self.home / ".config" / "waybar" / "config.jsonc"
        self.assertEqual(deployed.read_text(encoding="utf-8"), "FROM-V2\n")
        undo(self.engine)
        self.assertEqual(Prefs.load().get("bar_style"), "compact")
        self.assertEqual(deployed.read_text(encoding="utf-8"), "COMPACT\n")

    def test_second_undo_toggles_back_to_the_theme_just_left(self) -> None:
        _write_theme(self.repo, "other", bar_style="compact")
        self._mark_current("sample")
        prefs = Prefs.load()
        prefs.set("wallpaper", "/tmp/a.png")
        prefs.set("bar_style", "default")
        prefs.set("bar", "waybar")
        prefs.set("widgets", ["clock"])
        prefs.save()

        self.engine.apply("other")
        on_other = Prefs.load()
        on_other.set("wallpaper", "/tmp/b.png")
        on_other.set("widgets", ["matrix"])
        on_other.save()
        self.assertEqual(Prefs.load().get("bar_style"), "compact")

        first = undo(self.engine)
        self.assertEqual(first, "sample")
        self.assertEqual(self._current().read_text(encoding="utf-8").strip(), "sample")
        back = Prefs.load()
        self.assertEqual(back.get("wallpaper"), "/tmp/a.png")
        self.assertEqual(back.get("bar_style"), "default")
        self.assertEqual(back.get("widgets"), ["clock"])

        second = undo(self.engine)
        self.assertEqual(second, "other")
        self.assertEqual(self._current().read_text(encoding="utf-8").strip(), "other")
        toggled = Prefs.load()
        self.assertEqual(toggled.get("wallpaper"), "/tmp/b.png")
        self.assertEqual(toggled.get("bar_style"), "compact")
        self.assertEqual(toggled.get("widgets"), ["matrix"])
        self.assertEqual(toggled.get("bar"), "waybar")

    def test_undo_restores_per_theme_widget_set(self) -> None:
        _write_theme(self.repo, "other")
        other_toml = self.repo / "themes" / "other" / "theme.toml"
        other_toml.write_text(
            other_toml.read_text(encoding="utf-8").replace(
                'widgets = ["clock", "system"]',
                'widgets = ["quote"]',
            ),
            encoding="utf-8",
        )
        self._mark_current("sample")
        prefs = Prefs.load()
        prefs.set_widgets_for("sample", ["clock"])
        prefs.save()
        self.engine.apply("other")
        on_other = Prefs.load()
        self.assertEqual(on_other.widgets_for("other"), ["quote"])
        self.assertEqual(on_other.widgets_for("sample"), ["clock"])
        restored = undo(self.engine)
        self.assertEqual(restored, "sample")
        loaded = Prefs.load()
        self.assertEqual(loaded.widgets_for("sample"), ["clock"])
        self.assertEqual(loaded.get("widgets"), ["clock"])
        self.assertNotEqual(loaded.widgets_for("other"), ["clock"])

    def test_undo_without_snapshot_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            undo(self.engine)


if __name__ == "__main__":
    unittest.main()
