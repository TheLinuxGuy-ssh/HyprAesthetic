"""Root install warning and privilege-aware command argv."""

from __future__ import annotations


ROOT_WARNING = (
    "You are running as root. The recommended install is as a normal user\n"
    "with sudo (the installer will call sudo for packages). As root, configs\n"
    "are written under /root and a normal desktop session will not see them.\n"
    "If you ran sudo ./install.sh, drop sudo and run ./install.sh as yourself."
)


def allow_root_install(
    *,
    euid: int,
    assume_yes: bool,
    confirm=None,
    stdin_isatty: bool = False,
    printer=print,
    prompt=input,
) -> bool:
    if euid != 0:
        return True
    printer(ROOT_WARNING)
    if assume_yes:
        return True
    if confirm is not None:
        return bool(confirm())
    if not stdin_isatty:
        return False
    answer = prompt("Continue as root anyway? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def privileged_command(argv: list[str], *, euid: int) -> list[str]:
    if euid == 0:
        return list(argv)
    if argv and argv[0] == "sudo":
        return list(argv)
    return ["sudo", *argv]
