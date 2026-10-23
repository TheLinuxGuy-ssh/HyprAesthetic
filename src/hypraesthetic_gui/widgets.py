"""Control-center pages."""

from __future__ import annotations

import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gtk, Pango

from hypraesthetic.apply import ApplyEngine
from hypraesthetic.catalog import ThemeCatalog
from hypraesthetic.bar_schematic import modules_for_bar
from hypraesthetic.discover import (
    APP_CANDIDATES,
    FIRST_PARTY_BAR_IDS,
    WIDGET_CATALOG,
    WIDGET_DEFAULT_GEOMETRY,
    bar_display_name,
    current_theme_name,
    desktop_preview_image,
    format_percent,
    geom_to_fraction,
    list_bar_styles,
    list_cursor_themes,
    list_font_families,
    list_gtk_themes,
    list_icon_themes,
    list_on_path,
    list_wallpapers,
    normalize_font,
    parse_eww_geometry,
    primary_screen_size,
    resolve_wallpaper,
    spec_to_fractions,
    theme_preview_image,
    visible_bar_ids,
    widget_ids_from_prefs,
)
from hypraesthetic.export_theme import generate_from_wallpaper
from hypraesthetic.paths import layouts_dir
from hypraesthetic.doctor import Doctor
from hypraesthetic.install_theme import ThemeInstaller
from hypraesthetic.prefs import Prefs
from hypraesthetic.preset import prepare_preset_switch
from hypraesthetic.store import ThemeStore
from hypraesthetic_gui.dirty import bind_dirty_apply
from hypraesthetic_gui.preview import (
    FILM_HEIGHT,
    FILM_WIDTH,
    HERO_HEIGHT,
    HERO_WIDTH,
    PRESET_HEIGHT,
    PRESET_WIDTH,
    cover_pixbuf,
    load_static_pixbuf,
    preview_widget,
)

CSS = b"""
.ha-tile {
  padding: 0;
  border-radius: 14px;
  background-color: alpha(@card_bg_color, 0.72);
  border: 2px solid transparent;
}
.ha-tile.selected {
  background-color: alpha(@accent_bg_color, 0.55);
  border-color: @accent_color;
}
.ha-tile:hover {
  border-color: alpha(@accent_color, 0.55);
}
.ha-hero .ha-preview {
  min-width: 640px;
  min-height: 360px;
}
.ha-filmstrip .ha-preview {
  min-width: 160px;
  min-height: 90px;
}
.ha-tile-title {
  padding: 8px 12px 4px;
  font-weight: 600;
}
.ha-tile-sub {
  padding: 0 12px 10px;
  font-size: 0.85em;
}
.ha-chip {
  background-color: alpha(@accent_bg_color, 0.92);
  color: @accent_fg_color;
  border-radius: 8px;
  padding: 4px 10px;
  font-weight: 600;
}
.ha-canvas {
  background: #101010;
  border-radius: 10px;
}
.ha-stage {
  background: transparent;
}
"""

_CSS_DONE = False


def _install_css() -> None:
    global _CSS_DONE
    if _CSS_DONE:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _CSS_DONE = True


def _toast_overlay(child: Gtk.Widget) -> Adw.ToastOverlay:
    overlay = Adw.ToastOverlay()
    overlay.set_child(child)
    return overlay


def _status_label(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0, wrap=True)
    label.add_css_class("dim-label")
    return label


def _scrolled(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    scrolled = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_child(child)
    return scrolled


def _page(title: str, blurb: str) -> tuple[Adw.ToastOverlay, Gtk.Box]:
    _install_css()
    inner = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=14,
        margin_top=18,
        margin_bottom=24,
        margin_start=18,
        margin_end=18,
    )
    heading = Gtk.Label(label=title, xalign=0)
    heading.add_css_class("title-1")
    inner.append(heading)
    inner.append(_status_label(blurb))
    overlay = _toast_overlay(_scrolled(inner))
    return overlay, inner


def _form_page(title: str, blurb: str) -> tuple[Adw.ToastOverlay, Gtk.Box, Gtk.Button]:
    _install_css()
    form_box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=14,
        margin_top=18,
        margin_bottom=24,
        margin_start=18,
        margin_end=18,
    )
    heading = Gtk.Label(label=title, xalign=0)
    heading.add_css_class("title-1")
    form_box.append(heading)
    form_box.append(_status_label(blurb))
    column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
    column.append(_scrolled(form_box))
    apply_button = Gtk.Button(label="Apply changes")
    bar = Gtk.ActionBar()
    bar.pack_start(apply_button)
    column.append(bar)
    return _toast_overlay(column), form_box, apply_button


def _flow() -> Gtk.FlowBox:
    flow = Gtk.FlowBox(
        max_children_per_line=4,
        min_children_per_line=2,
        selection_mode=Gtk.SelectionMode.NONE,
        homogeneous=True,
        row_spacing=14,
        column_spacing=14,
        valign=Gtk.Align.START,
        hexpand=True,
    )
    return flow


def _preview_widget(image: Path | None, color: str | None = None) -> Gtk.Widget:
    return preview_widget(image, color)


def _tile(
    title: str,
    subtitle: str = "",
    image: Path | None = None,
    color: str | None = None,
    selected: bool = False,
    width: int | None = None,
    height: int | None = None,
    placeholder: str | None = None,
) -> Gtk.Button:
    button = Gtk.Button()
    button.add_css_class("ha-tile")
    button.add_css_class("flat")
    if selected:
        button.add_css_class("selected")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    if width is not None and height is not None:
        box.append(
            preview_widget(
                image,
                color,
                width=width,
                height=height,
                placeholder=placeholder,
            )
        )
    else:
        box.append(preview_widget(image, color, placeholder=placeholder))
    name = Gtk.Label(label=title, xalign=0, wrap=True)
    name.add_css_class("ha-tile-title")
    box.append(name)
    if subtitle:
        sub = Gtk.Label(label=subtitle, xalign=0, wrap=True)
        sub.add_css_class("ha-tile-sub")
        sub.add_css_class("dim-label")
        box.append(sub)
    button.set_child(box)
    return button


def _set_selected(buttons: dict[str, Gtk.Button], active: str) -> None:
    for key, button in buttons.items():
        if key == active:
            button.add_css_class("selected")
        else:
            button.remove_css_class("selected")


