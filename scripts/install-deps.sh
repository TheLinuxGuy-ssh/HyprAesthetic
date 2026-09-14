#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/distro-detect.sh"

declare -A PKGS=(
    ["arch"]="hyprland waybar hyprwave-git eww-git rofi-wayland wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["manjaro"]="hyprland waybar hyprwave-git eww-git rofi-wayland wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["endeavouros"]="hyprland waybar hyprwave-git eww-git rofi-wayland wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["garuda"]="hyprland waybar hyprwave-git eww-git rofi-wayland wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["fedora"]="hyprland waybar hyprwave eww rofi wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["fedora-asahi-remix"]="hyprland waybar hyprwave eww rofi wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["rhel"]="hyprland waybar hyprwave eww rofi wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["centos"]="hyprland waybar hyprwave eww rofi wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["ubuntu"]="hyprland waybar rofi wofi kitty alacritty dunst mako neovim libgtk-3-0 libgtk-4-1"
    ["debian"]="hyprland waybar rofi wofi kitty alacritty dunst mako neovim libgtk-3-0 libgtk-4-1"
    ["linuxmint"]="hyprland waybar rofi wofi kitty alacritty dunst mako neovim libgtk-3-0 libgtk-4-1"
    ["pop"]="hyprland waybar rofi wofi kitty alacritty dunst mako neovim libgtk-3-0 libgtk-4-1"
    ["kali"]="hyprland waybar rofi wofi kitty alacritty dunst mako neovim libgtk-3-0 libgtk-4-1"
    ["opensuse"]="hyprland waybar rofi wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["suse"]="hyprland waybar rofi wofi kitty alacritty dunst mako neovim gtk3 gtk4"
    ["nixos"]="hyprland waybar hyprwave eww rofi wofi kitty alacritty dunst mako neovim gtk3 gtk4"
)

AUR_HELPER=""

check_package_installed() {
    local pkg="$1"
    case "$PACKAGE_MANAGER" in
        pacman) pacman -Q "$pkg" >/dev/null 2>&1 ;;
        dnf) dnf list installed "$pkg" >/dev/null 2>&1 ;;
        apt) dpkg -l "$pkg" 2>/dev/null | grep -q "^ii" ;;
        zypper) zypper search -i "$pkg" >/dev/null 2>&1 ;;
        nix) nix profile list | grep -q "$pkg" ;;
        *) return 1 ;;
    esac
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

install_deps() {
    local pkgs_str="${PKGS[$DISTRO]:-}"
    [[ -n "$pkgs_str" ]] || die "No package list for distro: $DISTRO"
    
    local pkgs=($pkgs_str)
    local missing=()
    
    log_info "Checking dependencies for $DISTRO..."
    
    for pkg in "${pkgs[@]}"; do
        if check_package_installed "$pkg"; then
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
        local aur_pkgs=()
        local repo_pkgs=()
        
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
    local pkgs_str="${PKGS[$DISTRO]:-}"
    [[ -n "$pkgs_str" ]] || die "No package list for distro: $DISTRO"
    
    local pkgs=($pkgs_str)
    local missing=0
    
    for pkg in "${pkgs[@]}"; do
        if check_package_installed "$pkg"; then
            log_success "$pkg"
        else
            log_error "$pkg (missing)"
            ((missing++))
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