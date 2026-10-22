#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HYPRAESTHETIC_ROOT="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# shellcheck source=scripts/lib/common.sh
source "$REPO_ROOT/scripts/lib/common.sh"

print_banner() {
    cat <<'EOF'
╔══════════════════════════════════════════════════════════════╗
║                   HyprAesthetic installer                    ║
║                    Hyprland made easy                        ║
╚══════════════════════════════════════════════════════════════╝
EOF
}

ensure_local_bin_in_path() {
    local bin_dir="$HOME/.local/bin"
    local shell_rc=""

    case "$SHELL" in
        */zsh) shell_rc="$HOME/.zshrc" ;;
        */bash) shell_rc="$HOME/.bashrc" ;;
        */fish) shell_rc="$HOME/.config/fish/config.fish" ;;
        *) return 0 ;;
    esac

    [[ -f "$shell_rc" ]] || return 0

    if grep -qE "(^|:)/?\.local/bin" "$shell_rc" 2>/dev/null || grep -q "\.local/bin" "$shell_rc" 2>/dev/null; then
        return 0
    fi

    if [[ "$SHELL" == *fish ]]; then
        echo -e "\n# HyprAesthetic\nfish_add_path $bin_dir" >>"$shell_rc"
    else
        echo -e "\n# HyprAesthetic\nexport PATH=\"$bin_dir:\$PATH\"" >>"$shell_rc"
    fi
    log_success "Added $bin_dir to PATH in $shell_rc"
}

print_banner
require_cmd python3
python3 -c "import tomllib" 2>/dev/null || die "Python tomllib required (Python 3.11+)"
ensure_local_bin_in_path
export PATH="$HOME/.local/bin:$PATH"
exec python3 -m hypraesthetic install "$@"
