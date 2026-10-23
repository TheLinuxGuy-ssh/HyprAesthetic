"""Deploy rofi palette and patch shipped adi1090x styles for theme accents."""

from __future__ import annotations

import re
from pathlib import Path

from hypraesthetic.render import render_file

_ROFI_SUBDIRS = ("launchers", "applets", "powermenu")

_CONTRAST_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        r"border-colour:\s*var\(selected\)",
        "border-colour:               var(theme-border)",
    ),
    (
        r"handle-colour:\s*var\(selected\)",
        "handle-colour:               var(theme-border)",
    ),
    (
        r"selected-normal-background:\s*var\(selected\)",
        "selected-normal-background:  var(background-alt)",
    ),
    (
        r"selected-normal-foreground:\s*var\(background\)",
        "selected-normal-foreground:  var(foreground)",
    ),
    (
        r"urgent-foreground:\s*var\(background\)",
        "urgent-foreground:           var(foreground)",
    ),
    (
        r"alternate-urgent-foreground:\s*var\(background\)",
        "alternate-urgent-foreground:  var(foreground)",
    ),
    (
        r"selected-active-foreground:\s*var\(background\)",
        "selected-active-foreground:  var(foreground)",
    ),
    (
        r"active-foreground:\s*var\(background\)",
        "active-foreground:           var(primary-fg)",
    ),
    (
        r"selected-urgent-foreground:\s*var\(background\)",
        "selected-urgent-foreground:  var(primary-fg)",
    ),
    (
        r"alternate-active-foreground:\s*var\(background\)",
        "alternate-active-foreground:  var(primary-fg)",
    ),
    (r"text-color:\s*@background;", "text-color:                  @foreground;"),
    (r"text-color:\s*var\(background\);", "text-color:                  var(foreground);"),
)


def patch_rasi_contrast(text: str) -> str:
    for pattern, repl in _CONTRAST_REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    if re.search(r"^element-text \{", text, re.M) and not re.search(
        r"^element-text \{.*?text-color:", text, re.M | re.S
    ):
        text = re.sub(
            r"^element-text \{",
            "element-text {\n    text-color:                  var(foreground);",
            text,
            count=1,
            flags=re.M,
        )
    return text


def _shared_colors_import(colors_file: Path) -> str:
    return (
        "/**\n * HyprAesthetic dynamic colors from theme.toml\n */\n"
        f'@import "{colors_file}"\n'
    )


def rewrite_shared_color_imports(rofi_dest: Path, colors_file: Path) -> None:
    if not rofi_dest.is_dir():
        return
    for path in rofi_dest.rglob("shared/colors.rasi"):
        path.write_text(_shared_colors_import(colors_file), encoding="utf-8")


def patch_deployed_rasi_files(rofi_dest: Path) -> None:
    if not rofi_dest.is_dir():
        return
    targets: list[Path] = []
    for sub in _ROFI_SUBDIRS:
        root = rofi_dest / sub
        if root.is_dir():
            targets.extend(root.rglob("*.rasi"))
    wall = rofi_dest / "wallpaper.rasi"
    if wall.is_file():
        targets.append(wall)
    for path in targets:
        if path.name == "colors.rasi" and "shared" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        updated = patch_rasi_contrast(text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def deploy_rofi_theme(rofi_dest: Path, templates_root: Path, variables: dict[str, str]) -> Path:
    """Render palette files and retarget all shared color imports under ~/.config/rofi."""
    rofi_dest.mkdir(parents=True, exist_ok=True)
    colors_dir = rofi_dest / "colors"
    colors_dir.mkdir(parents=True, exist_ok=True)
    colors_file = colors_dir / "hypraesthetic.rasi"
    render_file(templates_root / "rofi" / "colors.rasi.template", colors_file, variables)
    render_file(templates_root / "rofi" / "wallpaper.rasi.template", rofi_dest / "wallpaper.rasi", variables)
    rewrite_shared_color_imports(rofi_dest, colors_file)
    patch_deployed_rasi_files(rofi_dest)
    return colors_file
