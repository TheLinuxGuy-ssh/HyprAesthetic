#!/usr/bin/env bash

_EWW_LOCK_FILE="${HOME}/.cache/HyprAesthetic/eww-switch.lock"
_EWW_POLL_INTERVAL=0.05

_wait_eww_down() {
    local _
    # eww ping blocks ~1s when the daemon is gone — use pgrep for shutdown checks.
    for _ in {1..20}; do
        pgrep -x eww >/dev/null 2>&1 || return 0
        sleep "$_EWW_POLL_INTERVAL"
    done
    pkill -9 -x eww >/dev/null 2>&1 || true
    sleep 0.1
}

_wait_eww_up() {
    local _
    for _ in {1..60}; do
        eww ping >/dev/null 2>&1 && return 0
        sleep "$_EWW_POLL_INTERVAL"
    done
    return 1
}

ensure_eww_daemon() {
    if eww ping >/dev/null 2>&1; then
        return 0
    fi

    # GTK needs a Wayland display to resolve monitors for layer-shell windows
    GDK_BACKEND=wayland eww daemon >/dev/null 2>&1 &
    disown 2>/dev/null || true
    _wait_eww_up
}

# eww kill only stops the daemon; stray "eww open" clients leave orphan gtk-layer-shell
# surfaces that stack on top of newly opened widgets (looks like every widget is doubled).
kill_all_eww() {
    if eww ping >/dev/null 2>&1; then
        eww close-all >/dev/null 2>&1 || true
        eww kill >/dev/null 2>&1 || true
    fi
    pkill -x eww >/dev/null 2>&1 || true
    _wait_eww_down
}

close_all_eww_windows() {
    if ! eww ping >/dev/null 2>&1; then
        return 0
    fi

    eww close-all >/dev/null 2>&1 || true

    local _
    for _ in {1..20}; do
        [[ -z "$(eww active-windows 2>/dev/null)" ]] && return 0
        sleep "$_EWW_POLL_INTERVAL"
    done
}

hide_eww_widgets() {
    mkdir -p "$(dirname "$_EWW_LOCK_FILE")"
    (
        flock -w 20 200 || die "Timed out waiting for eww lock"
        close_all_eww_windows
        flock -u 200
    ) 200>"$_EWW_LOCK_FILE"
}

eww_layout_has_windows() {
    local dir="$1"
    [[ -f "$dir/eww.yuck" ]] && grep -q '(defwindow ' "$dir/eww.yuck"
}

eww_config_hash() {
    local dir="$1"
    local f="$dir/eww.yuck"
    [[ -f "$f" ]] && md5sum "$f" | awk '{print $1}' || echo ""
}

eww_config_dir() {
    echo "$HOME/.config/eww"
}

eww_active_widget_names() {
    local line name
    while IFS= read -r line; do
        name="${line#*:}"
        name="${name//[[:space:]]/}"
        [[ -n "$name" ]] && printf '%s\n' "$name"
    done < <(eww active-windows 2>/dev/null || true)
}

eww_widgets_match() {
    local -a expected=("$@")
    local -a active=()
    local expected_sorted active_sorted

    [[ ${#expected[@]} -gt 0 ]] || return 0

    mapfile -t active < <(eww_active_widget_names)
    [[ "${#active[@]}" -eq "${#expected[@]}" ]] || return 1

    expected_sorted="$(printf '%s\n' "${expected[@]}" | sort)"
    active_sorted="$(printf '%s\n' "${active[@]}" | sort)"
    [[ "$expected_sorted" == "$active_sorted" ]]
}

open_eww_widgets() {
    local screen="${1:-0}"
    shift
    local -a widgets=("$@")
    local -a pids=()
    local w pid opened=0

    [[ ${#widgets[@]} -gt 0 ]] || return 0
    ensure_eww_daemon || return 1

    for w in "${widgets[@]}"; do
        GDK_BACKEND=wayland eww open "$w" --screen "$screen" >/dev/null 2>&1 &
        pids+=("$!")
    done

    for pid in "${pids[@]}"; do
        wait "$pid" && opened=$((opened + 1)) || true
    done

    if [[ "$opened" -lt "${#widgets[@]}" ]]; then
        for w in "${widgets[@]}"; do
            eww active-windows 2>/dev/null | grep -qE ":[[:space:]]*${w}[[:space:]]*$" && continue
            if GDK_BACKEND=wayland eww open "$w" --screen "$screen" >/dev/null 2>&1; then
                opened=$((opened + 1))
            else
                log_warn "Could not open eww widget: $w"
            fi
        done
    fi

    [[ "$opened" -eq "${#widgets[@]}" ]]
}
