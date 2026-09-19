#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/rofi-menu.sh"

WALLPAPER_DIR="${HOME}/.wallpapers"
PICKER_RASI="${HOME}/.config/rofi/wallpaper.rasi"

usage() {
    cat <<EOF
Usage: $(basename "$0")

Open a Rofi menu to pick a wallpaper from ~/.wallpapers.
EOF
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

require_cmd rofi
[[ -d "$WALLPAPER_DIR" ]] || die "Wallpaper directory not found: $WALLPAPER_DIR"
[[ -f "$PICKER_RASI" ]] || die "Rofi picker theme not found: $PICKER_RASI (run ha-theme switch <theme>)"

get_current_wallpaper_name() {
    local current=""

    if command -v swww >/dev/null 2>&1 && swww query >/dev/null 2>&1; then
        current=$(swww query 2>/dev/null | awk '{print $NF}' | xargs basename 2>/dev/null || true)
    elif command -v awww >/dev/null 2>&1; then
        current=$(awww query 2>/dev/null | awk '{print $NF}' | xargs basename 2>/dev/null || true)
    fi

    printf '%s' "$current"
}

set_wallpaper() {
    local path="$1"
    local tool

    if command -v swww >/dev/null 2>&1; then
        tool="swww"
    elif command -v awww >/dev/null 2>&1; then
        tool="awww"
    else
        die "Neither swww nor awww installed"
    fi

    if ! pgrep -x "${tool}-daemon" >/dev/null; then
        "${tool}-daemon" >/dev/null 2>&1 &
        disown 2>/dev/null || true
        sleep 0.5
    fi

    "$tool" img "$path" --transition-type fade --transition-duration 1 >/dev/null 2>&1 \
        || die "Failed to set wallpaper: $path"
}

main() {
    local current_name selected_name selected_path wallpaper_path wallpaper_name label

    current_name=$(get_current_wallpaper_name)
    rofi_menu_reset

    while IFS= read -r wallpaper_path; do
        [[ -n "$wallpaper_path" ]] || continue
        [[ -f "$wallpaper_path" ]] || continue

        wallpaper_name=$(basename "$wallpaper_path")
        label="$wallpaper_name"
        [[ "$wallpaper_name" == "$current_name" ]] && label="$wallpaper_name (current)"

        rofi_menu_add "$label" "$wallpaper_path"
    done < <(find "$WALLPAPER_DIR" -maxdepth 1 -type f \
        \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.gif' -o -iname '*.webp' \) \
        | sort)

    [[ -n "$ROFI_MENU" ]] || die "No wallpapers found in $WALLPAPER_DIR"

    selected_name=$(rofi_menu_pick "Select Wallpaper:" "$PICKER_RASI")
    [[ -n "$selected_name" ]] || exit 0

    selected_name="${selected_name% (current)}"
    selected_path="$WALLPAPER_DIR/$selected_name"
    [[ -f "$selected_path" ]] || die "Wallpaper not found: $selected_path"

    set_wallpaper "$selected_path"
    log_success "Wallpaper set: $selected_path"
}

main "$@"
