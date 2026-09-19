#!/usr/bin/env bash

_ROFI_STYLE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_ROFI_STYLE_SCRIPT_DIR/common.sh"
source "$_ROFI_STYLE_SCRIPT_DIR/template-engine.sh"

render_theme_rofi_file() {
    local theme="$1"
    local template_name="$2"
    local output="$3"
    local theme_dir="$THEMES_DIR/$theme"
    local template="$THEMES_DIR/_template/rofi/${template_name}.template"
    local vars_file

    [[ -f "$template" ]] || die "Rofi template not found: $template"
    [[ -f "$theme_dir/theme.toml" ]] || die "Theme missing theme.toml: $theme"

    vars_file=$(mktemp /tmp/ha_rofi_vars_XXXXXX.sh)
    prepare_theme_vars "$theme_dir" "$vars_file"

    mkdir -p "$(dirname "$output")"
    TEMPLATE_FILE="$template" OUTPUT_FILE="$output" VARS_FILE="$vars_file" \
        python3 -c "$(cat <<'PYEOF'
import os
import re

template_file = os.environ["TEMPLATE_FILE"]
output_file = os.environ["OUTPUT_FILE"]
vars_file = os.environ["VARS_FILE"]

with open(vars_file) as f:
    vars_content = f.read()

variables = {}
for line in vars_content.strip().split("\n"):
    if "=" in line:
        key, value = line.split("=", 1)
        variables[key] = value

with open(template_file) as f:
    template = f.read()

def replace_var(match):
    var_name = match.group(1).replace(".", "_")
    value = variables.get(var_name, match.group(0))
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    return value

rendered = re.sub(r"\{\{([a-zA-Z0-9_.]+)\}\}", replace_var, template)

with open(output_file, "w") as f:
    f.write(rendered)
PYEOF
)"

    rm -f "$vars_file"
}

resolve_rofi_fonts_file() {
    local theme="${1:-$(get_current_theme)}"

    for f in \
        "$THEMES_DIR/$theme/rofi/launchers/type-1/shared/fonts.rasi" \
        "$HOME/.config/rofi/launchers/type-1/shared/fonts.rasi"
    do
        [[ -f "$f" ]] && echo "$f" && return 0
    done

    return 1
}

patch_rofi_rasi_contrast() {
    local rasi="$1"
    local file

    [[ -f "$rasi" ]] || return 0
    [[ "$(basename "$rasi")" == "colors.rasi" ]] && return 0

    file=$(mktemp)
    sed \
        -e 's/border-colour:[[:space:]]*var(selected)/border-colour:               var(theme-border)/g' \
        -e 's/handle-colour:[[:space:]]*var(selected)/handle-colour:               var(theme-border)/g' \
        -e 's/selected-normal-background:[[:space:]]*var(selected)/selected-normal-background:  var(background-alt)/g' \
        -e 's/selected-normal-foreground:[[:space:]]*var(background)/selected-normal-foreground:  var(foreground)/g' \
        -e 's/urgent-foreground:[[:space:]]*var(background)/urgent-foreground:           var(foreground)/g' \
        -e 's/alternate-urgent-foreground:[[:space:]]*var(background)/alternate-urgent-foreground:  var(foreground)/g' \
        -e 's/selected-active-foreground:[[:space:]]*var(background)/selected-active-foreground:  var(foreground)/g' \
        -e 's/active-foreground:[[:space:]]*var(background)/active-foreground:           var(primary-fg)/g' \
        -e 's/selected-urgent-foreground:[[:space:]]*var(background)/selected-urgent-foreground:  var(primary-fg)/g' \
        -e 's/alternate-active-foreground:[[:space:]]*var(background)/alternate-active-foreground:  var(primary-fg)/g' \
        -e 's/text-color:[[:space:]]*@background;/text-color:                  @foreground;/g' \
        -e 's/text-color:[[:space:]]*var(background);/text-color:                  var(foreground);/g' \
        "$rasi" >"$file"

    # element-text blocks often inherit broken colors with markup rows in applets
    if grep -q '^element-text {' "$file" && ! grep -A6 '^element-text {' "$file" | grep -q 'text-color:'; then
        sed -i '/^element-text {/a\    text-color:                  var(foreground);' "$file"
    fi

    mv "$file" "$rasi"
}

patch_rofi_launcher_styles() {
    local dest="${1:-$HOME/.config/rofi}"
    local rasi

    while IFS= read -r -d '' rasi; do
        patch_rofi_rasi_contrast "$rasi"
    done < <(find "$dest/launchers" "$dest/applets" "$dest/powermenu" -name '*.rasi' -print0 2>/dev/null)

    [[ -f "$dest/wallpaper.rasi" ]] && patch_rofi_rasi_contrast "$dest/wallpaper.rasi"
}

deploy_rofi_colors() {
    local theme="$1"
    local dest="${2:-$HOME/.config/rofi}"
    local colors_out="$dest/colors/hypraesthetic.rasi"
    local shared_colors="$dest/launchers/type-1/shared/colors.rasi"

    mkdir -p "$dest/colors"
    render_theme_rofi_file "$theme" "colors.rasi" "$colors_out"

    if [[ -d "$(dirname "$shared_colors")" ]]; then
        cat >"$shared_colors" <<EOF
/**
 * HyprAesthetic dynamic colors from theme.toml
 */
@import "$colors_out"
EOF
    fi

    patch_rofi_launcher_styles "$dest"

    echo "$colors_out"
}

deploy_wallpaper_picker_rasi() {
    local theme="${1:-$(get_current_theme)}"
    local dest="${2:-$HOME/.config/rofi}"
    local out="$dest/wallpaper.rasi"
    local fonts_file font_line

    mkdir -p "$dest"
    render_theme_rofi_file "$theme" "wallpaper.rasi" "$out"
    patch_rofi_rasi_contrast "$out"

    if fonts_file=$(resolve_rofi_fonts_file "$theme"); then
        font_line=$(grep -E '^\s*font:' "$fonts_file" 2>/dev/null | head -1 | sed 's/^[[:space:]]*//' || true)
        if [[ -n "$font_line" ]]; then
            awk -v font="$font_line" '
                /^\* \{/ && !done {
                    print
                    print "    " font
                    done=1
                    next
                }
                { print }
            ' "$out" >"$out.tmp"
            mv "$out.tmp" "$out"
        fi
    fi

    echo "$out"
}
