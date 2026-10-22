"""Simple {{dotted.key}} template renderer."""

from __future__ import annotations

import re
from pathlib import Path

VAR_RE = re.compile(r"\{\{([a-zA-Z0-9_.]+)\}\}")


def render_string(template: str, variables: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1).replace(".", "_")
        value = variables.get(key, match.group(0))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value

    return VAR_RE.sub(repl, template)


def render_file(template_path: Path, output_path: Path, variables: dict[str, str]) -> None:
    rendered = render_string(template_path.read_text(encoding="utf-8"), variables)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
