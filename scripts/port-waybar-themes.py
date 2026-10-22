#!/usr/bin/env python3
"""Port HANCORE waybar-themes into layouts/bars with HyprAesthetic colors."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hypraesthetic.waybar_config import sanitize_waybar_config  # noqa: E402
from hypraesthetic.waybar_css import theme_waybar_css  # noqa: E402
KEEP_FILES = {
    "config.jsonc",
    "style.css",
    "window_pill.py",
    "scrolling-mpris.py",
    "cava.sh",
    "bob2.svg",
}
HEADING_RE = re.compile(r"^## (V[^\n]+)\s*$", re.M)
BUILTIN = {"default", "compact", "a70", "cyberpunk"}


def slug(name: str) -> str:
    return name.strip().lower().replace(" ", "-")


def read_descriptions(readme: Path) -> dict[str, str]:
    if not readme.is_file():
        return {}
    text = readme.read_text(encoding="utf-8", errors="replace")
    found: dict[str, str] = {}
    matches = list(HEADING_RE.finditer(text))
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        blurb = ""
        for line in body.splitlines():
            line = re.sub(r"<[^>]+>", "", line).strip(" -")
            if line and not line.lower().startswith("#####") and "install-command" not in line.lower():
                blurb = line[:120]
                break
        found[name] = blurb or "HANCORE Waybar layout"
    return found


def rewrite_css(text: str) -> str:
    text = re.sub(
        r'@import\s+["\'][^"\']*omarchy[^"\']*["\']\s*;',
        '@import "colors.css";',
        text,
    )
    text = re.sub(
        r'@import\s+["\'][^"\']*rose-pine[^"\']*["\']\s*;',
        '@import "colors.css";',
        text,
    )
    if '@import "colors.css"' not in text:
        text = '@import "colors.css";\n' + text
    return theme_waybar_css(text)


def dump_toml(name: str, description: str, upstream: str) -> str:
    desc = description.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'name = "{name}"\n'
        f'description = "{desc}"\n'
        'source = "https://github.com/HANCORE-linux/waybar-themes"\n'
        f'upstream = "{upstream}"\n'
    )


def pick_preview(src: Path) -> Path | None:
    pngs = sorted(src.glob("*.png")) + sorted(src.glob("*.jpg"))
    small = [path for path in pngs if path.stat().st_size <= 180_000]
    if small:
        return min(small, key=lambda path: path.stat().st_size)
    return None


def port_one(src: Path, dest_root: Path, blurbs: dict[str, str]) -> Path:
    dest = dest_root / slug(src.name)
    dest.mkdir(parents=True, exist_ok=True)
    for name in KEEP_FILES:
        src_file = src / name
        if src_file.is_file():
            shutil.copy2(src_file, dest / name)
            if name.endswith(".py") or name.endswith(".sh"):
                (dest / name).chmod(0o755)
    config = dest / "config.jsonc"
    if config.is_file():
        text = sanitize_waybar_config(config.read_text(encoding="utf-8", errors="replace"))
        config.write_text(text, encoding="utf-8")
    style = dest / "style.css"
    if style.is_file():
        style.write_text(rewrite_css(style.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    preview = pick_preview(src)
    if preview is not None:
        shutil.copy2(preview, dest / "preview.png")
    (dest / "bar.toml").write_text(
        dump_toml(src.name, blurbs.get(src.name, "HANCORE Waybar layout"), src.name),
        encoding="utf-8",
    )
    return dest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(Path.home() / "waybar-themes"))
    args = parser.parse_args()
    source = Path(args.source).expanduser()
    config = source / "config"
    if not config.is_dir():
        raise SystemExit(f"Missing {config}")
    dest_root = ROOT / "layouts" / "bars"
    dest_root.mkdir(parents=True, exist_ok=True)
    blurbs = read_descriptions(source / "README.md")
    count = 0
    for child in sorted(config.iterdir()):
        if not child.is_dir() or child.name in {"test"}:
            continue
        if not (child / "config.jsonc").is_file() or not (child / "style.css").is_file():
            continue
        if slug(child.name) in BUILTIN:
            continue
        port_one(child, dest_root, blurbs)
        count += 1
    license_src = source / "LICENSE"
    if license_src.is_file():
        shutil.copy2(license_src, dest_root / "HANCORE-LICENSE")
    readme = dest_root / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Waybar layouts",
                "",
                "`default`, `compact`, `a70`, and `cyberpunk` are first-party HyprAesthetic bars.",
                "The `v*` layouts are ported from [HANCORE-linux/waybar-themes](https://github.com/HANCORE-linux/waybar-themes) (MIT).",
                "Omarchy-only modules were removed and colors import `colors.css` from the active HyprAesthetic theme.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"ported {count} bars -> {dest_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
