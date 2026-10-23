"""AUR helper choice and bootstrap. makepkg never runs as root."""

from __future__ import annotations

import os
import pwd
import shutil
import tempfile
from pathlib import Path

AUR_HELPERS = ("paru", "yay")
AUR_BIN = {"paru": "paru-bin", "yay": "yay-bin"}


def split_repo_and_aur(packages: list[str]) -> tuple[list[str], list[str]]:
    repo, aur = [], []
    for pkg in packages:
        (aur if pkg.endswith("-git") else repo).append(pkg)
    return repo, aur


def find_helper(which=None) -> str | None:
    probe = which or shutil.which
    for name in AUR_HELPERS:
        if probe(name):
            return name
    return None


def choose_helper(*, assume_yes: bool, which=None, ask=None, printer=print) -> str:
    found = find_helper(which=which)
    if found:
        return found
    if assume_yes:
        return "paru"
    printer("No AUR helper found (paru or yay).")
    printer("  1) paru  (recommended)")
    printer("  2) yay")
    if ask is None:
        raw = input("Install which helper? [1/2]: ")
    else:
        raw = ask()
    raw = str(raw).strip().lower()
    if raw in {"2", "yay"}:
        return "yay"
    return "paru"


def build_user(*, euid: int, environ: dict | None = None, users=None) -> str | None:
    env = environ if environ is not None else os.environ
    sudo_user = (env.get("SUDO_USER") or "").strip()
    if sudo_user and sudo_user != "root":
        return sudo_user
    if euid != 0:
        return pwd.getpwuid(euid).pw_name
    entries = users if users is not None else pwd.getpwall()
    named = [entry for entry in entries if 1000 <= getattr(entry, "pw_uid", 0) < 65534]
    named.sort(key=lambda entry: entry.pw_uid)
    return named[0].pw_name if named else None


def _user_ids(name: str, users) -> tuple[int, int] | None:
    if users is not None:
        for entry in users:
            if getattr(entry, "pw_name", None) == name:
                return int(entry.pw_uid), int(getattr(entry, "pw_gid", entry.pw_uid))
        return None
    try:
        record = pwd.getpwnam(name)
    except KeyError:
        return None
    return record.pw_uid, record.pw_gid


def ensure_helper(
    name: str,
    *,
    runner,
    euid: int,
    which=None,
    privileged,
    environ: dict | None = None,
    users=None,
) -> str | None:
    probe = which or shutil.which
    if probe(name):
        return name
    runner(privileged(["pacman", "-S", "--needed", "--noconfirm", name], euid=euid), check=False)
    if probe(name):
        return name
    user = build_user(euid=euid, environ=environ, users=users)
    if not user:
        return None
    runner(
        privileged(["pacman", "-S", "--needed", "--noconfirm", "base-devel", "git"], euid=euid),
        check=False,
    )
    url = f"https://aur.archlinux.org/{AUR_BIN[name]}.git"
    tmpdir = tempfile.mkdtemp(prefix=f"hypraesthetic-{AUR_BIN[name]}-")
    try:
        if euid == 0:
            ids = _user_ids(user, users)
            if ids is None:
                return None
            os.chown(tmpdir, ids[0], ids[1])
            runner(["runuser", "-u", user, "--", "git", "clone", url, tmpdir], check=False)
            runner(
                ["runuser", "-u", user, "--", "makepkg", "-s", "--noconfirm"],
                check=False,
                cwd=tmpdir,
            )
            built = sorted(str(path) for path in Path(tmpdir).glob("*.pkg.tar.zst"))
            if built:
                runner(privileged(["pacman", "-U", "--noconfirm", *built], euid=euid), check=False)
        else:
            runner(["git", "clone", url, tmpdir], check=False)
            runner(["makepkg", "-si", "--noconfirm"], check=False, cwd=tmpdir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return name if probe(name) else None
