"""Make Waybar CSS accents follow the active theme primary color."""

from __future__ import annotations

import re

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
DEFINE_RE = re.compile(r"@define-color\s+([A-Za-z0-9_-]+)\s+([^;]+);")
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
COLOR_PROP_RE = re.compile(
    r"(^|[\s;])color\s*:\s*([^;]+)",
    re.M | re.I,
)
FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*(?:\"[^\"]+\"|'[^']+')")
BG_PROP_RE = re.compile(
    r"(background(?:-color)?|border-color)\s*:\s*(#[0-9A-Fa-f]{3,8})",
    re.I,
)
BG_ANY_RE = re.compile(r"(background(?:-color)?)\s*:\s*([^;]+)", re.I)
ALPHA_RE = re.compile(r"alpha\s*\(\s*([^,]+)\s*,\s*([0-9.]+)", re.I)
LIGHT_FILL_RE = re.compile(r"@(?:foreground|fg|text|cream|cp-cream)\b", re.I)
PRIMARY_FILL_RE = re.compile(
    r"@(?:primary|red|love|gold|accent|iris|foam|rose|pine|highlight|yellow|orange|cp-orange|cp-red)\b",
    re.I,
)
ON_FILL_TEXT = {"@background", "@bg", "@base", "@primary_fg"}
THEME_VALUE_RE = re.compile(
    r"@(?:background|foreground|primary|surface|border)|alpha\s*\(",
    re.I,
)
SOLID_ACCENT_BG_RE = re.compile(
    r"background(?:-color)?\s*:\s*@(?:primary|red|love|gold|accent|iris|foam|"
    r"rose|pine|highlight|yellow|orange|cp-orange|cp-red)\b",
    re.I,
)
OPAQUE_ALPHA_BG_RE = re.compile(
    r"background(?:-color)?\s*:\s*alpha\(\s*@(?:primary|red|love|gold|accent)\s*,\s*"
    r"(?:1(?:\.0+)?|0?\.(?:[6-9]\d*))\s*\)",
    re.I,
)

BG_NAMES = {"bg", "background", "base"}
FG_NAMES = {"fg", "foreground", "cream", "text", "cp-cream"}
MUTED_NAMES = {"muted", "subtle", "foreground_muted"}
SURFACE_NAMES = {"grey", "gray", "grey2", "ia1", "blink-fg", "cp-gray", "overlay"}
BORDER_NAMES = {"border", "border-inactive_ws"}
ACCENT_NAMES = {
    "red",
    "rd1",
    "orange",
    "accent",
    "magenta",
    "cyan",
    "peach",
    "love",
    "gold",
    "rose",
    "pine",
    "foam",
    "iris",
    "highlight",
    "highlighthigh",
    "cp-orange",
    "cp-red",
    "primary",
    "yellow",
    "pink",
}
STRUCTURAL_ACCENT_NAMES = {"hover_bg", "border-active_ws", "magenta-border", "fg2"}
ON_ACCENT_NAMES = {"hover_fg", "primary_fg"}
NAMED_TEXT = {
    "@fg",
    "@foreground",
    "@text",
    "@subtle",
    "@muted",
    "@love",
    "@gold",
    "@red",
    "@accent",
    "@foam",
    "@iris",
    "@rose",
    "@pine",
    "@highlight",
}
KNOWN_ACCENT_HEX = {
    "#df6124",
    "#fabd2f",
    "#fe8019",
    "#b8bb26",
    "#eb6f92",
    "#c4a7e7",
    "#9ccfd8",
    "#ebbcba",
    "#31748f",
    "#f6c177",
    "#ea9d34",
    "#d7827e",
    "#907aa9",
    "#83a598",
    "#d3869b",
    "#fb4934",
    "#b16286",
    "#ff9b71",
    "#e5a359",
    "#c14f3d",
    "#eb7087",
    "#a55555",
    "#665b32",
    "#c2a46d",
}
KNOWN_ACCENT_NORM = {item.lower() for item in KNOWN_ACCENT_HEX}
STALE_MODULE_IDS = {
    "custom-omarchy",
    "custom-omarchy-theme",
    "custom-omarchy-theme-set",
    "custom-voxtype",
    "custom-update",
    "custom-updatespacman",
    "custom-weather",
    "custom-gpu",
    "custom-gpu-usage",
    "custom-idle-indicator",
    "custom-notification-silencing-indicator",
    "custom-screenrecording-indicator",
}


