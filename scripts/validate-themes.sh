#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/template-engine.sh"
source "$SCRIPT_DIR/lib/rofi-theme-style.sh"

_CONTRAST_PY="$SCRIPT_DIR/lib/contrast_check.py"
_WIDGET_CONTRAST_PY="$SCRIPT_DIR/lib/widget_contrast_check.py"

TEMPLATES=(
    "rofi/colors.rasi"
    "rofi/wallpaper.rasi"
    "waybar/colors.css"
    "dunst/dunst.conf"
    "kitty/kitty.conf"
    "hypr/colors.conf"
    "hypr/appearences.lua"
    "hyprwave/config.conf"
    "eww/eww.scss"
    "eww/eww.yuck"
    "nvim/current_theme.lua"
)

validate_contrast() {
    local theme="$1"
    local vars_file="$2"

    local out
    out=$(VARS_FILE="$vars_file" python3 "$_CONTRAST_PY" 2>&1) || {
        log_error "contrast check crashed: $out"
        return 1
    }

    if [[ -z "$out" ]]; then
        return 0
    fi

    while IFS= read -r line; do
        log_error "$line"
    done <<<"$out"
    return 1
}

validate_widget_contrast() {
    local theme="$1"
    local vars_file="$2"

    [[ -f "$HOME/.wallpapers/.keep" ]] && return 0

    local wp
    wp=$(get_theme_wallpaper_path "$theme" || true)
    [[ -n "$wp" && -f "$wp" ]] || return 0

    local yuck="$THEMES_DIR/$theme/eww/eww.yuck"
    [[ -f "$yuck" ]] || return 0

    local out
    out=$(VARS_FILE="$vars_file" WALLPAPER="$wp" YUCK="$yuck" \
        python3 "$_WIDGET_CONTRAST_PY" 2>&1) || true

    if [[ -z "$out" ]]; then
        return 0
    fi

    while IFS= read -r line; do
        log_warn "$line"
    done <<<"$out"
    return 0
}

validate_theme() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local vars_file="/tmp/ha_validate_${theme}.sh"
    local errors=0

    echo "=== $theme ==="

    [[ -f "$theme_dir/theme.toml" ]] || { log_error "missing theme.toml"; return 1; }

    prepare_theme_vars "$theme_dir" "$vars_file"

    for key in colors_waybar_background colors_waybar_border colors_waybar_primary \
        colors_waybar_warning colors_waybar_success colors_base00 \
        colors_eww_background colors_eww_foreground colors_eww_primary \
        colors_eww_error colors_eww_warning colors_eww_success colors_base0D \
        name display_name; do
        if ! grep -q "^${key}=" "$vars_file"; then
            log_error "missing $key in theme.toml"
            errors=$((errors + 1))
        fi
    done

    local tpl out
    for tpl_name in "${TEMPLATES[@]}"; do
        tpl="$THEMES_DIR/_template/${tpl_name}.template"
        out="/tmp/ha_validate_${theme}_$(basename "$tpl_name")"
        if [[ ! -f "$tpl" ]]; then
            log_warn "template missing: $tpl_name"
            continue
        fi
        if ! render_template "$tpl" "$out" "$vars_file" 2>/dev/null; then
            log_error "failed to render $tpl_name"
            errors=$((errors + 1))
            continue
        fi
        if grep -q '{{' "$out"; then
            log_error "unsubstituted variables in $tpl_name"
            grep '{{' "$out" || true
            errors=$((errors + 1))
        fi
    done

    # Check if theme has skip_contrast_check = true in [meta] section
    local skip_contrast=false
    if grep -q "^skip_contrast_check\s*=\s*true" "$theme_dir/theme.toml" 2>/dev/null; then
        skip_contrast=true
        log_info "skipping contrast check (theme declares skip_contrast_check)"
    fi

    if [[ "$skip_contrast" == "false" ]] && ! validate_contrast "$theme" "$vars_file"; then
        errors=$((errors + 1))
    fi

    if ! validate_widget_contrast "$theme" "$vars_file"; then
        errors=$((errors + 1))
    fi

    local wp
    wp=$(get_theme_wallpaper_path "$theme" || true)
    if [[ -z "$wp" || ! -f "$wp" ]]; then
        log_warn "wallpaper not found for $theme"
    fi

    if [[ ! -d "$theme_dir/rofi" ]]; then
        log_info "no rofi/ dir (fallback layout will be used)"
    fi

    rm -f "$vars_file"

    if [[ "$errors" -eq 0 ]]; then
        log_success "$theme OK"
    else
        log_error "$theme has $errors error(s)"
    fi

    return "$errors"
}

main() {
    local theme total=0 failed=0

    if [[ -n "${1:-}" ]]; then
        validate_theme "$1" || exit 1
        exit 0
    fi

    while IFS= read -r theme; do
        [[ -n "$theme" ]] || continue
        total=$((total + 1))
        validate_theme "$theme" || failed=$((failed + 1))
    done < <(list_theme_names)

    echo
    log_info "Validated $total theme(s): $((total - failed)) passed, $failed failed"
    [[ "$failed" -eq 0 ]]
}

main "$@"
