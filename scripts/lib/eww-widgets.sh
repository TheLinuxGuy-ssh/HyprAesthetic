#!/usr/bin/env bash

_EWW_LOCK_FILE="${HOME}/.cache/HyprAesthetic/eww-switch.lock"

ensure_eww_daemon() {
    if eww ping >/dev/null 2>&1; then
        return 0
    fi

    # GTK needs a Wayland display to resolve monitors for layer-shell windows
    GDK_BACKEND=wayland eww daemon >/dev/null 2>&1 &
    disown 2>/dev/null || true

    for _ in {1..50}; do
        eww ping >/dev/null 2>&1 && return 0
        sleep 0.15
    done

    return 1
}

# eww kill only stops the daemon; stray "eww open" clients leave orphan gtk-layer-shell
# surfaces that stack on top of newly opened widgets (looks like every widget is doubled).
kill_all_eww() {
    if eww ping >/dev/null 2>&1; then
        eww close-all >/dev/null 2>&1 || true
        eww kill >/dev/null 2>&1 || true
    fi
    pkill -x eww >/dev/null 2>&1 || true
    sleep 0.5
}

restart_eww_daemon() {
    kill_all_eww
    ensure_eww_daemon || die "Failed to start eww daemon"
    sleep 0.5
}

close_all_eww_windows() {
    local line win

    if ! eww ping >/dev/null 2>&1; then
        kill_all_eww
        return 0
    fi

    while IFS= read -r line; do
        win="${line%%:*}"
        win="${win//[[:space:]]/}"
        [[ -n "$win" ]] && eww close "$win" >/dev/null 2>&1 || true
    done < <(eww active-windows 2>/dev/null || true)

    eww close-all >/dev/null 2>&1 || true
    sleep 0.2
}

eww_layout_has_windows() {
    local dir="$1"
    [[ -f "$dir/eww.yuck" ]] && grep -q '(defwindow ' "$dir/eww.yuck"
}

open_eww_widgets() {
    local screen="${1:-0}"
    shift
    local -a widgets=("$@")
    local w opened=0

    [[ ${#widgets[@]} -gt 0 ]] || return 0
    ensure_eww_daemon || return 1
    sleep 0.3

    for w in "${widgets[@]}"; do
        local attempt
        for attempt in 1 2 3 4 5 6; do
            if GDK_BACKEND=wayland eww open "$w" --screen "$screen" >/dev/null 2>&1; then
                opened=$((opened + 1))
                break
            fi
            sleep 0.4
            ensure_eww_daemon || true
            [[ "$attempt" -eq 6 ]] && log_warn "Could not open eww widget: $w"
        done
    done

    [[ "$opened" -eq "${#widgets[@]}" ]]
}
