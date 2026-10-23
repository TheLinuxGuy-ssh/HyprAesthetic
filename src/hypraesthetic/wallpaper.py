"""Set the user wallpaper preference and apply it live when a daemon exists."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from hypraesthetic.prefs import Prefs

Runner = Callable[..., subprocess.CompletedProcess]


def set_user_wallpaper(
    path: Path,
    *,
    runner: Runner | None = None,
    which: Callable[[str], str | None] | None = None,
) -> bool:
    """Save wallpaper path to prefs and push to swww/awww when available."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        return False
    prefs = Prefs.load()
    prefs.set("wallpaper", str(resolved))
    prefs.save()
    run = runner or subprocess.run
    probe = which or shutil.which

    tool = probe("swww") or probe("awww")
    if not tool:
        return True
    tool_name = Path(tool).name
    daemon = f"{tool_name}-daemon"
    if run(["pgrep", "-x", daemon], capture_output=True).returncode != 0:
        run([daemon], check=False)
    run(
        [tool, "img", str(resolved), "--transition-type", "fade", "--transition-duration", "1"],
        check=False,
        capture_output=True,
    )
    return True
