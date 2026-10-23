#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/rofi-menu.sh"

PICKER_RASI="${HOME}/.config/rofi/wallpaper.rasi"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export HYPRAESTHETIC_ROOT="$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

usage() {
    cat <<EOF
Usage: $(basename "$0")

Open a Rofi menu to pick a wallpaper from ~/.wallpapers and ~/Pictures/Wallpapers.
EOF
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

require_cmd rofi
[[ -f "$PICKER_RASI" ]] || die "Rofi picker theme not found: $PICKER_RASI (run ha-theme switch <theme>)"

main() {
    local selected_label selected_path label path
    local -A path_by_label=()

    rofi_menu_reset

    while IFS=$'\t' read -r label path; do
        [[ -n "$path" ]] || continue
        path_by_label["${label% (current)}"]="$path"
        rofi_menu_add "$label" "$path"
    done < <(python3 -c "
from hypraesthetic.rofi_menus import wallpaper_menu_rows
for label, path in wallpaper_menu_rows():
    print(f'{label}\t{path}')
")

    [[ -n "$ROFI_MENU" ]] || die "No wallpapers found. Add images to ~/.wallpapers or ~/Pictures/Wallpapers."

    selected_label=$(rofi_menu_pick "Select Wallpaper:" "$PICKER_RASI")
    [[ -n "$selected_label" ]] || exit 0

    selected_label="${selected_label% (current)}"
    selected_path="${path_by_label[$selected_label]:-}"

    [[ -n "$selected_path" && -f "$selected_path" ]] || die "Wallpaper not found: $selected_label"

    if ! python3 -c "
from pathlib import Path
from hypraesthetic.wallpaper import set_user_wallpaper
import sys
ok = set_user_wallpaper(Path(sys.argv[1]))
sys.exit(0 if ok else 1)
" "$selected_path"; then
        die "Failed to save wallpaper: $selected_path"
    fi

    log_success "Wallpaper set: $selected_path"
}

main "$@"
