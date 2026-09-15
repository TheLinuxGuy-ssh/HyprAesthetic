#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/distro-detect.sh"

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
    find "$PROJECT_ROOT/themes" -mindepth 1 -maxdepth 1 -type d ! -name "_template" -printf "%f\n" | sort
}

select_theme() {
    local themes=($(list_themes))
    [[ ${#themes[@]} -gt 0 ]] || die "No themes found in $PROJECT_ROOT/themes"
    
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

install_shell_integration() {
    local shell_rc=""
    case "$SHELL" in
        */zsh) shell_rc="$HOME/.zshrc" ;;
        */bash) shell_rc="$HOME/.bashrc" ;;
        */fish) shell_rc="$HOME/.config/fish/config.fish" ;;
        *) return ;;
    esac
    
    local path_entry="export PATH=\"$PROJECT_ROOT:\$PATH\""
    local alias_entry="alias hat='ha-theme'"
    
    if [[ -f "$shell_rc" ]] && grep -q "ha-theme" "$shell_rc"; then
        log_info "Shell integration already present in $shell_rc"
        return
    fi
    
    if confirm "Add HyprAesthetic to PATH and create 'hat' alias in $shell_rc?"; then
        echo -e "\n# HyprAesthetic\n$path_entry\n$alias_entry" >> "$shell_rc"
        log_success "Added to $shell_rc (restart shell or source it)"
    fi
}

main() {
    print_banner
    
    check_requirements
    
    log_info "Detected distro: $DISTRO ($PACKAGE_MANAGER)"
    
    "$SCRIPT_DIR/install-deps.sh" install
    
    "$SCRIPT_DIR/backup-configs.sh" backup
    
    local theme
    theme=$(select_theme)
    log_info "Selected theme: $theme"
    
    "$PROJECT_ROOT/ha-theme" switch "$theme"
    
    install_shell_integration
    
cat <<EOF

╔═══════════════════════════════════════════════════════════════╗
║                    Installation complete!                     ║
╚═══════════════════════════════════════════════════════════════╝

Active theme: $theme

Next steps:
  1. Restart your shell or run: source ~/.zshrc (or .bashrc/.config/fish/config.fish)
  2. Switch themes anytime: ha-theme switch <theme>
  3. List themes: ha-theme list
  4. Short alias: hat switch <theme>

Config location: ~/.config/HyprAesthetic/
Backups: ~/.config.backup/

To uninstall: $SCRIPT_DIR/uninstall.sh

EOF
}

main "$@"