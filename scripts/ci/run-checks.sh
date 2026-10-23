#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"
cd "$ROOT"
export HYPRAESTHETIC_ROOT="$ROOT"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "=== Bash syntax ==="
bash -n install.sh
bash -n uninstall.sh
bash -n ha-theme
bash -n scripts/theme-switcher.sh
bash -n scripts/backup-configs.sh
bash -n scripts/install-deps.sh
bash -n scripts/session-start.sh
bash -n scripts/validate-themes.sh
bash -n scripts/validate-rofi-contrast.sh
bash -n scripts/rofi-theme-menu.sh
bash -n scripts/rofi-wallpaper-menu.sh
bash -n scripts/stress-test-themes.sh
for script in scripts/lib/*.sh; do
    bash -n "$script"
done

echo "=== Shellcheck ==="
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck -x -e SC1091 install.sh uninstall.sh ha-theme
    shellcheck -x -e SC1091 scripts/*.sh
    shellcheck -x -e SC1091 scripts/lib/*.sh
else
    echo "shellcheck not installed — skipping (installed in CI)"
fi

echo "=== Unit tests ==="
if command -v xvfb-run >/dev/null 2>&1; then
    GDK_BACKEND=x11 GSK_RENDERER=cairo \
        xvfb-run -a python3 -m unittest discover -s tests -v
else
    python3 -m unittest discover -s tests -v
fi

echo "=== Theme validation ==="
python3 -m hypraesthetic validate
bash scripts/validate-themes.sh

echo "=== Rofi contrast validation ==="
mkdir -p "$HOME/.config/HyprAesthetic" "$HOME/.config/rofi"
echo "toji" >"$HOME/.config/HyprAesthetic/current_theme"
rsync -a layouts/default/rofi/ "$HOME/.config/rofi/"
bash scripts/validate-rofi-contrast.sh

echo "=== Template tests ==="
python3 scripts/ci/test_templates.py

echo "=== Project structure ==="
test -f LICENSE
test -f README.md
test -f CONTRIBUTING.md
test -f CODE_OF_CONDUCT.md
test -f SECURITY.md
test -f .gitignore
test -f install.sh
test -f uninstall.sh
test -f ha-theme
test -f scripts/theme-switcher.sh
test -d themes/_template/hypr
test -d layouts/default/waybar
test -f data/packages.toml
test -f data/store-index.toml
test -d themes/spartan
test -f themes/spartan/theme.toml
test -x install.sh
test -x uninstall.sh
test -x ha-theme
test -x scripts/theme-switcher.sh

echo "All CI checks passed"
