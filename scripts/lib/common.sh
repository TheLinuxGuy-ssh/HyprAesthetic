#!/usr/bin/env bash
set -euo pipefail

_COMMON_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$_COMMON_SCRIPT_DIR/../.." && pwd)"
THEMES_DIR="$PROJECT_ROOT/themes"
CONFIG_DIR="$PROJECT_ROOT/config"
BACKUP_DIR="$HOME/.config.backup"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_debug() { [[ "${DEBUG:-0}" == "1" ]] && echo -e "${YELLOW}[DEBUG]${NC} $*"; }

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

get_current_theme() {
    local theme_file="$HOME/.config/hypranime/current_theme"
    [[ -f "$theme_file" ]] && cat "$theme_file" || echo ""
}

set_current_theme() {
    mkdir -p "$HOME/.config/hypranime"
    echo "$1" > "$HOME/.config/hypranime/current_theme"
}

get_timestamp() { date '+%Y-%m-%d_%H-%M-%S'; }

confirm() {
    local prompt="${1:-Continue?}"
    read -rp "$prompt [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}