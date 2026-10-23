#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/rofi-menu.sh"

THEME_SWITCHER="$SCRIPT_DIR/theme-switcher.sh"
PICKER_RASI="$HOME/.config/rofi/wallpaper.rasi"
RESTART="false"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export HYPRAESTHETIC_ROOT="$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

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
    local -A theme_by_label=()

    current=$(get_current_theme)
    rofi_menu_reset

    while IFS=$'\t' read -r label theme wallpaper_path; do
        [[ -n "$theme" ]] || continue
        display_name="${label% (active)}"
        theme_by_label["$display_name"]="$theme"
        rofi_menu_add "$label" "$wallpaper_path"
    done < <(python3 -c "
from hypraesthetic.rofi_menus import theme_menu_rows
for label, tid, preview in theme_menu_rows():
    print(f'{label}\t{tid}\t{preview}')
")

    [[ -n "$ROFI_MENU" ]] || die "No themes installed"

    selected_label=$(rofi_menu_pick "Select Theme:" "$PICKER_RASI")
    [[ -n "$selected_label" ]] || exit 0

    selected_label="${selected_label% (active)}"
    selected_theme="${theme_by_label[$selected_label]:-}"

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