def theme_waybar_css(css: str) -> str:
    text = css or ""
    if '@import "colors.css"' not in text:
        text = '@import "colors.css";\n' + text
    text = DEFINE_RE.sub(_rewrite_define, text)
    text = RULE_RE.sub(_drop_stale_selectors, text)
    accents = set(KNOWN_ACCENT_NORM)
    text = RULE_RE.sub(lambda match: _rewrite_rule(match, accents), text)
    text = RULE_RE.sub(lambda match: _replace_hexes_in_rule(match, accents), text)
    text = RULE_RE.sub(_ensure_contrast, text)
    text = re.sub(r"\}(?=\s*(?:#|@|\.|[A-Za-z]|/\*))", "}\n", text)
    return text


def set_bar_font(css: str, family: str) -> str:
    family = (family or "").strip()
    if not family:
        return css
    return FONT_FAMILY_RE.sub(f'font-family: "{family}"', css)


def _rewrite_define(match: re.Match[str]) -> str:
    original = match.group(1)
    value = match.group(2).strip()
    name = original.lower()
    if THEME_VALUE_RE.search(value):
        return match.group(0)
    hex_value = _norm_hex(value) if value.startswith("#") else ""
    known_accent = bool(hex_value and hex_value in KNOWN_ACCENT_NORM)
    chromatic = bool(value.startswith("#") and _is_chromatic(value))
    if name in BG_NAMES:
        return f"@define-color {original} @background;"
    if name in FG_NAMES:
        return f"@define-color {original} @foreground;"
    if name in MUTED_NAMES:
        return f"@define-color {original} @foreground_muted;"
    if name in SURFACE_NAMES:
        return f"@define-color {original} @surface;"
    if name in BORDER_NAMES:
        return f"@define-color {original} @border;"
    if name in ON_ACCENT_NAMES:
        return f"@define-color {original} @primary_fg;"
    if name in ACCENT_NAMES or known_accent or (name in STRUCTURAL_ACCENT_NAMES and chromatic):
        return f"@define-color {original} @primary;"
    return match.group(0)


def _rewrite_rule(match: re.Match[str], accents: set[str]) -> str:
    selector, body = match.group(1), match.group(2)
    lowered = selector.lower()
    if _is_status_rule(lowered) or not _is_accent_rule(lowered):
        return match.group(0)
    chromatic_bg = bool(SOLID_ACCENT_BG_RE.search(body) or OPAQUE_ALPHA_BG_RE.search(body))

    def replace_bg(item: re.Match[str]) -> str:
        nonlocal chromatic_bg
        hex_value = item.group(2)
        if _is_chromatic(hex_value):
            accents.add(_norm_hex(hex_value))
            chromatic_bg = True
            return f"{item.group(1)}: @primary"
        return item.group(0)

    body = BG_PROP_RE.sub(replace_bg, body)
    chromatic_bg = chromatic_bg or bool(
        SOLID_ACCENT_BG_RE.search(body) or OPAQUE_ALPHA_BG_RE.search(body)
    )

    def replace_color(item: re.Match[str]) -> str:
        prefix, value = item.group(1), item.group(2).strip()
        if chromatic_bg:
            return f"{prefix}color: @primary_fg"
        token, _amount = _token_and_amount(value)
        if token in NAMED_TEXT or value.lower() in NAMED_TEXT:
            return f"{prefix}color: @primary"
        if value.startswith("#") and _is_chromatic(value):
            accents.add(_norm_hex(value))
            return f"{prefix}color: @primary"
        rgb = _rgb(value) if value.startswith("#") else None
        if rgb and _luma(rgb) < 0.28:
            return f"{prefix}color: @primary_fg"
        if ".empty" in lowered and (".active" in lowered or ".focused" in lowered):
            return f"{prefix}color: @primary_fg"
        if ".active" in lowered or ".focused" in lowered:
            return f"{prefix}color: @primary"
        return item.group(0)

    body = COLOR_PROP_RE.sub(replace_color, body)
    return f"{selector}{{{body}}}"


