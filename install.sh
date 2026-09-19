#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$REPO_ROOT/scripts"
source "$SCRIPTS_DIR/lib/common.sh"
source "$SCRIPTS_DIR/lib/distro-detect.sh"

print_banner() {
    cat <<'EOF'
╔══════════════════════════════════════════════════════════════╗
║                   HyprAesthetic installer                    ║
║         Anime-themed Hyprland dotfiles system                ║
╚══════════════════════════════════════════════════════════════╝
EOF
}

check_requirements() {
    log_info "Checking system requirements..."

    require_cmd "python3"
    require_cmd "envsubst"

    python3 -c "import tomllib" 2>/dev/null || die "Python tomllib required (Python 3.11+)"

    log_success "Requirements satisfied"
}

list_themes() {
    find "$REPO_ROOT/themes" -mindepth 1 -maxdepth 1 -type d ! -name "_template" -printf "%f\n" | sort
}

select_theme() {
    local themes=($(list_themes))
    [[ ${#themes[@]} -gt 0 ]] || die "No themes found in $REPO_ROOT/themes"

    if [[ ${#themes[@]} -eq 1 ]]; then
        echo "${themes[0]}"
        return
    fi

    log_info "Available themes:"
    for i in "${!themes[@]}"; do
        echo "  $((i+1))) ${themes[i]}"
    done

    local choice
    while true; do
        read -rp "Select theme [1-${#themes[@]}]: " choice
        [[ "$choice" =~ ^[0-9]+$ ]] && ((choice >= 1 && choice <= ${#themes[@]})) && break
        log_error "Invalid choice"
    done

    echo "${themes[choice-1]}"
}

install_user_cli() {
    local bin_dir="$HOME/.local/bin"
    local ha_theme_bin="$bin_dir/ha-theme"
    local hat_bin="$bin_dir/hat"

    mkdir -p "$bin_dir" "$HOME/.config/HyprAesthetic"

    ln -sf "$REPO_ROOT/ha-theme" "$ha_theme_bin"
    ln -sf "$REPO_ROOT/scripts/rofi-wallpaper-menu.sh" "$bin_dir/hyprwall"

    cat >"$hat_bin" <<EOF
#!/usr/bin/env bash
exec "$ha_theme_bin" "\$@"
EOF
    chmod +x "$hat_bin"

    echo "$REPO_ROOT" >"$HOME/.config/HyprAesthetic/root"

    log_success "Installed user-wide CLI: $ha_theme_bin"
    log_success "Installed wallpaper picker: $bin_dir/hyprwall"
    log_success "Installed shortcut: $hat_bin"
}

ensure_local_bin_in_path() {
    local bin_dir="$HOME/.local/bin"
    local shell_rc=""

    case "$SHELL" in
        */zsh) shell_rc="$HOME/.zshrc" ;;
        */bash) shell_rc="$HOME/.bashrc" ;;
        */fish) shell_rc="$HOME/.config/fish/config.fish" ;;
        *) return 0 ;;
    esac

    [[ -f "$shell_rc" ]] || return 0

    if grep -qE "(^|:)/?\.local/bin" "$shell_rc" 2>/dev/null || grep -q "\.local/bin" "$shell_rc" 2>/dev/null; then
        log_info "~/.local/bin already configured in $shell_rc"
        return 0
    fi

    if [[ "$SHELL" == *fish ]]; then
        echo -e "\n# HyprAesthetic\nfish_add_path $bin_dir" >>"$shell_rc"
    else
        echo -e "\n# HyprAesthetic\nexport PATH=\"$bin_dir:\$PATH\"" >>"$shell_rc"
    fi

    log_success "Added $bin_dir to PATH in $shell_rc"
}

main() {
    print_banner

    check_requirements

    log_info "Detected distro: $DISTRO ($PACKAGE_MANAGER)"

    install_user_cli
    ensure_local_bin_in_path

    export PATH="$HOME/.local/bin:$PATH"

    "$SCRIPTS_DIR/install-deps.sh" install

    "$SCRIPTS_DIR/backup-configs.sh" backup

    local theme
    theme=$(select_theme)
    log_info "Selected theme: $theme"

    "$REPO_ROOT/ha-theme" switch "$theme"

    cat <<EOF

╔═══════════════════════════════════════════════════════════════╗
║                    Installation complete!                     ║
╚═══════════════════════════════════════════════════════════════╝

Active theme: $theme

Installed commands (user-wide):
  ha-theme
  hat

Next steps:
  1. Open a new shell or run: export PATH="\$HOME/.local/bin:\$PATH"
  2. Switch themes: ha-theme switch <theme>
  3. Theme picker menu: ha-theme menu   (or Super + A)
  4. List themes: ha-theme list

Config location: ~/.config/HyprAesthetic/
Install root: $REPO_ROOT
Backups: ~/.config.backup/

To uninstall: $REPO_ROOT/uninstall.sh

EOF
}

main "$@"
