#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hypraesthetic.rofi_style import deploy_rofi_theme, patch_rasi_contrast, rewrite_shared_color_imports


class RofiStyleTests(unittest.TestCase):
    def test_patch_rasi_contrast_fixes_selected_foreground(self) -> None:
        raw = "selected-normal-foreground:  var(background);\n"
        patched = patch_rasi_contrast(raw)
        self.assertIn("var(foreground)", patched)

    def test_deploy_writes_primary_as_selected_and_rewrites_shared_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates_root = root / "themes" / "_template"
            rofi_tpl = templates_root / "rofi"
            rofi_tpl.mkdir(parents=True)
            (rofi_tpl / "colors.rasi.template").write_text(
                "* { selected: {{colors.waybar.primary}}; active: {{colors.waybar.primary}}; }\n",
                encoding="utf-8",
            )
            (rofi_tpl / "wallpaper.rasi.template").write_text(
                '@import "colors/hypraesthetic.rasi"\n',
                encoding="utf-8",
            )
            rofi_dest = root / "rofi"
            shared = rofi_dest / "launchers" / "type-1" / "shared" / "colors.rasi"
            shared.parent.mkdir(parents=True)
            shared.write_text('@import "~/.config/rofi/colors/onedark.rasi"\n', encoding="utf-8")
            style = rofi_dest / "launchers" / "type-1" / "style-1.rasi"
            style.write_text(
                "selected-normal-foreground:  var(background);\n",
                encoding="utf-8",
            )
            variables = {"colors_waybar_primary": "#aabbcc"}
            colors = deploy_rofi_theme(rofi_dest, templates_root, variables)
            self.assertTrue(colors.is_file())
            text = colors.read_text(encoding="utf-8")
            self.assertIn("#aabbcc", text)
            shared_text = shared.read_text(encoding="utf-8")
            self.assertIn(str(colors), shared_text)
            self.assertNotIn("onedark", shared_text)
            self.assertIn("var(foreground)", style.read_text(encoding="utf-8"))

    def test_rewrite_shared_color_imports_updates_all_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rofi_dest = Path(tmp) / "rofi"
            for sub in ("launchers/type-3/shared", "applets/type-2/shared", "powermenu/type-4/shared"):
                path = rofi_dest / sub / "colors.rasi"
                path.parent.mkdir(parents=True)
                path.write_text("@import onedark\n", encoding="utf-8")
            colors = rofi_dest / "colors" / "hypraesthetic.rasi"
            colors.parent.mkdir(parents=True)
            colors.write_text("* {}\n", encoding="utf-8")
            rewrite_shared_color_imports(rofi_dest, colors)
            for sub in ("launchers/type-3/shared", "applets/type-2/shared", "powermenu/type-4/shared"):
                body = (rofi_dest / sub / "colors.rasi").read_text(encoding="utf-8")
                self.assertIn(str(colors), body)


if __name__ == "__main__":
    unittest.main()