def _replace_hexes_in_rule(match: re.Match[str], accents: set[str]) -> str:
    selector, body = match.group(1), match.group(2)
    if _is_status_rule(selector.lower()):
        return match.group(0)

    def repl(hex_match: re.Match[str]) -> str:
        value = _norm_hex(hex_match.group(0))
        if value in accents:
            return "@primary"
        return hex_match.group(0)

    return f"{selector}{{{HEX_RE.sub(repl, body)}}}"


def _ensure_contrast(match: re.Match[str]) -> str:
    selector, body = match.group(1), match.group(2)
    lowered = selector.lower()
    if _is_status_rule(lowered):
        return match.group(0)
    bg = BG_ANY_RE.search(body)
    color = COLOR_PROP_RE.search(body)
    empty_active = ".empty" in lowered and _is_accent_rule(lowered)
    if empty_active and color is not None and not _is_readable_on_fill(color.group(2).strip()):
        body = COLOR_PROP_RE.sub(lambda item: f"{item.group(1)}color: @primary_fg", body, count=1)
        return f"{selector}{{{body}}}"
    if bg is None or color is None:
        return match.group(0)
    kind = _fill_kind(bg.group(2))
    color_val = color.group(2).strip()
    if kind == "primary" and not _is_readable_on_fill(color_val):
        body = COLOR_PROP_RE.sub(lambda item: f"{item.group(1)}color: @primary_fg", body, count=1)
    elif kind == "light" and _is_accent_rule(selector.lower()):
        body = BG_ANY_RE.sub(lambda item: f"{item.group(1)}: @primary", body, count=1)
        body = COLOR_PROP_RE.sub(lambda item: f"{item.group(1)}color: @primary_fg", body, count=1)
    elif kind == "light" and not _is_readable_on_fill(color_val):
        body = COLOR_PROP_RE.sub(lambda item: f"{item.group(1)}color: @background", body, count=1)
    return f"{selector}{{{body}}}"


def _drop_stale_selectors(match: re.Match[str]) -> str:
    selector, body = match.group(1), match.group(2)
    parts = [item.strip() for item in selector.split(",") if item.strip()]
    kept = [item for item in parts if not _stale_selector(item)]
    if not kept:
        return ""
    if len(kept) == len(parts):
        return match.group(0)
    return f"{', '.join(kept)} {{{body}}}"


def _stale_selector(selector: str) -> bool:
    ids = re.findall(r"#([A-Za-z0-9_-]+)", selector)
    return any(item in STALE_MODULE_IDS for item in ids)


def _token_and_amount(value: str) -> tuple[str, float]:
    text = (value or "").strip()
    alpha = ALPHA_RE.search(text)
    if alpha is None:
        return text.lower(), 1.0
    try:
        amount = float(alpha.group(2))
    except ValueError:
        amount = 1.0
    return alpha.group(1).strip().lower(), amount


def _is_readable_on_fill(value: str) -> bool:
    token, amount = _token_and_amount(value)
    if amount < 0.7:
        return False
    return token in ON_FILL_TEXT


def _fill_kind(value: str) -> str:
    text = value.strip()
    if "transparent" in text.lower():
        return "none"
    token = text
    amount = 1.0
    alpha = ALPHA_RE.search(text)
    if alpha is not None:
        token = alpha.group(1)
        try:
            amount = float(alpha.group(2))
        except ValueError:
            amount = 1.0
    if amount < 0.5:
        return "none"
    if PRIMARY_FILL_RE.search(token):
        return "primary"
    if LIGHT_FILL_RE.search(token):
        return "light"
    return "other"


def _is_accent_rule(selector: str) -> bool:
    return any(token in selector for token in (".active", ".focused", ":hover", ".urgent"))


def _is_status_rule(selector: str) -> bool:
    return any(token in selector for token in (".warning", ".critical", ".error", ".charging", ".good"))


def _rgb(value: str) -> tuple[int, int, int] | None:
    raw = value.lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) >= 8:
        raw = raw[:6]
    if len(raw) != 6:
        return None
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return None


def _luma(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0


def _is_chromatic(value: str) -> bool:
    rgb = _rgb(value)
    if rgb is None:
        return False
    if max(rgb) - min(rgb) < 30:
        return False
    return _luma(rgb) >= 0.12


def _norm_hex(value: str) -> str:
    rgb = _rgb(value)
    if rgb is None:
        return value.lower()
    return "#{:02x}{:02x}{:02x}".format(*rgb)
