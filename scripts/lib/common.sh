#!/usr/bin/env bash
set -euo pipefail

_COMMON_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$_COMMON_SCRIPT_DIR/../.." && pwd)"
THEMES_DIR="$PROJECT_ROOT/themes"
CONFIG_DIR="$PROJECT_ROOT/config"
BACKUP_DIR="$HOME/.config.backup"
CONFIG_DIR_NAME="HyprAesthetic"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_debug() { [[ "${DEBUG:-0}" == "1" ]] && echo -e "${YELLOW}[DEBUG]${NC} $*"; true; }

die() { log_error "$*"; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Required command '$1' not found"; }

parse_toml() {
    local file="$1"
    [[ -f "$file" ]] || die "TOML file not found: $file"
    python3 -c "
import sys, tomllib
with open('$file', 'rb') as f:
    data = tomllib.load(f)
def flatten(d, prefix=''):
    for k, v in d.items():
        key = f'{prefix}{k}'.replace('-', '_')
        if isinstance(v, dict):
            flatten(v, f'{key}_')
        elif isinstance(v, bool):
            print(f'{key}=\"{str(v).lower()}\"')
        elif isinstance(v, (int, float)):
            print(f'{key}={v}')
        else:
            print(f'{key}=\"{v}\"')
flatten(data)
"
}

get_primary_screen() {
    if ! command -v hyprctl >/dev/null 2>&1; then
        echo "0"
        return
    fi
    hyprctl monitors -j 2>/dev/null | python3 -c "
import json, sys
try:
    monitors = json.load(sys.stdin)
except Exception:
    print(0); sys.exit(0)
if not monitors:
    print(0); sys.exit(0)
idx = next((i for i, m in enumerate(monitors) if m.get('focused')), 0)
print(idx)
"
}

get_toml_array() {
    local file="$1"
    local key="$2"
    [[ -f "$file" ]] || die "TOML file not found: $file"
    python3 -c "
import sys, tomllib
with open('$file', 'rb') as f:
    data = tomllib.load(f)
path = '$key'.split('.')
val = data
try:
    for p in path:
        val = val[p]
except KeyError:
    sys.exit(0)
if isinstance(val, list):
    for item in val:
        print(item)
"
}

get_current_theme() {
    local theme_file="$HOME/.config/HyprAesthetic/current_theme"
    [[ -f "$theme_file" ]] && cat "$theme_file" || echo ""
}

set_current_theme() {
    mkdir -p "$HOME/.config/HyprAesthetic"
    echo "$1" > "$HOME/.config/HyprAesthetic/current_theme"
}

get_toml_value() {
    local file="$1"
    local key="$2"
    [[ -f "$file" ]] || return 0
    parse_toml "$file" | grep "^${key}=" | head -1 | cut -d= -f2- | tr -d '"' || true
}

get_theme_display_name() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local display_name

    display_name=$(get_toml_value "$theme_dir/theme.toml" "display_name" 2>/dev/null || true)
    [[ -n "$display_name" ]] && echo "$display_name" || echo "$theme"
}

get_theme_wallpaper_file() {
    local theme="$1"
    get_toml_value "$THEMES_DIR/$theme/theme.toml" "misc_wallpaper" 2>/dev/null || true
}

get_theme_wallpaper_path() {
    local theme="$1"
    local wallpaper

    wallpaper=$(get_theme_wallpaper_file "$theme")
    [[ -n "$wallpaper" && -f "$HOME/.wallpapers/$wallpaper" ]] && echo "$HOME/.wallpapers/$wallpaper"
}

get_theme_waybar_color() {
    local theme="$1"
    local key="$2"
    local toml="$THEMES_DIR/$theme/theme.toml"
    local value fallback_key

    value=$(get_toml_value "$toml" "colors_waybar_${key}" 2>/dev/null || true)
    [[ -n "$value" ]] && echo "$value" && return 0

    case "$key" in
        background) fallback_key="colors_base00" ;;
        foreground) fallback_key="colors_base05" ;;
        surface) fallback_key="colors_base01" ;;
        primary) fallback_key="colors_base0D" ;;
        error) fallback_key="colors_base08" ;;
        *) fallback_key="" ;;
    esac

    [[ -n "$fallback_key" ]] && get_toml_value "$toml" "$fallback_key" 2>/dev/null || true
}

list_theme_names() {
    find "$THEMES_DIR" -mindepth 1 -maxdepth 1 -type d ! -name "_template" -printf "%f\n" | sort
}

resolve_fallback_theme_dir() {
    local component="$1"
    local preferred="${2:-toji}"
    local theme

    if [[ -d "$THEMES_DIR/$preferred/$component" ]]; then
        echo "$THEMES_DIR/$preferred/$component"
        return 0
    fi

    while IFS= read -r theme; do
        [[ -n "$theme" ]] || continue
        [[ -d "$THEMES_DIR/$theme/$component" ]] && echo "$THEMES_DIR/$theme/$component" && return 0
    done < <(list_theme_names)

    return 1
}

get_timestamp() { date '+%Y-%m-%d_%H-%M-%S'; }

confirm() {
    local prompt="${1:-Continue?}"
    read -rp "$prompt [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}