def _toast(overlay: Adw.ToastOverlay, title: str) -> None:
    overlay.add_toast(Adw.Toast(title=title))


def _palette_runner(cmd: list[str]) -> None:
    from hypraesthetic.export_theme import export_theme

    if len(cmd) >= 3 and cmd[1] == "export-theme":
        export_theme(str(cmd[2]))


def _apply(overlay: Adw.ToastOverlay, theme: str | None = None, components: list[str] | None = None, message: str = "Applied") -> bool:
    try:
        engine = ApplyEngine()
        if theme:
            result = engine.apply(theme, components=components)
        else:
            result = engine.reapply(components=components)
        if result.errors:
            _toast(overlay, result.errors[0])
            return False
        _toast(overlay, message)
        return True
    except Exception as exc:  # noqa: BLE001 - surface apply errors in the UI
        _toast(overlay, str(exc))
        return False


def _accent_color() -> str:
    try:
        pkg = ThemeCatalog().get(current_theme_name())
    except (KeyError, OSError, ValueError):
        return "#74b9ff"
    return (
        pkg.colors.get("waybar", {}).get("primary")
        or pkg.palette.get("base0D")
        or "#74b9ff"
    )


def _combo(options: list[str], current: str) -> tuple[Gtk.DropDown, list[str]]:
    values = list(options)
    if current and current not in values:
        values.insert(0, current)
    if not values:
        values = [current or ""]
    dropdown = Gtk.DropDown.new_from_strings(values)
    dropdown.set_enable_search(True)
    if current in values:
        dropdown.set_selected(values.index(current))
    return dropdown, values


def _selected_text(dropdown: Gtk.DropDown, values: list[str]) -> str:
    index = int(dropdown.get_selected())
    if 0 <= index < len(values):
        return values[index]
    return values[0] if values else ""


def _font_button(value: str) -> Gtk.FontDialogButton:
    button = Gtk.FontDialogButton(dialog=Gtk.FontDialog())
    text = normalize_font(value)
    if text:
        button.set_font_desc(Pango.FontDescription.from_string(text))
    return button


def _font_value(button: Gtk.FontDialogButton, fallback: str) -> str:
    desc = button.get_font_desc()
    raw = desc.to_string() if desc is not None else fallback
    return normalize_font(raw)


def presets_page() -> Gtk.Widget:
    overlay, box = _page(
        "Presets",
        "Click a theme to apply it. The active card uses the accent color.",
    )
    flow = _flow()
    buttons: dict[str, Gtk.Button] = {}
    active = current_theme_name()

    def apply_theme(name: str) -> None:
        prefs = prepare_preset_switch(Prefs.load())
        prefs.save()
        if _apply(overlay, theme=name, message=f"Applied {name}"):
            _set_selected(buttons, name)

    for pkg in ThemeCatalog().list():
        shot = desktop_preview_image(pkg)
        tile = _tile(
            pkg.display_name,
            pkg.description or pkg.name,
            image=shot,
            color=pkg.colors.get("waybar", {}).get("primary") or pkg.palette.get("base0D"),
            selected=pkg.name == active,
            width=PRESET_WIDTH,
            height=PRESET_HEIGHT,
            placeholder=None if shot is not None else "Desktop screenshot not added yet",
        )
        tile.connect("clicked", lambda _b, name=pkg.name: apply_theme(name))
        buttons[pkg.name] = tile
        flow.append(tile)
    undo_button = Gtk.Button(label="Undo last apply", halign=Gtk.Align.START)
    undo_button.connect("clicked", lambda *_a: _undo_last_apply(overlay, buttons))
    box.append(undo_button)
    box.append(flow)
    return overlay


def _undo_last_apply(overlay: Adw.ToastOverlay, buttons: dict[str, Gtk.Button]) -> None:
    from hypraesthetic import undo as undo_mod

    try:
        result = undo_mod.undo(ApplyEngine())
    except FileNotFoundError:
        _toast(overlay, "Nothing to undo")
        return
    except Exception as exc:  # noqa: BLE001 - surface undo errors in the UI
        _toast(overlay, str(exc))
        return
    if result.errors:
        _toast(overlay, result.errors[0])
        return
    _toast(overlay, f"Restored {result.theme}")
    _set_selected(buttons, result.theme)


def _paint(widget: Gtk.Widget, color: str, rules: str = "") -> None:
    if not color:
        return
    body = f"background: {color};"
    if rules:
        body = f"{body} {rules}"
    klass = f"ha-swatch-{abs(hash((color, rules))) % 10_000_000}"
    widget.add_css_class(klass)
    provider = Gtk.CssProvider()
    provider.load_from_data(f".{klass} {{ {body} }}".encode())
    widget.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _theme_bar_colors(pkg) -> tuple[str, str]:
    waybar = {}
    if pkg is not None:
        waybar = pkg.colors.get("waybar") or {}
    primary = str(waybar.get("primary") or "") or "#74b9ff"
    surface = str(waybar.get("surface") or "") or "#1a1a1a"
    return primary, surface


def _modules_for_style(style) -> tuple[list[str], list[str], list[str]]:
    if style is None:
        return [], [], []
    path = style.path / "config.jsonc"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return [], [], []
    return modules_for_bar(text)


def _bar_copy(style_id: str, style) -> tuple[str, str]:
    meta = ""
    if style is not None:
        raw = str(style.name or "").strip()
        if raw.casefold() != style_id.casefold():
            meta = raw
    return bar_display_name(style_id, meta)


def _bar_schematic(
    groups: tuple[list[str], list[str], list[str]],
    primary: str,
    surface: str,
) -> Gtk.ScrolledWindow:
    bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    bar.set_size_request(-1, 36)
    bar.set_hexpand(True)
    _paint(bar, surface, "border-radius: 8px; padding: 4px;")
    aligns = (Gtk.Align.START, Gtk.Align.CENTER, Gtk.Align.END)
    for align, names in zip(aligns, groups, strict=True):
        group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        group.set_hexpand(True)
        group.set_halign(align)
        group.set_valign(Gtk.Align.CENTER)
        for name in names:
            pill = Gtk.Label(label=name.rsplit("/", 1)[-1])
            pill.set_tooltip_text(name)
            _paint(pill, primary, "border-radius: 6px; padding: 1px 5px; font-size: 8px;")
            group.append(pill)
        bar.append(group)
    pane = Gtk.ScrolledWindow(hexpand=True, vexpand=False)
    pane.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    pane.set_propagate_natural_width(False)
    pane.set_child(bar)
    return pane


