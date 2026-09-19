#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/rofi-menu.sh"

THEME_SWITCHER="$SCRIPT_DIR/theme-switcher.sh"
PICKER_RASI="$HOME/.config/rofi/wallpaper.rasi"
RESTART="false"

usage() {
    cat <<EOF
Usage: $(basename "$0") [--restart]

Open a Rofi menu to pick a HyprAesthetic theme by name with wallpaper previews.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --restart) RESTART="true" ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
    shift
done

require_cmd rofi
[[ -f "$PICKER_RASI" ]] || die "Rofi picker theme not found: $PICKER_RASI (run ha-theme switch <theme>)"

launch_menu() {
    local current theme display_name label wallpaper_path selected_label selected_theme
    local -A name_to_theme=()

    current=$(get_current_theme)
    rofi_menu_reset

    while IFS= read -r theme; do
        [[ -n "$theme" ]] || continue

        display_name=$(get_theme_display_name "$theme")
        name_to_theme["$display_name"]="$theme"

        label="$display_name"
        [[ "$theme" == "$current" ]] && label="$display_name (active)"

        wallpaper_path=$(get_theme_wallpaper_path "$theme" || true)
        rofi_menu_add "$label" "$wallpaper_path"
    done < <(list_theme_names)

    [[ -n "$ROFI_MENU" ]] || die "No themes found in $THEMES_DIR"

    selected_label=$(rofi_menu_pick "Select Theme:" "$PICKER_RASI")
    [[ -n "$selected_label" ]] || exit 0

    selected_label="${selected_label% (active)}"
    selected_theme="${name_to_theme[$selected_label]:-}"

    [[ -n "$selected_theme" ]] || die "Unknown theme selected: $selected_label"

    if [[ "$selected_theme" == "$current" ]]; then
        log_info "Theme already active: $selected_theme"
        exit 0
    fi

    log_info "Switching to theme: $selected_theme"
    if [[ "$RESTART" == "true" ]]; then
        "$THEME_SWITCHER" switch "$selected_theme" --restart
    else
        "$THEME_SWITCHER" switch "$selected_theme"
    fi
}

launch_menu
