#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/template-engine.sh"
source "$SCRIPT_DIR/lib/rofi-theme-style.sh"
source "$SCRIPT_DIR/lib/eww-widgets.sh"

THEMES_DIR="$PROJECT_ROOT/themes"
CONFIG_DIR="$PROJECT_ROOT/config"

list_themes() {
    list_theme_names
}

theme_exists() {
    [[ -d "$THEMES_DIR/$1" ]]
}

validate_theme() {
    local theme="$1"
    theme_exists "$theme" || die "Theme not found: $theme (run 'ha-theme list' to see available)"
    [[ -f "$THEMES_DIR/$theme/theme.toml" ]] || die "Theme missing theme.toml: $theme"
}

deploy_hyprland_config() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local template_dir="$THEMES_DIR/_template/hypr"
    local output_dir="$CONFIG_DIR/hypr"
    local vars_file="/tmp/ha_vars_$.sh"

    prepare_theme_vars "$theme_dir" "$vars_file"
    render_template_dir "$template_dir" "$output_dir" "$vars_file"

    mkdir -p "$HOME/.config/hypr"
    cp -r "$output_dir"/* "$HOME/.config/hypr/"

    # Shared autostart — never spawn processes on hyprland.start (fires on every reload)
    cp "$template_dir/autostart.lua" "$HOME/.config/hypr/autostart.lua"

    if [[ -d "$THEMES_DIR/$theme/hypr" ]]; then
        for hypr_file in "$THEMES_DIR/$theme/hypr"/*.lua; do
            [[ -f "$hypr_file" ]] || continue
            [[ "$(basename "$hypr_file")" == "autostart.lua" ]] && continue
            cp "$hypr_file" "$HOME/.config/hypr/"
        done
        for hypr_conf in monitors.conf workspaces.conf; do
            [[ -f "$THEMES_DIR/$theme/hypr/$hypr_conf" ]] && cp "$THEMES_DIR/$theme/hypr/$hypr_conf" "$HOME/.config/hypr/"
        done
    fi

    rm -f "$vars_file"
}

reload_hyprland() {
    if pgrep -x Hyprland >/dev/null; then
        hyprctl reload >/dev/null 2>&1 || true
    fi
}

switch_hyprland() {
    local theme="$1"
    local reload="${2:-true}"
    deploy_hyprland_config "$theme"
    [[ "$reload" == "true" ]] && reload_hyprland
    log_success "Hyprland configured"
}

switch_wallpaper() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"

    local wallpaper="$(parse_toml "$theme_dir/theme.toml" | grep '^misc_wallpaper=' | cut -d= -f2- | tr -d '"' || true)"

    if [[ -z "$wallpaper" ]]; then
        log_warn "No wallpaper defined for theme: $theme"
        return 0
    fi

    local wallpaper_path="$HOME/.wallpapers/$wallpaper"
    if [[ ! -f "$wallpaper_path" ]]; then
        log_warn "Wallpaper not found: $wallpaper_path"
        return 0
    fi

    local tool
    if command -v awww >/dev/null 2>&1; then
        tool="awww"
    elif command -v swww >/dev/null 2>&1; then
        tool="swww"
    else
        log_warn "Neither awww nor swww installed - skipping wallpaper"
        return 0
    fi

    if ! pgrep -x "${tool}-daemon" >/dev/null; then
        "${tool}-daemon" >/dev/null 2>&1 &
        disown 2>/dev/null || true
        sleep 0.5
    fi

    "$tool" img "$wallpaper_path" --transition-type none >/dev/null 2>&1 || log_warn "Failed to set wallpaper: $wallpaper_path"

    log_success "Wallpaper set: $wallpaper_path"
}

switch_waybar() {
    local theme="$1"
    local restart="${2:-false}"
    local theme_dir="$THEMES_DIR/$theme"
    local template_dir="$THEMES_DIR/_template/waybar"
    local output_dir="$CONFIG_DIR/waybar"
    local vars_file="/tmp/ha_vars_$.sh"
    
    prepare_theme_vars "$theme_dir" "$vars_file"
    render_template_dir "$template_dir" "$output_dir" "$vars_file"
 
    rm -rf "$HOME/.config/waybar"
    mkdir -p "$HOME/.config/waybar"
    cp -r "$theme_dir/waybar" "$HOME/.config/"

    # Always apply palette from theme.toml
    if [[ -f "$output_dir/colors.css" ]]; then
        cp "$output_dir/colors.css" "$HOME/.config/waybar/colors.css"
    elif [[ -f "$theme_dir/waybar/colors.css" ]]; then
        cp "$theme_dir/waybar/colors.css" "$HOME/.config/waybar/colors.css"
    fi
    
    if [[ "$restart" == "true" ]]; then
        if pgrep -x waybar >/dev/null; then
            pkill waybar
            sleep 0.2
        fi
        hyprctl dispatch 'hl.dsp.exec_cmd("waybar")'
    fi
    
    rm -f "$vars_file"
    log_success "Waybar configured"
}

switch_hyprwave() {
    local theme="$1"
    local restart="${2:-false}"
    local theme_dir="$THEMES_DIR/$theme"
    local template_dir="$THEMES_DIR/_template/hyprwave"
    local output_dir="$CONFIG_DIR/hyprwave"
    local vars_file="/tmp/ha_vars_$.sh"

    mkdir -p "$HOME/.config/hyprwave"

    if [[ -f "$theme_dir/hyprwave/config.toml" ]]; then
        cp "$theme_dir/hyprwave/config.toml" "$HOME/.config/hyprwave/"
    elif [[ -f "$theme_dir/hyprwave/config.conf" ]]; then
        cp "$theme_dir/hyprwave/config.conf" "$HOME/.config/hyprwave/"
    else
        prepare_theme_vars "$theme_dir" "$vars_file"
        render_template_dir "$template_dir" "$output_dir" "$vars_file"
        cp -r "$output_dir"/* "$HOME/.config/hyprwave/"
        rm -f "$vars_file"
    fi
    
    if [[ "$restart" == "true" ]]; then
        if pgrep -x hyprwave >/dev/null; then
            pkill hyprwave
            sleep 0.2
        fi
        hyprctl dispatch 'hl.dsp.exec_cmd("hyprwave")'
    fi
    
    log_success "Hyprwave configured"
}

_get_eww_widgets_for_theme() {
    local theme_dir="$1"
    local -a widgets=()
    local w

    while IFS= read -r w; do
        [[ -n "$w" ]] && widgets+=("$w")
    done < <(get_toml_array "$theme_dir/theme.toml" "eww.default_widgets")

    if [[ ${#widgets[@]} -eq 0 ]]; then
        while IFS= read -r w; do
            [[ -n "$w" ]] && widgets+=("$w")
        done < <(get_toml_array "$THEMES_DIR/toji/theme.toml" "eww.default_widgets")
    fi

    printf '%s\n' "${widgets[@]}"
}

_deploy_eww_config() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local eww_src="$theme_dir/eww"
    local dest="$HOME/.config/eww"
    local fallback_src=""

    # Replacing a symlink removes the config path and kills a running daemon.
    if [[ -L "$dest" ]]; then
        kill_all_eww
        rm -f "$dest"
    fi

    mkdir -p "$dest"

    if [[ -d "$eww_src" ]] && eww_layout_has_windows "$eww_src"; then
        rsync -a --delete "$eww_src/" "$dest/"
    elif fallback_src="$(resolve_fallback_theme_dir "eww" "toji" || true)" && [[ -n "$fallback_src" ]]; then
        log_info "Using fallback eww layout from $(basename "$(dirname "$fallback_src")")"
        rsync -a --delete "$fallback_src/" "$dest/"
        [[ -f "$eww_src/eww.scss" ]] && cp "$eww_src/eww.scss" "$dest/eww.scss"
    else
        local template_dir="$THEMES_DIR/_template/eww"
        local output_dir="$CONFIG_DIR/eww"
        local vars_file="/tmp/ha_vars_$.sh"

        prepare_theme_vars "$theme_dir" "$vars_file"
        render_template_dir "$template_dir" "$output_dir" "$vars_file"
        rsync -a "$output_dir/" "$dest/"
        rm -f "$vars_file"
    fi
}

_show_eww_widgets() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local old_hash new_hash screen
    local -a widgets=()

    old_hash="$(eww_config_hash "$(eww_config_dir)")"
    mapfile -t widgets < <(_get_eww_widgets_for_theme "$theme_dir")

    mkdir -p "$(dirname "$_EWW_LOCK_FILE")"
    (
        flock -w 20 200 || die "Timed out waiting for eww lock"

        _deploy_eww_config "$theme"
        new_hash="$(eww_config_hash "$(eww_config_dir)")"
        screen="$(get_primary_screen)"

        if eww ping >/dev/null 2>&1 && [[ "$old_hash" == "$new_hash" ]] && eww_widgets_match "${widgets[@]}"; then
            if eww reload >/dev/null 2>&1; then
                log_success "Eww configured"
                flock -u 200
                return 0
            fi
            log_warn "Eww reload failed — restarting daemon"
        fi

        if eww ping >/dev/null 2>&1 && [[ "$old_hash" == "$new_hash" ]]; then
            close_all_eww_windows
            if eww reload >/dev/null 2>&1; then
                if [[ ${#widgets[@]} -gt 0 ]]; then
                    open_eww_widgets "$screen" "${widgets[@]}" || log_warn "Some eww widgets failed to open"
                    log_info "Opened eww widgets: ${widgets[*]}"
                fi
                log_success "Eww configured"
                flock -u 200
                return 0
            fi
            log_warn "Eww reload failed — restarting daemon"
        fi

        kill_all_eww
        ensure_eww_daemon || die "Failed to start eww daemon"

        if [[ ${#widgets[@]} -gt 0 ]]; then
            open_eww_widgets "$screen" "${widgets[@]}" || log_warn "Some eww widgets failed to open"
            log_info "Opened eww widgets: ${widgets[*]}"
        fi

        log_success "Eww configured"
        flock -u 200
    ) 200>"$_EWW_LOCK_FILE"
}

switch_eww() {
    local theme="$1"
    local phase="${2:-show}"

    case "$phase" in
        hide)
            hide_eww_widgets
            ;;
        show)
            _show_eww_widgets "$theme"
            ;;
        *)
            die "Unknown eww switch phase: $phase"
            ;;
    esac
}

switch_rofi() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme/rofi"
    local dest="$HOME/.config/rofi"
    local fallback_dir item file

    mkdir -p "$dest"

    if [[ ! -d "$theme_dir" ]]; then
        fallback_dir=$(resolve_fallback_theme_dir "rofi" "toji" || true)
        if [[ -n "$fallback_dir" ]]; then
            log_info "Using fallback rofi layout from $(basename "$(dirname "$fallback_dir")")"
            theme_dir="$fallback_dir"
        fi
    fi

    if [[ -d "$theme_dir" ]]; then
        for item in launchers powermenu applets colors images scripts; do
            if [[ -d "$theme_dir/$item" ]]; then
                rm -rf "$dest/$item"
                cp -r "$theme_dir/$item" "$dest/"
            fi
        done

        for file in config.rasi style.rasi; do
            if [[ -f "$theme_dir/$file" ]]; then
                ln -sf "$theme_dir/$file" "$dest/$file"
            fi
        done
    else
        log_warn "No rofi layout available for theme: $theme"
    fi

    deploy_rofi_colors "$theme" "$dest" >/dev/null
    deploy_wallpaper_picker_rasi "$theme" "$dest" >/dev/null

    log_success "Rofi configured"
}

switch_kitty() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local template="$THEMES_DIR/_template/kitty/kitty.conf.template"
    local vars_file="/tmp/ha_vars_$.sh"
    local rendered="$CONFIG_DIR/kitty/kitty.conf"

    mkdir -p "$HOME/.config/kitty" "$CONFIG_DIR/kitty"

    if [[ -f "$template" ]]; then
        prepare_theme_vars "$theme_dir" "$vars_file"
        render_template "$template" "$rendered" "$vars_file"
        rm -f "$vars_file"
    fi

    local dest_kitty="$HOME/.config/kitty/kitty.conf"
    local extra_kitty="$theme_dir/kitty/kitty.conf"

    rm -f "$dest_kitty"

    {
        [[ -f "$rendered" ]] && cat "$rendered"
        [[ -f "$extra_kitty" ]] && cat "$extra_kitty"
    } >"$dest_kitty"

    if pgrep -x kitty >/dev/null; then
        killall -USR1 kitty 2>/dev/null || true
    fi

    log_success "Kitty configured"
}

switch_gtk() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local gtk_src="$theme_dir/gtk"
    local fallback_gtk

    mkdir -p "$HOME/.config/gtk-3.0" "$HOME/.config/gtk-4.0"

    if [[ ! -d "$gtk_src" ]]; then
        fallback_gtk=$(resolve_fallback_theme_dir "gtk" "a70" || true)
        [[ -n "$fallback_gtk" ]] && gtk_src="$fallback_gtk"
    fi

    if [[ -f "$gtk_src/gtk-3.0/settings.ini" ]]; then
        ln -sf "$gtk_src/gtk-3.0/settings.ini" "$HOME/.config/gtk-3.0/settings.ini"
    fi
    if [[ -f "$gtk_src/gtk-4.0/settings.ini" ]]; then
        ln -sf "$gtk_src/gtk-4.0/settings.ini" "$HOME/.config/gtk-4.0/settings.ini"
    fi
    
    if command -v gsettings >/dev/null && [[ -f "$gtk_src/gtk-3.0/settings.ini" ]]; then
        local gtk_theme
        gtk_theme=$(grep -i 'gtk-theme-name' "$gtk_src/gtk-3.0/settings.ini" 2>/dev/null | cut -d= -f2 | tr -d ' ' || true)
        [[ -n "$gtk_theme" ]] && gsettings set org.gnome.desktop.interface gtk-theme "$gtk_theme" 2>/dev/null || true
    fi
    
    log_success "GTK configured"
}

switch_dunst() {
    local theme="$1"
    local restart="${2:-false}"
    local theme_dir="$THEMES_DIR/$theme"
    local template="$THEMES_DIR/_template/dunst/dunst.conf.template"
    local vars_file="/tmp/ha_vars_$.sh"
    local rendered="$CONFIG_DIR/dunst/dunst.conf"

    mkdir -p "$HOME/.config/dunst" "$CONFIG_DIR/dunst"

    if [[ -f "$template" ]]; then
        prepare_theme_vars "$theme_dir" "$vars_file"
        render_template "$template" "$rendered" "$vars_file"
        cp "$rendered" "$HOME/.config/dunst/dunst.conf"
        rm -f "$vars_file"
    elif [[ -f "$theme_dir/dunst/dunst.conf" ]]; then
        ln -sf "$theme_dir/dunst/dunst.conf" "$HOME/.config/dunst/dunst.conf"
    fi

    if [[ "$restart" == "true" ]] && command -v dunst >/dev/null 2>&1; then
        if pgrep -x dunst >/dev/null; then
            pkill dunst
            sleep 0.2
        fi
        dunst &
    fi
    
    log_success "Dunst configured"
}

switch_nvim() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    local template="$THEMES_DIR/_template/nvim/current_theme.lua.template"
    local vars_file="/tmp/ha_vars_$.sh"
    local rendered="$CONFIG_DIR/nvim/current_theme.lua"
    local theme_lua="$theme_dir/nvim/lua/themes/${theme}.lua"

    mkdir -p "$HOME/.config/nvim/lua/themes" "$CONFIG_DIR/nvim"

    if [[ -f "$theme_lua" ]]; then
        ln -sf "$theme_lua" "$HOME/.config/nvim/lua/themes/current_theme.lua"
    elif [[ -f "$template" ]]; then
        prepare_theme_vars "$theme_dir" "$vars_file"
        render_template "$template" "$rendered" "$vars_file"
        cp "$rendered" "$HOME/.config/nvim/lua/themes/current_theme.lua"
        rm -f "$vars_file"
    fi

    log_success "Neovim theme configured"
}

switch_theme() {
    local theme="$1"
    local dry_run="${2:-false}"
    local restart="${3:-false}"
    
    validate_theme "$theme"
    
    log_info "Switching to theme: $theme"
    
    if [[ "$dry_run" == "true" ]]; then
        log_info "DRY RUN - would switch:"
        echo "  - Hyprland (template)"
        echo "  - Wallpaper (awww/swww)"
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
    
    # Eww hides first and shows last so widgets don't overlap the in-progress switch.
    hide_eww_widgets

    # Deploy hypr config without reload first — reload mid-switch races with eww/waybar
    deploy_hyprland_config "$theme"
    switch_wallpaper "$theme"
    switch_waybar "$theme" "$restart"
    switch_hyprwave "$theme" "$restart"
    switch_rofi "$theme"
    switch_kitty "$theme"
    switch_gtk "$theme"
    switch_dunst "$theme" "$restart"
    switch_nvim "$theme"
    reload_hyprland

    switch_eww "$theme" show

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
            [[ -n "${2:-}" ]] || die "Usage: $0 switch <theme> [--dry-run] [--restart]"
            local dry_run="false"
            local restart="false"
            [[ "${3:-}" == "--dry-run" ]] && dry_run="true"
            [[ "${4:-}" == "--restart" ]] && restart="true"
            [[ "${3:-}" == "--restart" ]] && restart="true"
            switch_theme "$2" "$dry_run" "$restart"
            ;;
        switch-hyprland) switch_hyprland "${2:-}" ;;
        switch-wallpaper) switch_wallpaper "${2:-}" ;;
        switch-waybar)
            local theme="${2:-}"
            local restart="${3:-false}"
            [[ "$restart" == "--restart" ]] && restart="true"
            switch_waybar "$theme" "$restart"
            ;;
        switch-hyprwave)
            local theme="${2:-}"
            local restart="${3:-false}"
            [[ "$restart" == "--restart" ]] && restart="true"
            switch_hyprwave "$theme" "$restart"
            ;;
        switch-eww)
            local theme="${2:-$(get_current_theme)}"
            [[ -n "$theme" ]] || die "No theme set (run ha-theme switch <theme> first)"
            switch_eww "$theme" show
            ;;
        switch-rofi) switch_rofi "${2:-}" ;;
        switch-kitty) switch_kitty "${2:-}" ;;
        switch-gtk) switch_gtk "${2:-}" ;;
        switch-dunst)
            local theme="${2:-}"
            local restart="${3:-false}"
            [[ "$restart" == "--restart" ]] && restart="true"
            switch_dunst "$theme" "$restart"
            ;;
        switch-nvim) switch_nvim "${2:-}" ;;
        menu)
            local restart="false"
            [[ "${2:-}" == "--restart" ]] && restart="true"
            if [[ "$restart" == "true" ]]; then
                "$SCRIPT_DIR/rofi-theme-menu.sh" --restart
            else
                "$SCRIPT_DIR/rofi-theme-menu.sh"
            fi
            ;;
        wallpaper-menu)
            "$SCRIPT_DIR/rofi-wallpaper-menu.sh"
            ;;
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
        validate)
            "$SCRIPT_DIR/validate-themes.sh" "${2:-}"
            ;;
        validate-rofi)
            "$SCRIPT_DIR/validate-rofi-contrast.sh" "${2:-}" "${3:-}"
            ;;
        session-start)
            "$SCRIPT_DIR/session-start.sh"
            ;;
        *) die "Usage: $0 {list|current|validate [theme]|menu [--restart]|switch <theme> [--dry-run] [--restart]|switch-<component> <theme> [--restart]|backup|restore [timestamp]|doctor}" ;;
    esac
}

main "$@"
