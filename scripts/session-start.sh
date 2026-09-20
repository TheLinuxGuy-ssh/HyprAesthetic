#!/usr/bin/env bash
# Runs once per Hyprland session (login). Starts eww, waybar, wallpaper, etc.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

CACHE_DIR="${HOME}/.cache/HyprAesthetic"
LOG_FILE="${CACHE_DIR}/session-start.log"
FLAG="${CACHE_DIR}/session-${HYPRLAND_INSTANCE_SIGNATURE:-default}.flag"

mkdir -p "$CACHE_DIR"

log_session() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG_FILE"
}

[[ -f "$FLAG" ]] && exit 0

theme="$(get_current_theme)"
[[ -n "$theme" ]] || theme="a70"

log_session "Starting session for theme: $theme"

# Wait for Hyprland to be ready before opening layer-shell widgets
for _ in {1..50}; do
    hyprctl monitors >/dev/null 2>&1 && break
    sleep 0.2
done

touch "$FLAG"

# Wallpaper
if "$SCRIPT_DIR/theme-switcher.sh" switch-wallpaper "$theme" >>"$LOG_FILE" 2>&1; then
    log_session "Wallpaper set"
else
    log_session "Wallpaper switch failed (non-fatal)"
fi

# Core bar — only if not already running
if command -v waybar >/dev/null 2>&1 && ! pgrep -x waybar >/dev/null; then
    waybar >>"$LOG_FILE" 2>&1 &
    disown 2>/dev/null || true
    log_session "Started waybar"
fi

# Clipboard history
if command -v wl-paste >/dev/null 2>&1 && command -v cliphist >/dev/null 2>&1; then
    if ! pgrep -f "wl-paste --watch cliphist store" >/dev/null; then
        wl-paste --watch cliphist store >>"$LOG_FILE" 2>&1 &
        disown 2>/dev/null || true
        log_session "Started cliphist"
    fi
fi

# Hyprwave overlay
if command -v hyprwave >/dev/null 2>&1 && ! pgrep -x hyprwave >/dev/null; then
    hyprwave >>"$LOG_FILE" 2>&1 &
    disown 2>/dev/null || true
    log_session "Started hyprwave"
fi

# Eww widgets — give compositor a moment after wallpaper/bar
sleep 1
if "$SCRIPT_DIR/theme-switcher.sh" switch-eww "$theme" >>"$LOG_FILE" 2>&1; then
    log_session "Eww widgets opened"
else
    log_session "Eww switch failed — retrying once"
    sleep 2
    "$SCRIPT_DIR/theme-switcher.sh" switch-eww "$theme" >>"$LOG_FILE" 2>&1 || \
        log_session "Eww retry failed"
fi

# Monitor layout helper (toji layouts)
if command -v hyprdynamicmonitors >/dev/null 2>&1; then
    hyprdynamicmonitors run >>"$LOG_FILE" 2>&1 || true
    log_session "hyprdynamicmonitors run"
fi

log_session "Session start complete"
