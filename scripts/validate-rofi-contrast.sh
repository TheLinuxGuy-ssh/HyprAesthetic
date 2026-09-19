#!/usr/bin/env bash
# Check deployed Rofi styles for low-contrast text patterns.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/rofi-theme-style.sh"

ROFI_DIR="${1:-$HOME/.config/rofi}"
ISSUES=0

check_file() {
    local file="$1"
    local bad

    bad=$(grep -E '(selected-normal-foreground|normal-foreground|alternate-normal-foreground).*[[:space:]]var\(background\)' "$file" 2>/dev/null || true)
    if [[ -n "$bad" ]]; then
        log_error "$(basename "$file"): dark-on-dark foreground — $bad"
        ISSUES=$((ISSUES + 1))
    fi

    if grep -q '^element-text {' "$file" && ! grep -A8 '^element-text {' "$file" | grep -q 'text-color:'; then
        log_warn "$(basename "$file"): element-text missing explicit text-color"
    fi
}

main() {
    local theme="${2:-$(get_current_theme)}"

    [[ -d "$ROFI_DIR" ]] || die "Rofi config not found: $ROFI_DIR"

    log_info "Validating rofi contrast in $ROFI_DIR (theme: ${theme:-unknown})"

    deploy_rofi_colors "$theme" "$ROFI_DIR" >/dev/null
    deploy_wallpaper_picker_rasi "$theme" "$ROFI_DIR" >/dev/null

    while IFS= read -r -d '' f; do
        check_file "$f"
    done < <(find "$ROFI_DIR" -name '*.rasi' -print0 2>/dev/null)

    if [[ -f "$ROFI_DIR/wallpaper.rasi" ]]; then
        if grep -A6 '^element-text {' "$ROFI_DIR/wallpaper.rasi" | grep -q '@foreground\|var(foreground)'; then
            log_success "Theme picker text-color OK"
        else
            log_error "Theme picker element-text missing foreground color"
            ISSUES=$((ISSUES + 1))
        fi
    fi

    if [[ "$ISSUES" -eq 0 ]]; then
        log_success "Rofi contrast validation passed"
    else
        log_error "Rofi contrast validation failed ($ISSUES issue(s))"
        exit 1
    fi
}

main "$@"
