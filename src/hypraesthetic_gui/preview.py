"""Theme and wallpaper previews via GdkPixbuf so GIFs load under GTK 4."""

from __future__ import annotations

import math
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

# Match desktop screenshot aspect ratio (e.g. 2560×1600 → 16:10).
PREVIEW_REF_WIDTH = 2560
PREVIEW_REF_HEIGHT = 1600


def preview_height_for_width(width: int) -> int:
    return max(1, int(round(width * PREVIEW_REF_HEIGHT / PREVIEW_REF_WIDTH)))


def preview_width_for_height(height: int) -> int:
    return max(1, int(round(height * PREVIEW_REF_WIDTH / PREVIEW_REF_HEIGHT)))


TILE_WIDTH = 196
TILE_HEIGHT = preview_height_for_width(TILE_WIDTH)
PRESET_WIDTH = 420
PRESET_HEIGHT = preview_height_for_width(PRESET_WIDTH)
FILM_WIDTH = 160
FILM_HEIGHT = preview_height_for_width(FILM_WIDTH)
HERO_WIDTH = 640
HERO_HEIGHT = preview_height_for_width(HERO_WIDTH)
MAX_ANIM_BYTES = 8 * 1024 * 1024
MAX_ANIM_PIXELS = 8_000_000


def _interp_type() -> GdkPixbuf.InterpType:
    return getattr(GdkPixbuf.InterpType, "HYPSERSAMPLE", GdkPixbuf.InterpType.BILINEAR)


def _cover_dims(src_w: int, src_h: int, width: int, height: int) -> tuple[int, int]:
    src_w = max(int(src_w), 1)
    src_h = max(int(src_h), 1)
    width = max(int(width), 1)
    height = max(int(height), 1)
    if src_w * height >= src_h * width:
        scaled_h = height
        scaled_w = math.ceil(src_w * height / src_h)
    else:
        scaled_w = width
        scaled_h = math.ceil(src_h * width / src_w)
    return max(int(scaled_w), 1), max(int(scaled_h), 1)


def _scale_cover(src: GdkPixbuf.Pixbuf, width: int, height: int) -> GdkPixbuf.Pixbuf | None:
    src_w = max(src.get_width(), 1)
    src_h = max(src.get_height(), 1)
    scaled_w, scaled_h = _cover_dims(src_w, src_h, width, height)
    if scaled_w == src_w and scaled_h == src_h:
        return src
    return src.scale_simple(scaled_w, scaled_h, _interp_type())


def cover_pixbuf(src: GdkPixbuf.Pixbuf, width: int, height: int) -> GdkPixbuf.Pixbuf | None:
    width = max(1, int(width))
    height = max(1, int(height))
    decode_size = (width * 2, height * 2)
    scaled = _scale_cover(src, decode_size[0], decode_size[1])
    if scaled is None:
        return None
    fitted = _scale_cover(scaled, width, height)
    if fitted is None:
        return None
    fitted_w = fitted.get_width()
    fitted_h = fitted.get_height()
    x = max(0, (fitted_w - width) // 2)
    y = max(0, (fitted_h - height) // 2)
    crop_w = min(width, fitted_w)
    crop_h = min(height, fitted_h)
    cropped = fitted.new_subpixbuf(x, y, crop_w, crop_h)
    if cropped is None:
        return fitted
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
    placeholder: str | None = None,
) -> Gtk.Widget:
    frame = Gtk.Frame()
    frame.add_css_class("ha-preview")
    frame.set_overflow(Gtk.Overflow.HIDDEN)
    picture = _picture_for(image, width, height) if image is not None and image.is_file() else None
    if picture is not None:
        frame.set_child(picture)
        return frame
    if placeholder:
        frame.set_child(_placeholder(placeholder, width, height))
        return frame
    frame.set_child(_swatch(color, width, height))
    return frame


def _decode_static_cover(path: Path | str, width: int, height: int) -> GdkPixbuf.Pixbuf | None:
    width = max(1, int(width))
    height = max(1, int(height))
    decode_size = (width * 2, height * 2)
    src_w, src_h = _file_pixel_size(path)
    if src_w > decode_size[0] or src_h > decode_size[1]:
        load_w, load_h = _cover_dims(src_w, src_h, decode_size[0], decode_size[1])
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), load_w, load_h, True)
        except GLib.Error:
            pixbuf = None
        if pixbuf is not None:
            return pixbuf
    return load_static_pixbuf(path)


def _file_pixel_size(path: Path | str) -> tuple[int, int]:
    try:
        info = GdkPixbuf.Pixbuf.get_file_info(str(path))
    except GLib.Error:
        return 0, 0
    if not info:
        return 0, 0
    try:
        return max(int(info[1] or 0), 0), max(int(info[2] or 0), 0)
    except (TypeError, ValueError, IndexError):
        return 0, 0


def _picture_for(image: Path, width: int, height: int) -> Gtk.Picture | None:
    anim, src = _preview_source(image, width, height)
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


def _preview_source(
    image: Path, width: int, height: int
) -> tuple[GdkPixbuf.PixbufAnimation | None, GdkPixbuf.Pixbuf | None]:
    suffix = image.suffix.lower()
    decode_size = (max(1, int(width)) * 2, max(1, int(height)) * 2)
    if suffix in {".gif", ".webp"} and _worth_animating(image):
        anim = load_animation(image)
        if anim is not None:
            frame = anim.get_static_image()
            if frame is not None and not anim.is_static_image():
                return anim, frame
            if (
                frame is not None
                and frame.get_width() <= decode_size[0]
                and frame.get_height() <= decode_size[1]
            ):
                return None, frame
    return None, _decode_static_cover(image, width, height)


def _worth_animating(image: Path) -> bool:
    try:
        return image.stat().st_size <= MAX_ANIM_BYTES
    except OSError:
        return False


def _placeholder(text: str, width: int, height: int) -> Gtk.Box:
    box = Gtk.Box()
    box.set_size_request(width, height)
    label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
    label.set_halign(Gtk.Align.CENTER)
    label.set_valign(Gtk.Align.CENTER)
    box.append(label)
    return box


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
