#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/template-engine.sh"

THEMES_DIR="$PROJECT_ROOT/themes"
CONFIG_DIR="$PROJECT_ROOT/config"

list_themes() {
    find "$THEMES_DIR" -mindepth 1 -maxdepth 1 -type d ! -name "_template" -printf "%f\n" | sort
}

theme_exists() {
    [[ -d "$THEMES_DIR/$1" ]]
}

validate_theme() {
    local theme="$1"
    theme_exists "$theme" || die "Theme not found: $theme (run 'hypranime-theme list' to see available)"
    [[ -f "$THEMES_DIR/$theme/theme.toml" ]] || die "Theme missing theme.toml: $theme"
}

switch_hyprland() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local template_dir="$THEMES_DIR/_template/hypr"
    local output_dir="$CONFIG_DIR/hypr"
    local vars_file="/tmp/hypranime_vars_$$.sh"
    
    prepare_theme_vars "$theme_dir" "$vars_file"
    render_template_dir "$template_dir" "$output_dir" "$vars_file"
    
    mkdir -p "$HOME/.config/hypr"
    cp -r "$output_dir"/* "$HOME/.config/hypr/"
    
    if pgrep -x Hyprland >/dev/null; then
        hyprctl reload >/dev/null 2>&1 || true
    fi
    
    rm -f "$vars_file"
    log_success "Hyprland configured"
}

switch_waybar() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local template_dir="$THEMES_DIR/_template/waybar"
    local output_dir="$CONFIG_DIR/waybar"
    local vars_file="/tmp/hypranime_vars_$$.sh"
    
    prepare_theme_vars "$theme_dir" "$vars_file"
    render_template_dir "$template_dir" "$output_dir" "$vars_file"
    
    mkdir -p "$HOME/.config/waybar"
    cp -r "$output_dir"/* "$HOME/.config/waybar/"
    
    # Copy theme-specific colors.css if it exists
    if [[ -f "$theme_dir/waybar/colors.css" ]]; then
        cp "$theme_dir/waybar/colors.css" "$HOME/.config/waybar/"
    fi
    
    if pgrep -x waybar >/dev/null; then
        pkill waybar
        sleep 0.2
    fi
    waybar &
    
    rm -f "$vars_file"
    log_success "Waybar configured"
}

switch_hyprwave() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local template_dir="$THEMES_DIR/_template/hyprwave"
    local output_dir="$CONFIG_DIR/hyprwave"
    local vars_file="/tmp/hypranime_vars_$$.sh"
    
    prepare_theme_vars "$theme_dir" "$vars_file"
    render_template_dir "$template_dir" "$output_dir" "$vars_file"
    
    mkdir -p "$HOME/.config/hyprwave"
    cp -r "$output_dir"/* "$HOME/.config/hyprwave/"
    
    if pgrep -x hyprwave >/dev/null; then
        pkill hyprwave
        sleep 0.2
    fi
    hyprwave &
    
    rm -f "$vars_file"
    log_success "Hyprwave configured"
}

switch_eww() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    
    mkdir -p "$HOME/.config/eww"
    
    if [[ -f "$theme_dir/eww/eww.yuck" && -f "$theme_dir/eww/eww.scss" ]]; then
        cp "$theme_dir/eww/eww.yuck" "$HOME/.config/eww/"
        cp "$theme_dir/eww/eww.scss" "$HOME/.config/eww/"
    else
        local template_dir="$THEMES_DIR/_template/eww"
        local output_dir="$CONFIG_DIR/eww"
        local vars_file="/tmp/hypranime_vars_$$.sh"
        
        prepare_theme_vars "$theme_dir" "$vars_file"
        render_template_dir "$template_dir" "$output_dir" "$vars_file"
        
        cp -r "$output_dir"/* "$HOME/.config/eww/"
        rm -f "$vars_file"
    fi
    
    if pgrep -x eww >/dev/null; then
        eww reload >/dev/null 2>&1 || true
    fi
    
    log_success "Eww configured"
}

switch_rofi() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    
    mkdir -p "$HOME/.config/rofi"
    
    if [[ -f "$theme_dir/rofi/config.rasi" ]]; then
        ln -sf "$theme_dir/rofi/config.rasi" "$HOME/.config/rofi/config.rasi"
    elif [[ -f "$theme_dir/rofi/style.rasi" ]]; then
        ln -sf "$theme_dir/rofi/style.rasi" "$HOME/.config/rofi/style.rasi"
    fi
    
    log_success "Rofi configured"
}

switch_kitty() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    
    mkdir -p "$HOME/.config/kitty"
    
    if [[ -f "$theme_dir/kitty/kitty.conf" ]]; then
        ln -sf "$theme_dir/kitty/kitty.conf" "$HOME/.config/kitty/kitty.conf"
    fi
    
    if pgrep -x kitty >/dev/null; then
        killall -USR1 kitty 2>/dev/null || true
    fi
    
    log_success "Kitty configured"
}

switch_gtk() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    
    mkdir -p "$HOME/.config/gtk-3.0" "$HOME/.config/gtk-4.0"
    
    if [[ -f "$theme_dir/gtk/gtk-3.0/settings.ini" ]]; then
        ln -sf "$theme_dir/gtk/gtk-3.0/settings.ini" "$HOME/.config/gtk-3.0/settings.ini"
    fi
    if [[ -f "$theme_dir/gtk/gtk-4.0/settings.ini" ]]; then
        ln -sf "$theme_dir/gtk/gtk-4.0/settings.ini" "$HOME/.config/gtk-4.0/settings.ini"
    fi
    
    if command -v gsettings >/dev/null; then
        local gtk_theme
        gtk_theme=$(grep -i 'gtk-theme-name' "$theme_dir/gtk/gtk-3.0/settings.ini" 2>/dev/null | cut -d= -f2 | tr -d ' ')
        [[ -n "$gtk_theme" ]] && gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" 2>/dev/null || true
    fi
    
    log_success "GTK configured"
}

switch_dunst() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    
    mkdir -p "$HOME/.config/dunst"
    
    if [[ -f "$theme_dir/dunst/dunst.conf" ]]; then
        ln -sf "$theme_dir/dunst/dunst.conf" "$HOME/.config/dunst/dunst.conf"
    fi
    
    if pgrep -x dunst >/dev/null; then
        pkill dunst
        sleep 0.2
    fi
    dunst &
    
    log_success "Dunst configured"
}

switch_nvim() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    
    mkdir -p "$HOME/.config/nvim/lua/themes"
    
    if [[ -f "$theme_dir/nvim/lua/themes/${theme}.lua" ]]; then
        ln -sf "$theme_dir/nvim/lua/themes/${theme}.lua" "$HOME/.config/nvim/lua/themes/current_theme.lua"
    fi
    
    log_success "Neovim theme configured"
}

switch_theme() {
    local theme="$1"
    local dry_run="${2:-false}"
    
    validate_theme "$theme"
    
    log_info "Switching to theme: $theme"
    
    if [[ "$dry_run" == "true" ]]; then
        log_info "DRY RUN - would switch:"
        echo "  - Hyprland (template)"
        echo "  - Waybar (template)"
        echo "  - Hyprwave (template)"
        echo "  - Eww (template/symlink)"
        echo "  - Rofi (symlink)"
        echo "  - Kitty (symlink)"
        echo "  - GTK (symlink)"
        echo "  - Dunst (symlink)"
        echo "  - Neovim (symlink)"
        return
    fi
    
    switch_hyprland "$theme"
    switch_waybar "$theme"
    switch_hyprwave "$theme"
    switch_eww "$theme"
    switch_rofi "$theme"
    switch_kitty "$theme"
    switch_gtk "$theme"
    switch_dunst "$theme"
    switch_nvim "$theme"
    
    set_current_theme "$theme"
    
    log_success "Theme switch complete: $theme"
}

show_current() {
    local current
    current=$(get_current_theme)
    [[ -n "$current" ]] && echo "Current theme: $current" || echo "No theme set"
}

main() {
    case "${1:-}" in
        list) list_themes ;;
        current) show_current ;;
        switch)
            [[ -n "${2:-}" ]] || die "Usage: $0 switch <theme> [--dry-run]"
            local dry_run="false"
            [[ "${3:-}" == "--dry-run" ]] && dry_run="true"
            switch_theme "$2" "$dry_run"
            ;;
        switch-hyprland) switch_hyprland "${2:-}" ;;
        switch-waybar) switch_waybar "${2:-}" ;;
        switch-hyprwave) switch_hyprwave "${2:-}" ;;
        switch-eww) switch_eww "${2:-}" ;;
        switch-rofi) switch_rofi "${2:-}" ;;
        switch-kitty) switch_kitty "${2:-}" ;;
        switch-gtk) switch_gtk "${2:-}" ;;
        switch-dunst) switch_dunst "${2:-}" ;;
        switch-nvim) switch_nvim "${2:-}" ;;
        backup) "$SCRIPT_DIR/backup-configs.sh" backup ;;
        restore) "$SCRIPT_DIR/backup-configs.sh" restore "${2:-}" ;;
        doctor)
            log_info "Checking system..."
            require_cmd hyprland && log_success "hyprland"
            require_cmd waybar && log_success "waybar"
            require_cmd hyprwave && log_success "hyprwave"
            require_cmd eww && log_success "eww"
            require_cmd rofi && log_success "rofi"
            require_cmd kitty && log_success "kitty"
            require_cmd dunst && log_success "dunst"
            require_cmd nvim && log_success "nvim"
            log_success "All core commands available"
            ;;
        *) die "Usage: $0 {list|current|switch <theme> [--dry-run]|switch-<component> <theme>|backup|restore [ts]|doctor}" ;;
    esac
}

main "$@"