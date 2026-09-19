#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/distro-detect.sh"

COMPONENTS=("hypr" "waybar" "hyprwave" "eww" "rofi" "kitty" "gtk" "dunst" "nvim")

declare -A CONFIG_PATHS
CONFIG_PATHS=(
    ["hypr"]="$HOME/.config/hypr"
    ["waybar"]="$HOME/.config/waybar"
    ["hyprwave"]="$HOME/.config/hyprwave"
    ["eww"]="$HOME/.config/eww"
    ["rofi"]="$HOME/.config/rofi"
    ["kitty"]="$HOME/.config/kitty"
    ["gtk"]="$HOME/.config/gtk-3.0 $HOME/.config/gtk-4.0"
    ["dunst"]="$HOME/.config/dunst"
    ["nvim"]="$HOME/.config/nvim"
)

backup_configs() {
    local timestamp
    timestamp=$(get_timestamp)
    local backup_path="$BACKUP_DIR/$timestamp"
    
    log_info "Creating backup at $backup_path"
    mkdir -p "$backup_path"
    
    local backed_up=0
    for component in "${COMPONENTS[@]}"; do
        local paths="${CONFIG_PATHS[$component]}"
        for path in $paths; do
            if [[ -e "$path" ]]; then
                local rel_path="${path#$HOME/.config/}"
                local dest_dir
                if [[ "$rel_path" == */* ]]; then
                    dest_dir="$backup_path/$(dirname "$rel_path")"
                else
                    dest_dir="$backup_path"
                fi
                mkdir -p "$dest_dir"
                cp -r "$path" "$dest_dir/"
                log_success "Backed up: $path"
                backed_up=$((backed_up + 1))
            fi
        done
    done
    
    if [[ $backed_up -eq 0 ]]; then
        log_warn "No existing configs to backup"
        rmdir "$backup_path"
    else
        echo "$timestamp" > "$backup_path/manifest.txt"
        log_success "Backup complete: $backup_path"
    fi
}

restore_configs() {
    local timestamp="${1:-}"
    
    if [[ -z "$timestamp" ]]; then
        log_info "Available backups:"
        ls -1 "$BACKUP_DIR" 2>/dev/null | sort -r | head -20 || log_warn "No backups found"
        read -rp "Enter timestamp to restore: " timestamp
    fi
    
    local backup_path="$BACKUP_DIR/$timestamp"
    [[ -d "$backup_path" ]] || die "Backup not found: $backup_path"
    
    log_info "Restoring from $backup_path"
    
    if confirm "This will overwrite current configs. Continue?"; then
        cp -r "$backup_path"/* "$HOME/.config/"
        log_success "Restore complete"
    else
        log_info "Restore cancelled"
    fi
}

list_backups() {
    log_info "Available backups in $BACKUP_DIR:"
    ls -1 "$BACKUP_DIR" 2>/dev/null | sort -r || log_warn "No backups found"
}

main() {
    case "${1:-}" in
        backup) backup_configs ;;
        restore) restore_configs "${2:-}" ;;
        list) list_backups ;;
        *) die "Usage: $0 {backup|restore [timestamp]|list}" ;;
    esac
}

main "$@"