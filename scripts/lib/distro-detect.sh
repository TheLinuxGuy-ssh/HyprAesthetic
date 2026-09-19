#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DISTRO=""
PACKAGE_MANAGER=""
INSTALL_CMD=""
UPDATE_CMD=""

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        DISTRO="${ID:-unknown}"
    elif [[ -f /etc/arch-release ]]; then
        DISTRO="arch"
    elif [[ -f /etc/fedora-release ]]; then
        DISTRO="fedora"
    elif [[ -f /etc/debian_version ]]; then
        DISTRO="debian"
    else
        DISTRO="unknown"
    fi
    
    case "$DISTRO" in
        arch|manjaro|endeavouros|garuda)
            PACKAGE_MANAGER="pacman"
            INSTALL_CMD="sudo pacman -S --needed --noconfirm"
            UPDATE_CMD="sudo pacman -Sy"
            ;;
        fedora*|rhel|centos|rocky|alma)
            PACKAGE_MANAGER="dnf"
            INSTALL_CMD="sudo dnf install -y"
            UPDATE_CMD="sudo dnf check-update || true"
            ;;
        ubuntu|debian|linuxmint|pop|kali)
            PACKAGE_MANAGER="apt"
            INSTALL_CMD="sudo apt install -y"
            UPDATE_CMD="sudo apt update"
            ;;
        opensuse*|suse)
            PACKAGE_MANAGER="zypper"
            INSTALL_CMD="sudo zypper install -y"
            UPDATE_CMD="sudo zypper refresh"
            ;;
        nixos)
            PACKAGE_MANAGER="nix"
            INSTALL_CMD="nix profile install"
            UPDATE_CMD="nix-channel --update"
            ;;
        *)
            PACKAGE_MANAGER="unknown"
            INSTALL_CMD=""
            UPDATE_CMD=""
            ;;
    esac
    
    log_debug "Detected: distro=$DISTRO, pm=$PACKAGE_MANAGER"
    true
}

install_packages() {
    local packages=("$@")
    [[ ${#packages[@]} -eq 0 ]] && return 0
    
    [[ "$PACKAGE_MANAGER" != "unknown" ]] || die "Unknown package manager for distro: $DISTRO"
    
    log_info "Installing packages: ${packages[*]}"
    eval "$UPDATE_CMD"
    eval "$INSTALL_CMD ${packages[*]}"
}

check_package_installed() {
    local pkg="$1"
    case "$PACKAGE_MANAGER" in
        pacman) pacman -Q "$pkg" >/dev/null 2>&1 ;;
        dnf) rpm -q "$pkg" >/dev/null 2>&1 ;;
        apt) dpkg -l "$pkg" >/dev/null 2>&1 ;;
        zypper) rpm -q "$pkg" >/dev/null 2>&1 ;;
        nix) nix profile list | grep -q "$pkg" ;;
        *) return 1 ;;
    esac
}

detect_distro