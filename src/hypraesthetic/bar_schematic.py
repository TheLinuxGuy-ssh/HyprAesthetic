"""Read waybar jsonc module groups for the bar schematic."""

from __future__ import annotations

import json
import re

# Same `,` before `}` / `]` cleanup as sanitize_waybar_config. The full
# sanitizer also rewrites clicks and drops modules, so the schematic only
# borrows this step after comments are gone.
_TRAILING_COMMA_RE = re.compile(r",\s*([\]}])")


def modules_for_bar(config_text: str) -> tuple[list[str], list[str], list[str]]:
    """Left, center, right module names from a waybar jsonc string."""
    try:
        data = json.loads(_TRAILING_COMMA_RE.sub(r"\1", _strip_jsonc(config_text or "")))
    except (json.JSONDecodeError, ValueError, TypeError):
        return [], [], []
    if not isinstance(data, dict):
        return [], [], []
    return (
        _string_list(data.get("modules-left")),
        _string_list(data.get("modules-center")),
        _string_list(data.get("modules-right")),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _strip_jsonc(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    escape = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue
        out.append(ch)
        i += 1
    return "".join(out)
