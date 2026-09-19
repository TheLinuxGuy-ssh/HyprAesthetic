#!/usr/bin/env python3
"""CI checks for theme.toml parsing and template rendering."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME_TOML = ROOT / "themes" / "cyberpunk" / "theme.toml"
VARS_FILE = Path("/tmp/ha_ci_vars.sh")


def flatten(data: dict, prefix: str = "") -> list[str]:
    lines: list[str] = []
    for key, value in data.items():
        flat_key = f"{prefix}{key}".replace("-", "_")
        if isinstance(value, dict):
            lines.extend(flatten(value, f"{flat_key}_"))
        elif isinstance(value, bool):
            lines.append(f'{flat_key}="{str(value).lower()}"')
        elif isinstance(value, (int, float)):
            lines.append(f"{flat_key}={value}")
        else:
            lines.append(f'{flat_key}="{value}"')
    return lines


def load_variables() -> dict[str, str]:
    variables: dict[str, str] = {}
    for line in VARS_FILE.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            variables[key] = value
    return variables


def render_template(template_path: Path, variables: dict[str, str]) -> str:
    template = template_path.read_text()

    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1).replace(".", "_")
        value = variables.get(var_name, match.group(0))
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        return value

    return re.sub(r"\{\{([a-zA-Z0-9_.]+)\}\}", replace_var, template)


def test_theme_toml() -> None:
    with THEME_TOML.open("rb") as handle:
        data = tomllib.load(handle)

    assert data["name"] == "cyberpunk"
    assert "colors" in data
    assert "components" in data
    print(f"Theme: {data['name']}")
    print(f"Colors: {len(data['colors'])}")
    print(f"Components: {data['components']}")


def test_variable_extraction() -> None:
    with THEME_TOML.open("rb") as handle:
        data = tomllib.load(handle)

    lines = flatten(data)
    VARS_FILE.write_text("\n".join(lines) + "\n")
    assert VARS_FILE.stat().st_size > 0
    print(f"Extracted {len(lines)} variables")


def test_waybar_template() -> None:
    rendered = render_template(
        ROOT / "themes" / "_template" / "waybar" / "colors.css.template",
        load_variables(),
    )
    assert "@define-color background" in rendered
    assert "#0d0d0d" in rendered
    print("Waybar template OK")


def test_hyprland_template() -> None:
    rendered = render_template(
        ROOT / "themes" / "_template" / "hypr" / "colors.conf.template",
        load_variables(),
    )
    assert "active_border = #74b9ff" in rendered
    print("Hyprland template OK")


def test_hyprwave_template() -> None:
    rendered = render_template(
        ROOT / "themes" / "_template" / "hyprwave" / "config.toml.template",
        load_variables(),
    )
    assert 'background = "#0d0d0d"' in rendered
    print("Hyprwave template OK")


def test_all_theme_tomls() -> None:
    for theme_file in sorted(ROOT.glob("themes/*/theme.toml")):
        if theme_file.parent.name == "_template":
            continue
        with theme_file.open("rb") as handle:
            data = tomllib.load(handle)
        assert "name" in data
        assert "colors" in data
        assert "components" in data
        print(f"OK: {data['name']}")


def main() -> int:
    test_theme_toml()
    test_variable_extraction()
    test_waybar_template()
    test_hyprland_template()
    test_hyprwave_template()
    test_all_theme_tomls()
    print("All template tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
