"""AUR helper choice and bootstrap. makepkg never runs as root."""

from __future__ import annotations

import os
import pwd
import shutil
import tempfile
from pathlib import Path

AUR_HELPERS = ("paru", "yay")
AUR_BIN = {"paru": "paru-bin", "yay": "yay-bin"}


def split_repo_and_aur(
    packages: list[str],
    extra_aur: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    named = set(extra_aur or ())
    repo, aur = [], []
    for pkg in packages:
        (aur if pkg.endswith("-git") or pkg in named else repo).append(pkg)
    return repo, aur


def find_helper(which=None) -> str | None:
    probe = which or shutil.which
    for name in AUR_HELPERS:
        if probe(name):
            return name
    return None


def helper_runs(name: str, runner) -> bool:
    """True when the helper binary actually executes.

    Prebuilt -bin packages can sit on PATH while linked to an older libalpm
    than the installed pacman. `which` still finds them; --version does not.
    """
    try:
        result = runner([name, "--version"], check=False)
    except OSError:
        return False
    return getattr(result, "returncode", 1) == 0


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

    def ready() -> bool:
        return bool(probe(name) and helper_runs(name, runner))

    def succeeded(result) -> bool:
        return getattr(result, "returncode", 1) == 0

    def package_files(directory: str) -> list[str]:
        return sorted(str(path) for path in Path(directory).glob("*.pkg.tar.zst"))

    def remove_bin(bin_pkg: str) -> None:
        # -R only. -s would drop dependencies if the following -U fails.
        # -c / -Rcns would cascade through packages that depend on the helper.
        runner(
            privileged(["pacman", "-R", "--noconfirm", f"{bin_pkg}-debug"], euid=euid),
            check=False,
        )
        runner(
            privileged(["pacman", "-R", "--noconfirm", bin_pkg], euid=euid),
            check=False,
        )

    def install_files(paths: list[str]) -> bool:
        return succeeded(
            runner(privileged(["pacman", "-U", "--noconfirm", *paths], euid=euid), check=False)
        )

    def build(pkg: str, *, replace_bin: str | None = None) -> bool:
        user = build_user(euid=euid, environ=environ, users=users)
        if not user:
            return False
        runner(
            privileged(["pacman", "-S", "--needed", "--noconfirm", "base-devel", "git"], euid=euid),
            check=False,
        )
        url = f"https://aur.archlinux.org/{pkg}.git"
        tmpdir = tempfile.mkdtemp(prefix=f"hypraesthetic-{pkg}-")
        keep_archive = False

        def commit(paths: list[str]) -> bool:
            nonlocal keep_archive
            # -R only runs while the built archive is still on disk. Hold the
            # tree across that removal so a failed -U does not delete it.
            if not paths or not all(Path(path).is_file() for path in paths):
                return False
            keep_archive = True
            if replace_bin:
                remove_bin(replace_bin)
            if install_files(paths):
                keep_archive = False
                return True
            return False

        try:
            if euid == 0:
                ids = _user_ids(user, users)
                if ids is None:
                    return False
                os.chown(tmpdir, ids[0], ids[1])
                cloned = runner(
                    ["runuser", "-u", user, "--", "git", "clone", url, tmpdir],
                    check=False,
                )
                if not succeeded(cloned):
                    return False
                if not succeeded(
                    runner(
                        ["runuser", "-u", user, "--", "makepkg", "-s", "--noconfirm"],
                        check=False,
                        cwd=tmpdir,
                    )
                ):
                    return False
                return commit(package_files(tmpdir))
            if not succeeded(runner(["git", "clone", url, tmpdir], check=False)):
                return False
            if replace_bin:
                packed = runner(["makepkg", "-s", "--noconfirm"], check=False, cwd=tmpdir)
                if not succeeded(packed):
                    return False
                return commit(package_files(tmpdir))
            return succeeded(runner(["makepkg", "-si", "--noconfirm"], check=False, cwd=tmpdir))
        finally:
            if not keep_archive:
                shutil.rmtree(tmpdir, ignore_errors=True)

    if ready():
        return name
    runner(privileged(["pacman", "-S", "--needed", "--noconfirm", name], euid=euid), check=False)
    if ready():
        return name
    if not probe(name):
        if not build(AUR_BIN[name]) or not ready():
            if not probe(name):
                return None
    if probe(name) and not ready():
        # paru-bin / yay-bin provide the command but are linked to an older libalpm.
        # Build the source package first; remove the -bin packages only after it exists.
        if not build(name, replace_bin=AUR_BIN[name]):
            return None
    return name if ready() else None
