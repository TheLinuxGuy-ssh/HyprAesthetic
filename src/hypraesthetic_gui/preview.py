"""Theme and wallpaper previews via GdkPixbuf so GIFs load under GTK 4."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

TILE_WIDTH = 196
TILE_HEIGHT = 118
MAX_ANIM_BYTES = 8 * 1024 * 1024
MAX_ANIM_PIXELS = 8_000_000


def cover_pixbuf(src: GdkPixbuf.Pixbuf, width: int, height: int) -> GdkPixbuf.Pixbuf | None:
    width = max(1, int(width))
    height = max(1, int(height))
    src_w = max(src.get_width(), 1)
    src_h = max(src.get_height(), 1)
    scale = max(width / src_w, height / src_h)
    scaled_w = max(1, int(src_w * scale))
    scaled_h = max(1, int(src_h * scale))
    scaled = src.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)
    if scaled is None:
        return None
    x = max(0, (scaled_w - width) // 2)
    y = max(0, (scaled_h - height) // 2)
    crop_w = min(width, scaled_w)
    crop_h = min(height, scaled_h)
    cropped = scaled.new_subpixbuf(x, y, crop_w, crop_h)
    if cropped is None:
        return scaled
    return cropped.copy()


def load_animation(path: Path | str) -> GdkPixbuf.PixbufAnimation | None:
    try:
        return GdkPixbuf.PixbufAnimation.new_from_file(str(path))
    except GLib.Error:
        return None


def load_static_pixbuf(path: Path | str) -> GdkPixbuf.Pixbuf | None:
    anim = load_animation(path)
    if anim is not None:
        image = anim.get_static_image()
        if image is not None:
            return image
    try:
        return GdkPixbuf.Pixbuf.new_from_file(str(path))
    except GLib.Error:
        return None


def should_animate(
    path: Path | str,
    anim: GdkPixbuf.PixbufAnimation,
    *,
    max_bytes: int = MAX_ANIM_BYTES,
    max_pixels: int = MAX_ANIM_PIXELS,
) -> bool:
    if anim.is_static_image():
        return False
    file = Path(path)
    try:
        if file.stat().st_size > max_bytes:
            return False
    except OSError:
        return False
    return anim.get_width() * anim.get_height() <= max_pixels


def preview_widget(
    image: Path | None,
    color: str | None = None,
    width: int = TILE_WIDTH,
    height: int = TILE_HEIGHT,
) -> Gtk.Widget:
    frame = Gtk.Frame()
    frame.add_css_class("ha-preview")
    frame.set_overflow(Gtk.Overflow.HIDDEN)
    picture = _picture_for(image, width, height) if image is not None and image.is_file() else None
    if picture is not None:
        frame.set_child(picture)
        return frame
    frame.set_child(_swatch(color, width, height))
    return frame


def _picture_for(image: Path, width: int, height: int) -> Gtk.Picture | None:
    anim = load_animation(image)
    src = anim.get_static_image() if anim is not None else load_static_pixbuf(image)
    if src is None:
        return None
    picture = Gtk.Picture()
    picture.set_content_fit(Gtk.ContentFit.COVER)
    picture.set_size_request(width, height)
    picture.set_hexpand(True)
    if not _set_cover(picture, src, width, height):
        return None
    if anim is not None and should_animate(image, anim):
        player = _FramePlayer(picture, anim, width, height)
        picture.connect("map", player.start)
        picture.connect("unmap", player.stop)
        picture.connect("unrealize", player.stop)
        picture._ha_player = player  # noqa: SLF001 — keep the player alive
        if picture.get_mapped():
            player.start()
    return picture


def _set_cover(picture: Gtk.Picture, src: GdkPixbuf.Pixbuf, width: int, height: int) -> bool:
    cropped = cover_pixbuf(src, width, height)
    if cropped is None:
        return False
    picture.set_paintable(Gdk.Texture.new_for_pixbuf(cropped))
    return True


def _swatch(color: str | None, width: int, height: int) -> Gtk.Box:
    box = Gtk.Box()
    box.set_size_request(width, height)
    box.set_hexpand(True)
    if not color:
        return box
    klass = f"ha-swatch-{abs(hash(color)) % 10_000_000}"
    box.add_css_class(klass)
    provider = Gtk.CssProvider()
    provider.load_from_data(f".{klass} {{ background: {color}; }}".encode())
    box.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return box


class _FramePlayer:
    def __init__(self, picture: Gtk.Picture, anim: GdkPixbuf.PixbufAnimation, width: int, height: int) -> None:
        self.picture = picture
        self.anim = anim
        self.width = width
        self.height = height
        self._iter: GdkPixbuf.PixbufAnimationIter | None = None
        self._source_id = 0

    def start(self, *_args) -> None:
        self.stop()
        self._iter = self.anim.get_iter(None)
        self._paint()
        self._arm()

    def stop(self, *_args) -> None:
        if self._source_id:
            GLib.source_remove(self._source_id)
            self._source_id = 0

    def _paint(self) -> None:
        if self._iter is None:
            return
        pixbuf = self._iter.get_pixbuf()
        if pixbuf is None:
            return
        _set_cover(self.picture, pixbuf, self.width, self.height)

    def _arm(self) -> None:
        if self._iter is None:
            return
        delay = self._iter.get_delay_time()
        if delay < 0:
            return
        self._source_id = GLib.timeout_add(max(delay, 20), self._tick)

    def _tick(self) -> bool:
        self._source_id = 0
        if not self.picture.get_mapped() or self._iter is None:
            return False
        self._iter.advance(None)
        self._paint()
        self._arm()
        return False
