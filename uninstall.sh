#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$REPO_ROOT/scripts"
source "$SCRIPTS_DIR/lib/common.sh"

COMPONENTS=("hypr" "waybar" "hyprwave" "eww" "rofi" "kitty" "gtk" "dunst" "nvim")

CONFIG_PATHS=(
    ["hypr"]="$HOME/.config/hypr"
    ["waybar"]="$HOME/.config/waybar"
    ["hyprwave"]="$HOME/.config/hyprwave"
    ["eww"]="$HOME/.config/eww"
    ["rofi"]="$HOME/.config/rofi"
    ["kitty"]="$HOME/.config/kitty"
    ["gtk"]="$HOME/.config/gtk-3.0 $HOME/.config/gtk-4.0"
    ["dunst"]="$HOME/.config/dunst"
    ["nvim"]="$HOME/.config/nvim/lua/themes/current_theme.lua"
)

remove_user_cli() {
    rm -f "$HOME/.local/bin/ha-theme" "$HOME/.local/bin/hat"
    log_success "Removed user-wide CLI from ~/.local/bin"
}

uninstall() {
    log_warn "This will remove all HyprAesthetic-managed configs from ~/.config"
    confirm "Continue with uninstall?" || { log_info "Cancelled"; exit 0; }

    "$SCRIPTS_DIR/backup-configs.sh" backup

    for component in "${COMPONENTS[@]}"; do
        local paths="${CONFIG_PATHS[$component]}"
        for path in $paths; do
            if [[ -L "$path" ]]; then
                local target
                target=$(readlink "$path")
                if [[ "$target" == *"Hypraesthetic/themes/"* ]] || [[ "$target" == *"HyprAesthetic/themes/"* ]]; then
                    rm "$path"
                    log_success "Removed symlink: $path"
                fi
            elif [[ -d "$path" ]] || [[ -f "$path" ]]; then
                log_warn "Not removing non-symlink: $path (manual cleanup needed)"
            fi
        done
    done

    remove_user_cli

    rm -f "$HOME/.config/HyprAesthetic/current_theme" "$HOME/.config/HyprAesthetic/root"
    rmdir "$HOME/.config/HyprAesthetic" 2>/dev/null || true

    log_success "Uninstall complete. Configs backed up to ~/.config.backup/"
    log_info "To restore: $SCRIPTS_DIR/backup-configs.sh restore <timestamp>"
}

main() {
    case "${1:-}" in
        uninstall|remove) uninstall ;;
        *) die "Usage: $0 uninstall" ;;
    esac
}

main "$@"
