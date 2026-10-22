#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/distro-detect.sh"

ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export HYPRAESTHETIC_ROOT="$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

AUR_HELPER=""

packages_for_current() {
    python3 - <<'PY'
from hypraesthetic.installer import _read_distro_id
from hypraesthetic.packages import PackageCatalog
from hypraesthetic.prefs import AUTOMATIC_SELECTION, Prefs

catalog = PackageCatalog.load()
try:
    selection = Prefs.load().selection()
except Exception:
    selection = AUTOMATIC_SELECTION
pkgs = catalog.packages_for_selection(_read_distro_id(), selection)
print("\n".join(pkgs))
PY
}

install_packages() {
    local packages=("$@")
    [[ ${#packages[@]} -eq 0 ]] && return 0
    case "$PACKAGE_MANAGER" in
        pacman) sudo pacman -S --needed --noconfirm "${packages[@]}" ;;
        dnf) sudo dnf install -y "${packages[@]}" ;;
        apt) sudo apt update && sudo apt install -y "${packages[@]}" ;;
        zypper) sudo zypper install -y "${packages[@]}" ;;
        nix) nix profile install "${packages[@]}" ;;
        *) die "Unknown package manager: $PACKAGE_MANAGER" ;;
    esac
}

detect_aur_helper() {
    for helper in yay paru; do
        command -v "$helper" >/dev/null 2>&1 && { AUR_HELPER="$helper"; return; }
    done
}

is_installed() {
    local pkg="$1"
    case "$PACKAGE_MANAGER" in
        pacman) pacman -Q "$pkg" >/dev/null 2>&1 ;;
        dnf) rpm -q "$pkg" >/dev/null 2>&1 ;;
        apt) dpkg -s "$pkg" >/dev/null 2>&1 ;;
        zypper) rpm -q "$pkg" >/dev/null 2>&1 ;;
        nix) nix profile list | grep -q "$pkg" ;;
        *) return 1 ;;
    esac
}

install_deps() {
    local pkgs=()
    mapfile -t pkgs < <(packages_for_current)
    local missing=()
    log_info "Checking dependencies for $DISTRO..."
    for pkg in "${pkgs[@]}"; do
        [[ -n "$pkg" ]] || continue
        if is_installed "$pkg"; then
            log_success "Already installed: $pkg"
        else
            log_warn "Missing: $pkg"
            missing+=("$pkg")
        fi
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
        log_success "All dependencies satisfied"
        return 0
    fi
    log_info "Missing packages: ${missing[*]}"
    if [[ "$DISTRO" =~ ^(arch|manjaro|endeavouros|garuda)$ ]]; then
        detect_aur_helper
        local aur_pkgs=() repo_pkgs=()
        for pkg in "${missing[@]}"; do
            if [[ "$pkg" == *-git ]]; then
                aur_pkgs+=("$pkg")
            else
                repo_pkgs+=("$pkg")
            fi
        done
        if [[ ${#repo_pkgs[@]} -gt 0 ]]; then
            confirm "Install repo packages: ${repo_pkgs[*]}?" && install_packages "${repo_pkgs[@]}"
        fi
        if [[ ${#aur_pkgs[@]} -gt 0 ]]; then
            [[ -n "$AUR_HELPER" ]] || die "AUR helper (yay/paru) required for: ${aur_pkgs[*]}"
            confirm "Install AUR packages: ${aur_pkgs[*]}?" && eval "$AUR_HELPER -S --needed --noconfirm ${aur_pkgs[*]}"
        fi
    else
        confirm "Install packages: ${missing[*]}?" && install_packages "${missing[@]}"
    fi
    log_success "Dependency installation complete"
}

check_deps() {
    local pkgs=() missing=0
    mapfile -t pkgs < <(packages_for_current)
    for pkg in "${pkgs[@]}"; do
        [[ -n "$pkg" ]] || continue
        if is_installed "$pkg"; then
            log_success "$pkg"
        else
            log_error "$pkg (missing)"
            missing=$((missing + 1))
        fi
    done
    [[ $missing -eq 0 ]] || die "$missing package(s) missing"
}

main() {
    case "${1:-install}" in
        install) install_deps ;;
        check) check_deps ;;
        *) die "Usage: $0 {install|check}" ;;
    esac
}

main "$@"