def _bar_tile(title: str, subtitle: str, schematic: Gtk.Widget, selected: bool) -> Gtk.Button:
    button = Gtk.Button()
    button.add_css_class("ha-tile")
    button.add_css_class("flat")
    if selected:
        button.add_css_class("selected")
    column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    column.append(schematic)
    name = Gtk.Label(label=title, xalign=0, wrap=True)
    name.add_css_class("ha-tile-title")
    column.append(name)
    if subtitle:
        sub = Gtk.Label(label=subtitle, xalign=0, wrap=True)
        sub.add_css_class("ha-tile-sub")
        sub.add_css_class("dim-label")
        column.append(sub)
    button.set_child(column)
    return button


def _set_selected_groups(groups: dict[str, list[Gtk.Button]], active: str) -> None:
    for key, items in groups.items():
        for button in items:
            if key == active:
                button.add_css_class("selected")
            else:
                button.remove_css_class("selected")


def bar_page() -> Gtk.Widget:
    overlay, box = _page(
        "Bar",
        "Every layout keeps the current theme colors. Click a tile to switch only the bar.",
    )
    prefs = Prefs.load()
    current_style = str(prefs.get("bar_style") or "default")
    if prefs.get("bar") == "none":
        current_style = "none"
    pkg = _safe_theme()
    if pkg is None or str(pkg.layout.get("bar") or "") == "none":
        preset_id = "none"
        preset_owner = current_theme_name() if pkg is None else pkg.display_name
    else:
        preset_id = str(pkg.layout.get("bar_style") or "").strip() or "none"
        preset_owner = pkg.display_name
    primary, surface = _theme_bar_colors(pkg)
    listed = list_bar_styles()
    styles = {style.id: style for style in listed}
    search = Gtk.SearchEntry(placeholder_text="Search extra bar layouts")

    def _flow_box() -> Gtk.FlowBox:
        return Gtk.FlowBox(
            max_children_per_line=5,
            min_children_per_line=1,
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=True,
            row_spacing=12,
            column_spacing=12,
            valign=Gtk.Align.START,
            hexpand=True,
        )

    preset_flow = _flow_box()
    builtin_flow = _flow_box()
    extra_flow = _flow_box()
    buttons: dict[str, list[Gtk.Button]] = {}
    needle = [""]

    def extra_visible(child: Gtk.FlowBoxChild) -> bool:
        button = child.get_child()
        hay = (button.get_name() if button is not None else "") or ""
        style_id = hay.split(" ", 1)[0] if hay else ""
        return bool(visible_bar_ids([(style_id, hay)], needle[0]))

    extra_flow.set_filter_func(extra_visible)

    def apply_style(style_id: str) -> None:
        loaded = Prefs.load()
        if style_id == "none":
            loaded.set("bar", "none")
        else:
            loaded.set("bar", "waybar")
            loaded.set("bar_style", style_id)
        loaded.save()
        if _apply(overlay, components=["waybar"], message=f"Bar: {style_id}"):
            _set_selected_groups(buttons, style_id)

    def on_search(entry: Gtk.SearchEntry) -> None:
        needle[0] = entry.get_text().strip().lower()
        extra_flow.invalidate_filter()

    search.connect("search-changed", on_search)

    def add_tile(parent: Gtk.FlowBox, style_id: str, title: str, subtitle: str) -> None:
        tile = _bar_tile(
            title,
            subtitle,
            _bar_schematic(_modules_for_style(styles.get(style_id)), primary, surface),
            style_id == current_style,
        )
        tile.set_name(f"{style_id} {title} {subtitle}")
        tile.connect("clicked", lambda _b, sid=style_id: apply_style(sid))
        buttons.setdefault(style_id, []).append(tile)
        parent.append(tile)

    preset_title, _preset_blurb = _bar_copy(preset_id, styles.get(preset_id))
    add_tile(preset_flow, preset_id, preset_title, f"Used by {preset_owner}")
    for style_id in ("none", "default", "compact", "a70", "cyberpunk"):
        title, blurb = _bar_copy(style_id, styles.get(style_id))
        add_tile(builtin_flow, style_id, title, blurb)
    for style in listed:
        if style.id in FIRST_PARTY_BAR_IDS:
            continue
        title, blurb = _bar_copy(style.id, style)
        add_tile(extra_flow, style.id, title, blurb)

    box.append(search)
    box.append(Gtk.Label(label="For this preset", xalign=0))
    box.append(preset_flow)
    box.append(Gtk.Label(label="Built-in styles", xalign=0))
    box.append(builtin_flow)
    box.append(_status_label("Type to browse extra Waybar layouts."))
    box.append(extra_flow)
    return overlay


