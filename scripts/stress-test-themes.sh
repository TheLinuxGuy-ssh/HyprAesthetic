#!/usr/bin/env bash
# Cycle through all themes and verify eww/widgets without interactive prompts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

CYCLES="${1:-2}"
FAILURES=0
TOTAL=0

check_eww() {
    local theme="$1"
    local expected count

    eww ping >/dev/null 2>&1 || { log_error "$theme: eww daemon not running"; return 1; }

    mapfile -t expected < <(get_toml_array "$THEMES_DIR/$theme/theme.toml" "eww.default_widgets")
    if [[ ${#expected[@]} -eq 0 ]]; then
        mapfile -t expected < <(get_toml_array "$THEMES_DIR/toji/theme.toml" "eww.default_widgets")
    fi

    count=$(eww active-windows 2>/dev/null | grep -c ':' || echo 0)
    if [[ "$count" -ne "${#expected[@]}" ]]; then
        log_error "$theme: expected ${#expected[@]} eww windows, got $count"
        eww active-windows 2>/dev/null || true
        return 1
    fi

    log_success "$theme: $count eww window(s) active"
    return 0
}

run_switch() {
    local from="$1"
    local to="$2"

    TOTAL=$((TOTAL + 1))
    log_info "Switch: $from -> $to"

    if ! "$SCRIPT_DIR/theme-switcher.sh" switch "$to" --restart 2>&1 | tail -5; then
        log_error "Switch to $to failed"
        FAILURES=$((FAILURES + 1))
        return 1
    fi

    sleep 2
    check_eww "$to" || { FAILURES=$((FAILURES + 1)); return 1; }
}

main() {
    local -a themes
    mapfile -t themes < <(list_theme_names)
    [[ ${#themes[@]} -gt 0 ]] || die "No themes found"

    log_info "Stress test: ${#themes[@]} themes, $CYCLES cycle(s)"

    for cycle in $(seq 1 "$CYCLES"); do
        log_info "=== Cycle $cycle/$CYCLES ==="
        local i
        for i in "${!themes[@]}"; do
            local next="${themes[$(( (i + 1) % ${#themes[@]} ))]}"
            run_switch "${themes[$i]}" "$next"
        done
    done

    # Critical path: cyberpunk -> toji
    run_switch "any" "cyberpunk"
    run_switch "cyberpunk" "toji"

    echo
    log_info "Results: $TOTAL switches, $FAILURES failed"
    [[ "$FAILURES" -eq 0 ]]
}

main "$@"
