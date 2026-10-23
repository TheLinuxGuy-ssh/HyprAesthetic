#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path

STATIC_GIF = bytes.fromhex(
    "47494638396101000100800000ffffff0000002c00000000010001000002024401003b"
)
ANIMATED_GIF = bytes.fromhex(
    "47494638396101000100800000ffffff000000"
    "21ff0b4e45545343415045322e300301000000"
    "21f904000a0000002c0000000001000100000202440100"
    "21f904000a0000002c00000000010001000002024c0100"
    "3b"
)


def _pixbuf_ok() -> bool:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Gdk", "4.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf  # noqa: F401
    except (ValueError, ImportError):
        return False
    return True


@unittest.skipUnless(_pixbuf_ok(), "GdkPixbuf is not available")
class PreviewTests(unittest.TestCase):
    def test_cover_pixbuf_crops_to_requested_size(self) -> None:
        from gi.repository import GdkPixbuf

        from hypraesthetic_gui.preview import cover_pixbuf

        src = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 40, 20)
        self.assertIsNotNone(src)
        src.fill(0xFF000000)
        cropped = cover_pixbuf(src, 10, 10)
        self.assertIsNotNone(cropped)
        self.assertEqual(cropped.get_width(), 10)
        self.assertEqual(cropped.get_height(), 10)

    def test_cover_pixbuf_decodes_at_least_target_size(self) -> None:
        from gi.repository import GdkPixbuf

        from hypraesthetic_gui.preview import (
            FILM_HEIGHT,
            FILM_WIDTH,
            HERO_HEIGHT,
            HERO_WIDTH,
            PRESET_HEIGHT,
            PRESET_WIDTH,
            cover_pixbuf,
        )

        self.assertEqual((PRESET_WIDTH, PRESET_HEIGHT), (420, 236))
        self.assertEqual((FILM_WIDTH, FILM_HEIGHT), (160, 90))
        self.assertEqual((HERO_WIDTH, HERO_HEIGHT), (640, 360))
        src = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 2000, 1000)
        self.assertIsNotNone(src)
        src.fill(0x11223300)
        seen: list[tuple[int, int]] = []
        original = GdkPixbuf.Pixbuf.scale_simple

        def spy(pixbuf, width, height, interp):
            seen.append((int(width), int(height)))
            return original(pixbuf, width, height, interp)

        with unittest.mock.patch.object(GdkPixbuf.Pixbuf, "scale_simple", spy):
            cropped = cover_pixbuf(src, PRESET_WIDTH, PRESET_HEIGHT)
        self.assertIsNotNone(cropped)
        self.assertEqual(cropped.get_width(), 420)
        self.assertEqual(cropped.get_height(), 236)
        self.assertTrue(any(width >= 840 and height >= 472 for width, height in seen), seen)

    def test_load_animation_reads_static_gif(self) -> None:
        from hypraesthetic_gui.preview import load_animation, load_static_pixbuf

        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "static.gif"
        path.write_bytes(STATIC_GIF)
        anim = load_animation(path)
        if anim is None:
            tmp.cleanup()
            self.skipTest("GdkPixbuf GIF loader is not available")
        self.assertTrue(anim.is_static_image())
        self.assertEqual(anim.get_width(), 1)
        self.assertEqual(anim.get_height(), 1)
        pixbuf = load_static_pixbuf(path)
        self.assertIsNotNone(pixbuf)
        self.assertEqual(pixbuf.get_width(), 1)
        tmp.cleanup()

    def test_load_animation_reads_two_frame_gif(self) -> None:
        from hypraesthetic_gui.preview import load_animation, should_animate

        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "loop.gif"
        path.write_bytes(ANIMATED_GIF)
        anim = load_animation(path)
        if anim is None:
            tmp.cleanup()
            self.skipTest("GdkPixbuf GIF loader is not available")
        if anim.is_static_image():
            tmp.cleanup()
            self.skipTest("GdkPixbuf decoded the fixture as a still frame")
        self.assertTrue(should_animate(path, anim))
        self.assertFalse(should_animate(path, anim, max_bytes=1))
        self.assertFalse(should_animate(path, anim, max_pixels=0))
        tmp.cleanup()

    def test_load_animation_returns_none_for_garbage(self) -> None:
        from hypraesthetic_gui.preview import load_animation, load_static_pixbuf

        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "nope.gif"
        path.write_bytes(b"not an image")
        self.assertIsNone(load_animation(path))
        self.assertIsNone(load_static_pixbuf(path))
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