def widgets_page() -> Gtk.Widget:
    overlay, box, apply_button = _form_page(
        "Widgets",
        "Choose overlay widgets, then save to apply them. Placement is per theme: switching presets restores that theme's layout, and Reset restores it too.",
    )
    prefs = Prefs.load()
    theme = current_theme_name()
    before = prefs.get("widgets_by_theme")
    prefs.adopt_legacy_widgets(theme)
    if prefs.get("widgets_by_theme") != before:
        prefs.save()
    enabled_ids = prefs.widgets_for(theme)
    if not enabled_ids:
        pkg = _safe_theme()
        if pkg is not None and pkg.widgets:
            enabled_ids = [str(item) for item in pkg.widgets]
        else:
            enabled_ids = [str(item) for item in (prefs.get("widgets") or [])]
    enabled = set(widget_ids_from_prefs(enabled_ids))
    switches: dict[str, Gtk.Switch] = {}
    for item in WIDGET_CATALOG:
        row = Adw.ActionRow(title=item["title"], subtitle=item["blurb"])
        switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=item["id"] in enabled)
        switches[item["id"]] = switch
        row.add_suffix(switch)
        row.set_activatable_widget(switch)
        box.append(row)
    dash = Gtk.CheckButton(label="Open the eww dashboard on login")
    dash.set_active(bool(prefs.get("dashboard")))
    box.append(dash)
    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    edit = Gtk.Button(label="Edit layout")
    reset = Gtk.Button(label="Reset placement")

    def selected_ids() -> list[str]:
        return [item["id"] for item in WIDGET_CATALOG if switches[item["id"]].get_active()]

    def collect() -> dict:
        return {"widgets": selected_ids(), "dashboard": dash.get_active()}

    snapshot = collect()
    refresh = bind_dirty_apply(apply_button, snapshot, collect)
    for switch in switches.values():
        switch.connect("notify::active", refresh)
    dash.connect("notify::active", refresh)

    def persist_and_apply(message: str) -> None:
        loaded = Prefs.load()
        ids = selected_ids()
        loaded.set_widgets_for(current_theme_name(), ids)
        loaded.set("widgets", ids)
        loaded.set("dashboard", dash.get_active())
        extras = list(loaded.get("extras") or [])
        if loaded.get("widgets") and "eww" not in extras:
            extras.append("eww")
        loaded.set("extras", extras)
        loaded.save()
        _apply(overlay, components=["eww"], message=message)
        snapshot.clear()
        snapshot.update(collect())
        refresh()

    apply_button.connect("clicked", lambda *_: persist_and_apply("Widgets applied"))
    edit.connect("clicked", lambda *_: _open_editor(overlay, selected_ids(), persist_and_apply))
    reset.connect("clicked", lambda *_: _reset_geometry(overlay))
    actions.append(edit)
    actions.append(reset)
    box.append(actions)
    return overlay


def _reset_geometry(overlay: Adw.ToastOverlay) -> None:
    theme = current_theme_name()
    prefs = Prefs.load()
    prefs.clear_geometry_for(theme)
    prefs.save()
    _apply(overlay, theme=theme, components=["eww"], message="Placement reset to theme layout")


def _open_editor(overlay: Adw.ToastOverlay, widget_ids: list[str], persist) -> None:
    if not widget_ids:
        _toast(overlay, "Turn on at least one widget first")
        return
    parent = overlay.get_root()
    editor = WidgetEditor(parent if isinstance(parent, Gtk.Window) else None, widget_ids, overlay, persist)
    editor.present()


