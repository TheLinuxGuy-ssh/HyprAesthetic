"""Strip Omarchy leftovers and other stale modules from Waybar jsonc."""

from __future__ import annotations

import re

DROP_MODULES = {
    "custom/omarchy",
    "custom/omarchy-theme",
    "custom/omarchy-theme-set",
    "custom/update",
    "custom/updatespacman",
    "custom/voxtype",
    "custom/idle-indicator",
    "custom/notification-silencing-indicator",
    "custom/screenrecording-indicator",
    "custom/weather",
    "custom/gpu",
}
CLICKS = (
    ("omarchy-launch-or-focus-tui btop", "kitty -e btop"),
    ("omarchy-launch-or-focus-tui wiremix", "pavucontrol"),
    ("omarchy-launch-wifi", "nm-connection-editor"),
    ("omarchy-launch-bluetooth", "blueman-manager"),
    ("omarchy-launch-audio", "pavucontrol"),
    ("omarchy-menu power", "wlogout"),
    ("omarchy-menu", "ha-theme gui"),
    ("omarchy-launch-floating-terminal-with-presentation omarchy-tz-select", "ha-theme gui"),
    ("omarchy-toggle-idle", "ha-theme gui"),
    ("omarchy-toggle-notification-silencing", "ha-theme gui"),
)
STALE_EXEC_RE = re.compile(
    r"omarchy-|\$OMARCHY_PATH|wttrbar|waybar-module-pacman-updates|gpu-usage-waybar"
)
OMARCHY_CLICK_RE = re.compile(
    r',?\s*"(?:on-click(?:-right|-middle)?|on-scroll-(?:up|down))"\s*:\s*"(?:\\.|[^"\\])*(?:omarchy-|\$OMARCHY_PATH|/omarchy/)(?:\\.|[^"\\])*"'
)
ARRAY_RE = re.compile(r'("modules(?:-(?:left|center|right))?"\s*:\s*)\[(.*?)\]', re.S)
KEY_RE = re.compile(r'"((?:custom|hyprland)/[^"]+)"\s*:')


def sanitize_waybar_config(text: str) -> str:
    text = (text or "").replace("\x00", "")
    for old, new in CLICKS:
        text = text.replace(old, new)
    text = OMARCHY_CLICK_RE.sub("", text)
    drop = set(DROP_MODULES)
    drop.update(_stale_custom_keys(text))
    for name in sorted(drop, key=len, reverse=True):
        text = _remove_key(text, name)
        text = re.sub(rf',?\s*"{re.escape(name)}"(?=\s*[,\]}}])', "", text)
    text = ARRAY_RE.sub(lambda match: _filter_array(match, drop), text)
    used = _used_modules(text)
    for name in sorted(_defined_custom_keys(text), key=len, reverse=True):
        if name not in used:
            text = _remove_key(text, name)
    text = re.sub(r'"class<org\.omarchy\.terminal>"\s*:\s*"[^"]*"\s*,?', "", text)
    text = re.sub(r"[\{\[]\s*,", lambda match: match.group(0)[0], text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*([\]}])", r"\1", text)
    return text


def _filter_array(match: re.Match[str], drop: set[str]) -> str:
    prefix, body = match.group(1), match.group(2)
    names = re.findall(r'"([^"]+)"', body)
    kept = [name for name in names if name not in drop]
    inner = ", ".join(f'"{name}"' for name in kept)
    return f"{prefix}[{inner}]"


def _used_modules(text: str) -> set[str]:
    used: set[str] = set()
    for match in ARRAY_RE.finditer(text):
        used.update(re.findall(r'"([^"]+)"', match.group(2)))
    return used


def _defined_custom_keys(text: str) -> set[str]:
    found: set[str] = set()
    for match in KEY_RE.finditer(text):
        key = match.group(1)
        if not key.startswith("custom/"):
            continue
        start = match.end()
        while start < len(text) and text[start] in " \t\n\r":
            start += 1
        if start < len(text) and text[start] == "{":
            found.add(key)
    return found


def _stale_custom_keys(text: str) -> set[str]:
    found: set[str] = set()
    for match in KEY_RE.finditer(text):
        key = match.group(1)
        if not key.startswith("custom/"):
            continue
        start = match.end()
        while start < len(text) and text[start] in " \t\n\r":
            start += 1
        if start >= len(text) or text[start] != "{":
            continue
        end = _object_end(text, start)
        if end < 0:
            continue
        body = text[start : end + 1]
        if STALE_EXEC_RE.search(body):
            found.add(key)
    return found


def _remove_key(text: str, key: str) -> str:
    needle = f'"{key}"'
    pieces: list[str] = []
    index = 0
    while True:
        found = text.find(needle, index)
        if found < 0:
            pieces.append(text[index:])
            break
        cursor = found + len(needle)
        while cursor < len(text) and text[cursor] in " \t\n\r":
            cursor += 1
        if cursor >= len(text) or text[cursor] != ":":
            pieces.append(text[index:cursor])
            index = cursor
            continue
        cursor += 1
        while cursor < len(text) and text[cursor] in " \t\n\r":
            cursor += 1
        if cursor < len(text) and text[cursor] == "{":
            end = _object_end(text, cursor)
            if end < 0:
                pieces.append(text[index:])
                break
            start = found
            prev = found - 1
            while prev >= index and text[prev] in " \t\n\r":
                prev -= 1
            if prev >= index and text[prev] == ",":
                start = prev
            pieces.append(text[index:start])
            index = end + 1
            continue
        end = cursor
        while end < len(text) and text[end] not in ",}":
            end += 1
        start = found
        prev = found - 1
        while prev >= index and text[prev] in " \t\n\r":
            prev -= 1
        if prev >= index and text[prev] == ",":
            start = prev
        pieces.append(text[index:start])
        index = end
    return "".join(pieces)


def _object_end(text: str, open_idx: int) -> int:
    depth = 0
    in_str = False
    escape = False
    index = open_idx
    while index < len(text):
        char = text[index]
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
            index += 1
            continue
        if char == '"':
            in_str = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1
