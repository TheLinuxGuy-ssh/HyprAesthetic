#!/usr/bin/env bash

# Build a rofi dmenu payload without a trailing blank row.
# Icon rows use echo -e escapes: "label\0icon\x1f/path" (bash arrays cannot hold null bytes).

ROFI_MENU=""

rofi_menu_reset() {
    ROFI_MENU=""
}

rofi_menu_add() {
    local label="$1"
    local icon_path="${2:-}"

    [[ -n "$label" ]] || return 0

    if [[ -n "$ROFI_MENU" ]]; then
        ROFI_MENU+=$'\n'
    fi

    if [[ -n "$icon_path" && -f "$icon_path" ]]; then
        # Literal \0 and \x1f — interpreted by echo -en when piping to rofi
        ROFI_MENU+="${label}\0icon\x1f${icon_path}"
    else
        ROFI_MENU+="${label}"
    fi
}

rofi_menu_pick() {
    local prompt="$1"
    local theme_file="$2"
    local selection

    [[ -n "$ROFI_MENU" ]] || return 1

    selection=$(echo -en "$ROFI_MENU" | rofi -dmenu \
        -p "$prompt" \
        -theme "$theme_file")

    printf '%s' "${selection:-}"
}