class WidgetEditor(Adw.Window):
    _HANDLE = 14

    def __init__(self, parent: Gtk.Window | None, widget_ids: list[str], overlay: Adw.ToastOverlay, persist):
        super().__init__(title="Edit widget layout")
        self.set_default_size(1100, 720)
        self.set_modal(True)
        if parent is not None:
            self.set_transient_for(parent)
        self._overlay = overlay
        self._persist = persist
        self._ids = widget_ids
        self._titles = {item["id"]: item["title"] for item in WIDGET_CATALOG}
        self._screen = primary_screen_size()
        self._wallpaper = resolve_wallpaper(
            pkg=_safe_theme(),
            override=str(Prefs.load().get("wallpaper") or ""),
            live=True,
        )
        self._pixbuf: GdkPixbuf.Pixbuf | None = None
        self._pixbuf_key: tuple[str, int, int] | None = None
        self._entries: dict[str, dict[str, Gtk.Entry]] = {}
        self._fracs: dict[str, list[float]] = {}
        self._raw: dict[str, dict[str, str]] = {}
        self._resized: set[str] = set()
        self._selected = widget_ids[0]
        self._drag: dict[str, object] | None = None
        self._syncing = False
        self._accent = _hex_rgb(_accent_color())
        geom = self._load_geometry()
        for widget_id in widget_ids:
            spec = geom.get(widget_id) or dict(WIDGET_DEFAULT_GEOMETRY.get(widget_id) or {})
            cleaned = {key: str(spec.get(key) or "").strip().strip('"') for key in ("x", "y", "width", "height")}
            self._raw[widget_id] = cleaned
            self._fracs[widget_id] = list(spec_to_fractions(cleaned, self._screen))

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        save = Gtk.Button(label="Save layout")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        header.pack_start(save)
        toolbar.add_top_bar(header)

        split = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=16,
            margin_start=16,
            margin_end=16,
            margin_bottom=16,
        )
        stage_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True, vexpand=True)
        ratio = self._screen[0] / max(self._screen[1], 1)
        frame = Gtk.AspectFrame(obey_child=False, ratio=ratio, hexpand=True, vexpand=True)
        frame.add_css_class("ha-canvas")
        frame.set_overflow(Gtk.Overflow.HIDDEN)
        self._stage = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self._stage.add_css_class("ha-stage")
        self._stage.set_draw_func(self._draw)
        self._stage.set_cursor(Gdk.Cursor.new_from_name("grab"))
        drag = Gtk.GestureDrag()
        drag.set_button(1)
        drag.connect("drag-begin", self._on_begin)
        drag.connect("drag-update", self._on_update)
        drag.connect("drag-end", self._on_end)
        self._stage.add_controller(drag)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self._stage.add_controller(motion)
        frame.set_child(self._stage)
        stage_box.append(frame)
        caption = "Current wallpaper"
        if self._wallpaper is not None:
            caption = f"{self._wallpaper.name} · {self._screen[0]}×{self._screen[1]}"
        stage_box.append(_status_label(caption + ". Drag a widget to move it; drag the corner to resize."))
        split.append(stage_box)

        fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fields.set_size_request(300, -1)
        for widget_id in widget_ids:
            spec = self._raw[widget_id]
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            title = Gtk.Label(label=self._titles.get(widget_id, widget_id), xalign=0)
            title.add_css_class("heading")
            group.append(title)
            row = Gtk.Box(spacing=6)
            entries: dict[str, Gtk.Entry] = {}
            for key in ("x", "y", "width", "height"):
                column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                label = Gtk.Label(label=key, xalign=0)
                label.add_css_class("dim-label")
                entry = Gtk.Entry(text=spec.get(key) or "", width_chars=7, placeholder_text=key)
                entry.connect("changed", self._on_entry, widget_id, key)
                entries[key] = entry
                column.append(label)
                column.append(entry)
                row.append(column)
            self._entries[widget_id] = entries
            group.append(row)
            fields.append(group)
        split.append(_scrolled(fields))
        toolbar.set_content(split)
        self.set_content(toolbar)

    def _load_geometry(self) -> dict[str, dict[str, str]]:
        geom: dict[str, dict[str, str]] = {key: dict(value) for key, value in WIDGET_DEFAULT_GEOMETRY.items()}
        pkg = _safe_theme()
        yuck_paths = []
        if pkg is not None:
            yuck_paths.append(Path(pkg.root) / "eww" / "eww.yuck")
        yuck_paths.append(layouts_dir() / "default" / "eww" / "eww.yuck")
        for path in yuck_paths:
            if path.is_file():
                geom.update(parse_eww_geometry(path.read_text(encoding="utf-8")))
                break
        saved = Prefs.load().geometry_for(current_theme_name())
        for key, value in saved.items():
            geom[str(key)] = {str(k): str(v).strip('"') for k, v in value.items()}
        return geom

    def _canvas(self) -> tuple[int, int]:
        return max(1, self._stage.get_width()), max(1, self._stage.get_height())

    def _rect_px(self, widget_id: str, canvas: tuple[int, int] | None = None) -> tuple[float, float, float, float]:
        cw, ch = canvas or self._canvas()
        x, y, width, height = self._fracs[widget_id]
        return x * cw, y * ch, max(width * cw, 36), max(height * ch, 28)

    def _hit(self, px: float, py: float) -> tuple[str, str] | None:
        handle = self._HANDLE
        ordered = [self._selected] + [item for item in reversed(self._ids) if item != self._selected]
        for widget_id in ordered:
            x, y, width, height = self._rect_px(widget_id)
            if x + width - handle <= px <= x + width and y + height - handle <= py <= y + height:
                return widget_id, "resize"
            if x <= px <= x + width and y <= py <= y + height:
                return widget_id, "move"
        return None

    def _on_motion(self, _controller, x: float, y: float) -> None:
        hit = self._hit(x, y)
        name = "default"
        if hit is not None:
            name = "nwse-resize" if hit[1] == "resize" else "grab"
        self._stage.set_cursor(Gdk.Cursor.new_from_name(name))

    def _on_begin(self, gesture: Gtk.GestureDrag, x: float, y: float) -> None:
        hit = self._hit(x, y)
        if hit is None:
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            self._drag = None
            return
        widget_id, mode = hit
        self._selected = widget_id
        self._drag = {"id": widget_id, "mode": mode, "start": list(self._fracs[widget_id])}
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self._stage.set_cursor(Gdk.Cursor.new_from_name("grabbing" if mode == "move" else "nwse-resize"))
        self._stage.queue_draw()

    def _on_update(self, _gesture, dx: float, dy: float) -> None:
        if not self._drag:
            return
        widget_id = str(self._drag["id"])
        start = list(self._drag["start"])  # type: ignore[arg-type]
        cw, ch = self._canvas()
        x, y, width, height = start
        if self._drag["mode"] == "resize":
            width = max(0.04, min(0.95, start[2] + float(dx) / cw))
            height = max(0.04, min(0.95, start[3] + float(dy) / ch))
            self._resized.add(widget_id)
        else:
            x = start[0] + float(dx) / cw
            y = start[1] + float(dy) / ch
        x, y = _clamp_pos(x, y, width, height)
        self._fracs[widget_id] = [x, y, width, height]
        self._write_entries(widget_id)
        self._stage.queue_draw()

    def _on_end(self, *_args) -> None:
        self._drag = None
        self._stage.set_cursor(Gdk.Cursor.new_from_name("grab"))

    def _on_entry(self, entry: Gtk.Entry, widget_id: str, key: str) -> None:
        if self._syncing:
            return
        text = entry.get_text().strip()
        self._raw[widget_id][key] = text
        if not any(ch.isdigit() for ch in text):
            return
        axis = "x" if key in {"x", "width"} else "y"
        value = geom_to_fraction(text, axis, self._screen)
        idx = {"x": 0, "y": 1, "width": 2, "height": 3}[key]
        self._fracs[widget_id][idx] = value
        self._stage.queue_draw()

    def _write_entries(self, widget_id: str) -> None:
        x, y, width, height = self._fracs[widget_id]
        self._syncing = True
        self._entries[widget_id]["x"].set_text(format_percent(x))
        self._entries[widget_id]["y"].set_text(format_percent(y))
        if widget_id in self._resized:
            self._entries[widget_id]["width"].set_text(str(max(1, round(width * self._screen[0]))))
            self._entries[widget_id]["height"].set_text(str(max(1, round(height * self._screen[1]))))
        self._syncing = False

    def _cover_pixbuf(self, width: int, height: int) -> GdkPixbuf.Pixbuf | None:
        if self._wallpaper is None or not self._wallpaper.is_file():
            return None
        key = (str(self._wallpaper), width, height)
        if self._pixbuf is not None and self._pixbuf_key == key:
            return self._pixbuf
        src = load_static_pixbuf(self._wallpaper)
        if src is None:
            return None
        cropped = cover_pixbuf(src, width, height)
        if cropped is None:
            return None
        self._pixbuf = cropped
        self._pixbuf_key = key
        return self._pixbuf

    def _draw(self, _area, cr, width: int, height: int) -> None:
        cw, ch = max(1, width), max(1, height)
        cr.set_source_rgb(0.06, 0.06, 0.06)
        cr.rectangle(0, 0, cw, ch)
        cr.fill()
        pixbuf = self._cover_pixbuf(int(cw), int(ch))
        if pixbuf is not None:
            Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
            cr.paint()
        cr.set_source_rgba(1, 1, 1, 0.08)
        cr.set_line_width(1)
        for i in range(1, 10):
            cr.move_to(i * cw / 10, 0)
            cr.line_to(i * cw / 10, ch)
            cr.move_to(0, i * ch / 10)
            cr.line_to(cw, i * ch / 10)
        cr.stroke()
        red, green, blue = self._accent
        canvas = (int(cw), int(ch))
        for widget_id in self._ids:
            x, y, box_w, box_h = self._rect_px(widget_id, canvas)
            selected = widget_id == self._selected
            cr.set_source_rgba(red, green, blue, 0.55 if selected else 0.38)
            _round_rect(cr, x, y, box_w, box_h, 8)
            cr.fill()
            cr.set_source_rgba(red, green, blue, 0.95 if selected else 0.7)
            cr.set_line_width(2 if selected else 1)
            _round_rect(cr, x, y, box_w, box_h, 8)
            cr.stroke()
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Sans")
            cr.set_font_size(12)
            label = self._titles.get(widget_id, widget_id)
            cr.move_to(x + 8, y + 18)
            cr.show_text(label)
            handle = self._HANDLE
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.rectangle(x + box_w - handle, y + box_h - handle, handle, handle)
            cr.fill()

    def _save(self, *_args) -> None:
        geom: dict[str, dict[str, str]] = {}
        for widget_id, entries in self._entries.items():
            spec = {key: entry.get_text().strip() for key, entry in entries.items() if entry.get_text().strip()}
            if "y" in spec:
                spec["y"] = _clamp_y_text(spec["y"], spec.get("height") or "0", self._screen)
            if spec:
                geom[widget_id] = spec
        prefs = Prefs.load()
        prefs.set_geometry_for(current_theme_name(), geom)
        prefs.save()
        self._persist("Layout applied")
        self.close()


def _clamp_y_text(y_text: str, height_text: str, screen: tuple[int, int]) -> str:
    y = geom_to_fraction(y_text or "0", "y", screen)
    height = geom_to_fraction(height_text or "0", "y", screen)
    clamped = max(y, 0.0)
    if clamped + height > 1:
        clamped = max(0.0, 1.0 - height)
    if clamped == y:
        return y_text
    return format_percent(clamped)


def _clamp_pos(x: float, y: float, width: float, height: float) -> tuple[float, float]:
    min_vis = 0.02
    x = min(max(x, -width + min_vis), 1.0 - min_vis)
    y = min(max(y, -height + min_vis), 1.0 - min_vis)
    return x, y


def _round_rect(cr, x: float, y: float, width: float, height: float, radius: float) -> None:
    radius = min(radius, width / 2, height / 2)
    cr.new_path()
    cr.arc(x + width - radius, y + radius, radius, -1.5708, 0)
    cr.arc(x + width - radius, y + height - radius, radius, 0, 1.5708)
    cr.arc(x + radius, y + height - radius, radius, 1.5708, 3.1416)
    cr.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
    cr.close_path()


def _hex_rgb(value: str) -> tuple[float, float, float]:
    raw = value.lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) < 6:
        return 0.45, 0.72, 1.0
    return int(raw[0:2], 16) / 255.0, int(raw[2:4], 16) / 255.0, int(raw[4:6], 16) / 255.0


def _safe_theme():
    try:
        return ThemeCatalog().get(current_theme_name())
    except (KeyError, OSError, ValueError):
        return None


def fonts_page() -> Gtk.Widget:
    overlay, box, apply_button = _form_page(
        "Fonts",
        "These pickers list fonts installed on this system, the same way GNOME Tweaks does.",
    )
    prefs = Prefs.load()
    fonts = dict(prefs.get("fonts") or {})
    buttons = {
        "ui": _font_button(str(fonts.get("ui") or "Adwaita Sans 11")),
        "bar": _font_button(str(fonts.get("bar") or "JetBrainsMono Nerd Font 11")),
        "terminal": _font_button(str(fonts.get("terminal") or "JetBrainsMono Nerd Font")),
    }
    families = list_font_families()
    for key, title in (("ui", "Interface"), ("bar", "Bar"), ("terminal", "Terminal")):
        row = Adw.ActionRow(title=title, subtitle=f"{len(families)} families discovered" if families else "fc-list found no fonts")
        row.add_suffix(buttons[key])
        box.append(row)

    def collect() -> dict:
        return {
            "ui": _font_value(buttons["ui"], "Adwaita Sans 11"),
            "bar": _font_value(buttons["bar"], "JetBrainsMono Nerd Font 11"),
            "terminal": _font_value(buttons["terminal"], "JetBrainsMono Nerd Font"),
        }

    snapshot = collect()
    refresh = bind_dirty_apply(apply_button, snapshot, collect)
    for button in buttons.values():
        button.connect("notify::font-desc", refresh)

    def persist(_button: Gtk.Button) -> None:
        loaded = Prefs.load()
        current = collect()
        loaded.set(
            "fonts",
            {
                "ui": current["ui"],
                "bar": current["bar"],
                "terminal": current["terminal"],
                "icons": str(loaded.get("fonts.icons") or "Papirus-Dark"),
            },
        )
        loaded.save()
        _apply(overlay, components=["gtk", "kitty", "waybar"], message="Fonts applied")
        snapshot.clear()
        snapshot.update(collect())
        refresh()

    apply_button.connect("clicked", persist)
    return overlay


def apps_page() -> Gtk.Widget:
    overlay, box, apply_button = _form_page("Apps", "Super+E file manager, Super+T terminal, Super+B browser.")
    groups = [
        ("file_manager", "File manager"),
        ("terminal", "Terminal"),
        ("launcher", "Launcher"),
        ("browser", "Browser"),
    ]
    dropdowns: dict[str, tuple[Gtk.DropDown, list[str]]] = {}
    prefs = Prefs.load()
    for key, title in groups:
        options = APP_CANDIDATES[key]
        current = str(prefs.get(key) or options[0])
        row = Adw.ActionRow(title=title)
        dropdown, values = _combo(list_on_path(options, current=current), current)
        dropdowns[key] = (dropdown, values)
        row.add_suffix(dropdown)
        box.append(row)

    def collect() -> dict:
        return {key: _selected_text(dropdown, values) for key, (dropdown, values) in dropdowns.items()}

    snapshot = collect()
    refresh = bind_dirty_apply(apply_button, snapshot, collect)
    for dropdown, _values in dropdowns.values():
        dropdown.connect("notify::selected", refresh)

    def persist(_button: Gtk.Button) -> None:
        loaded = Prefs.load()
        for key, value in collect().items():
            loaded.set(key, value)
        loaded.save()
        _apply(overlay, components=["hyprland"], message="Apps applied")
        snapshot.clear()
        snapshot.update(collect())
        refresh()

    apply_button.connect("clicked", persist)
    return overlay


def _look_spin(value: object, lower: float, upper: float, fallback: int) -> Gtk.SpinButton:
    try:
        current = int(value)
    except (TypeError, ValueError):
        current = fallback
    spin = Gtk.SpinButton.new_with_range(lower, upper, 1)
    spin.set_value(current)
    return spin


def look_page() -> Gtk.Widget:
    overlay, box, apply_button = _form_page(
        "Look",
        "Wallpaper tiles apply immediately. GTK, icons, and Hyprland need Apply changes.",
    )
    prefs = Prefs.load()
    current_wall = str(prefs.get("wallpaper") or "")
    live_wall = resolve_wallpaper(pkg=_safe_theme(), override=current_wall, live=True)
    wall_buttons: dict[str, Gtk.Button] = {}
    hero = Gtk.Box(halign=Gtk.Align.START)
    hero.add_css_class("ha-hero")

    def show_hero(path: Path | None) -> None:
        while child := hero.get_first_child():
            hero.remove(child)
        if path is not None:
            hero.append(preview_widget(path, width=HERO_WIDTH, height=HERO_HEIGHT))
            return
        missing = Gtk.Label(label="No wallpaper", xalign=0)
        missing.set_size_request(HERO_WIDTH, HERO_HEIGHT)
        hero.append(missing)

    def apply_wallpaper(path: Path) -> None:
        loaded = Prefs.load()
        loaded.set("wallpaper", str(path))
        loaded.save()
        if _apply(overlay, components=["wallpaper"], message=f"Wallpaper: {path.name}"):
            _set_selected(wall_buttons, str(path))
            show_hero(path)

    def is_current(image: Path) -> bool:
        if live_wall is not None:
            try:
                return image.resolve() == live_wall.resolve()
            except OSError:
                return image.name == live_wall.name
        return str(image) == current_wall or image.name == Path(current_wall).name

    box.append(Gtk.Label(label="Wallpaper", xalign=0, css_classes=["heading"]))
    show_hero(live_wall)
    box.append(hero)

    strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    strip.add_css_class("ha-filmstrip")
    for image in list_wallpapers():
        tile = _tile(
            image.stem.replace("_", " "),
            image.name,
            image=image,
            selected=is_current(image),
            width=FILM_WIDTH,
            height=FILM_HEIGHT,
        )
        tile.connect("clicked", lambda _b, path=image: apply_wallpaper(path))
        wall_buttons[str(image)] = tile
        strip.append(tile)
    film = Gtk.ScrolledWindow(hexpand=True, vexpand=False)
    film.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    film.set_propagate_natural_height(True)
    film.set_child(strip)
    box.append(film)

    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.START)
    browse = Gtk.Button(label="Browse wallpaper…")
    browse.connect("clicked", lambda *_: _browse_wallpaper(overlay, apply_wallpaper))
    actions.append(browse)
    if shutil.which("wallust") or shutil.which("matugen"):
        generate = Gtk.Button(label="Generate palette from wallpaper")
        generate.add_css_class("flat")

        def on_generate(_button: Gtk.Button) -> None:
            name = f"{current_theme_name()}-export"
            try:
                message = generate_from_wallpaper(
                    name,
                    which=shutil.which,
                    runner=_palette_runner,
                )
            except Exception as exc:  # noqa: BLE001 - surface generator errors in the UI
                _toast(overlay, str(exc))
                return
            _toast(overlay, message)

        generate.connect("clicked", on_generate)
        actions.append(generate)
    box.append(actions)

    gtk_themes = list_gtk_themes()
    icon_themes = list_icon_themes()
    cursor_themes = list_cursor_themes()
    gtk_drop, gtk_values = _combo(gtk_themes, str(prefs.get("gtk_theme") or ""))
    icon_drop, icon_values = _combo(icon_themes, str(prefs.get("icon_theme") or ""))
    cursor_options = [""] + [name for name in cursor_themes if name]
    cursor_drop, cursor_values = _combo(cursor_options, str(prefs.get("cursor_theme") or ""))
    gtk_row = Adw.ActionRow(title="GTK theme", subtitle=f"{len(gtk_themes)} themes found")
    gtk_row.add_suffix(gtk_drop)
    icon_row = Adw.ActionRow(title="Icon theme", subtitle=f"{len(icon_themes)} icon sets found")
    icon_row.add_suffix(icon_drop)
    cursor_row = Adw.ActionRow(title="Cursor theme", subtitle=f"{len(cursor_themes)} cursor themes found")
    cursor_row.add_suffix(cursor_drop)

    extras = list(prefs.get("extras") or [])
    hypr_row = Adw.ActionRow(title="Hyprwave", subtitle="Audio visualizer follows the active theme")
    hypr_switch = Gtk.Switch(valign=Gtk.Align.CENTER, active="hyprwave" in extras)
    hypr_row.add_suffix(hypr_switch)
    hypr_row.set_activatable_widget(hypr_switch)

    gaps_in = _look_spin(prefs.get("hypr.gaps_in"), 0, 200, 5)
    gaps_out = _look_spin(prefs.get("hypr.gaps_out"), 0, 200, 7)
    border = _look_spin(prefs.get("hypr.border_size"), 0, 20, 1)
    rounding = _look_spin(prefs.get("hypr.rounding"), 0, 50, 10)
    hypr_rows = (
        ("Gaps in", gaps_in),
        ("Gaps out", gaps_out),
        ("Border", border),
        ("Rounding", rounding),
    )

    def collect() -> dict:
        return {
            "gtk_theme": _selected_text(gtk_drop, gtk_values),
            "icon_theme": _selected_text(icon_drop, icon_values),
            "cursor_theme": _selected_text(cursor_drop, cursor_values),
            "hyprwave": hypr_switch.get_active(),
            "gaps_in": int(gaps_in.get_value()),
            "gaps_out": int(gaps_out.get_value()),
            "border_size": int(border.get_value()),
            "rounding": int(rounding.get_value()),
        }

    snapshot = collect()
    refresh = bind_dirty_apply(apply_button, snapshot, collect)
    for dropdown in (gtk_drop, icon_drop, cursor_drop):
        dropdown.connect("notify::selected", refresh)
    hypr_switch.connect("notify::active", refresh)
    for spin in (gaps_in, gaps_out, border, rounding):
        spin.connect("notify::value", refresh)

    def persist(_button: Gtk.Button) -> None:
        loaded = Prefs.load()
        loaded.set("gtk_theme", _selected_text(gtk_drop, gtk_values))
        loaded.set("icon_theme", _selected_text(icon_drop, icon_values))
        loaded.set("cursor_theme", _selected_text(cursor_drop, cursor_values))
        loaded.set("hypr.gaps_in", int(gaps_in.get_value()))
        loaded.set("hypr.gaps_out", int(gaps_out.get_value()))
        loaded.set("hypr.border_size", int(border.get_value()))
        loaded.set("hypr.rounding", int(rounding.get_value()))
        extra = list(loaded.get("extras") or [])
        if hypr_switch.get_active():
            if "hyprwave" not in extra:
                extra.append("hyprwave")
        else:
            extra = [item for item in extra if item != "hyprwave"]
        loaded.set("extras", extra)
        loaded.save()
        components = ["gtk", "hyprland"]
        if hypr_switch.get_active():
            components.append("hyprwave")
        _apply(overlay, components=components, message="Look applied")
        snapshot.clear()
        snapshot.update(collect())
        refresh()

    apply_button.connect("clicked", persist)

    box.append(Gtk.Label(label="GTK and icons", xalign=0, css_classes=["heading"]))
    theme_name = current_theme_name()
    gtk_name = str(prefs.get("gtk_theme") or "")
    if theme_name and theme_name not in gtk_name:
        box.append(_status_label("GTK and icons are picked independently of the preset palette."))
    box.append(gtk_row)
    box.append(icon_row)
    box.append(cursor_row)
    box.append(hypr_row)
    box.append(Gtk.Label(label="Hyprland", xalign=0, css_classes=["heading"]))
    for title, spin in hypr_rows:
        row = Adw.ActionRow(title=title)
        row.add_suffix(spin)
        box.append(row)
    return overlay


def _browse_wallpaper(overlay: Adw.ToastOverlay, apply_wallpaper) -> None:
    dialog = Gtk.FileDialog(title="Choose wallpaper")
    filt = Gtk.FileFilter()
    filt.set_name("Images")
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif"):
        filt.add_pattern(pattern)
    dialog.set_default_filter(filt)
    window = overlay.get_root()

    def done(source, result) -> None:
        try:
            file = source.open_finish(result)
        except Exception:  # noqa: BLE001
            return
        if file is None:
            return
        path = Path(file.get_path() or "")
        if path.is_file():
            apply_wallpaper(path)

    dialog.open(window if isinstance(window, Gtk.Window) else None, None, done)


def store_page() -> Gtk.Widget:
    overlay, box = _page(
        "Store",
        "Type a name, site/theme, or git URL. Builtin themes apply in place; remote themes clone into your local store and apply.",
    )
    search_row = Gtk.Box(spacing=8)
    entry = Gtk.Entry(placeholder_text="hypraesthetic/toji or https://github.com/you/theme.git", hexpand=True)
    add = Gtk.Button(label="Add to desktop")
    add.add_css_class("suggested-action")
    search_row.append(entry)
    search_row.append(add)
    box.append(search_row)
    results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.append(results)

    def render(query: str = "") -> None:
        while child := results.get_first_child():
            results.remove(child)
        text = query.strip()
        if not text:
            results.append(
                _status_label(
                    "Builtin presets are on the Presets page. Paste a git URL or type to search the index."
                )
            )
            return
        try:
            hits = ThemeStore().search(text)
        except Exception as exc:  # noqa: BLE001
            _toast(overlay, str(exc))
            return
        if not hits:
            results.append(_status_label("No matching themes in the store index."))
            return
        for item in hits:
            row = Gtk.Box(spacing=8)
            image = None
            if not item.is_remote:
                try:
                    image = theme_preview_image(ThemeCatalog().get(item.name))
                except (KeyError, OSError, ValueError):
                    image = None
            if image is not None:
                row.append(_preview_widget(image))
            title = Gtk.Label(label=item.display_name, xalign=0, hexpand=True)
            row.append(title)
            action = Gtk.Button(label="Install" if item.is_remote else "Apply")
            action.connect(
                "clicked",
                lambda _b, entry=item, current=text: _store_install(entry, overlay, render, current),
            )
            row.append(action)
            results.append(row)

    def submit(*_args: object) -> None:
        render(entry.get_text().strip())

    add.connect("clicked", submit)
    entry.connect("activate", submit)
    render("")
    return overlay


def _store_install(entry, overlay: Adw.ToastOverlay, refresh, query: str) -> None:
    try:
        if entry.is_remote:
            pkg = ThemeInstaller().install(entry.source)
            ApplyEngine().apply(pkg.name)
            _toast(overlay, f"Installed {pkg.display_name}")
        else:
            ApplyEngine().apply(entry.name)
            _toast(overlay, f"Applied {entry.display_name}")
        refresh(query)
    except Exception as exc:  # noqa: BLE001
        _toast(overlay, str(exc))


def doctor_page() -> Gtk.Widget:
    overlay, box = _page("Doctor", "Required and optional packages for this desktop.")
    report = Doctor().run()
    for check in report.checks:
        status = "OK" if check.ok else ("required missing" if check.required else "optional missing")
        row = Adw.ActionRow(title=check.friendly or check.id, subtitle=f"{status}: {check.detail}")
        if hasattr(row, "add_css_class"):
            if check.ok:
                row.add_css_class("success")
            elif check.required:
                row.add_css_class("error")
            else:
                row.add_css_class("warning")
        box.append(row)
    missing = report.missing_ids()
    label = "Nothing to install" if not missing else f"Install missing ({', '.join(missing)})"
    repair = Gtk.Button(label=label, halign=Gtk.Align.START)
    repair.add_css_class("suggested-action")

    def on_repair(*_args: object) -> None:
        if not report.missing_ids():
            _toast(overlay, "Nothing missing")
            return
        __import__("subprocess").Popen(["ha-theme", "install", "--mode", "automatic", "--yes"])

    repair.connect("clicked", on_repair)
    box.append(repair)
    return overlay
