# Adding Themes & Components to ha-theme

This guide explains how to extend ha-theme with new themes and components.

---

## Directory Structure Overview

```
ha-theme/
├── themes/
│   ├── _template/          # Base templates for template-based components
│   │   ├── hypr/           # Hyprland templates (.template files)
│   │   ├── waybar/         # Waybar templates
│   │   ├── hyprwave/       # Hyprwave templates
│   │   └── eww/            # Eww templates
│   └── <theme-name>/       # Each theme is a self-contained folder
│       ├── theme.toml      # REQUIRED: Theme metadata + color palette
│       ├── hypr/           # Hyprland configs (colors.conf, or full files)
│       ├── waybar/         # Waybar configs (colors.css, or full files)
│       ├── hyprwave/       # Hyprwave config.toml
│       ├── eww/            # Eww configs (eww.yuck, eww.scss)
│       ├── rofi/           # Rofi config.rasi / style.rasi
│       ├── kitty/          # Kitty kitty.conf
│       ├── gtk/            # GTK settings.ini (gtk-3.0/, gtk-4.0/)
│       ├── dunst/          # Dunst dunst.conf
│       └── nvim/           # Neovim lua/themes/<theme>.lua
├── scripts/
│   ├── theme-switcher.sh   # Main switcher logic
│   ├── switch-<component>.sh  # Per-component switch scripts
│   └── lib/                # Shared libraries
└── config/                 # Rendered output (gitignored)
```

---

## Adding a New Theme

### 1. Create Theme Directory

```bash
mkdir -p themes/mytheme/{hypr,waybar,hyprwave,eww,rofi,kitty,gtk/gtk-3.0,gtk/gtk-4.0,dunst,nvim/lua/themes}
```

### 2. Create `theme.toml` (REQUIRED)

```toml
name = "mytheme"
display_name = "My Theme"
description = "A beautiful anime theme"
author = "yourname"
version = "1.0.0"

[colors]
# Base16 palette (required for template rendering)
base00 = "#1a1a1a"  # background
base01 = "#2a2a2a"  # surface
base02 = "#3a3a3a"  # surface hover
base03 = "#4a4a4a"  # border
base04 = "#aaaaaa"  # foreground muted
base05 = "#ffffff"  # foreground
base06 = "#ffffff"
base07 = "#ffffff"
base08 = "#ff6b6b"  # red
base09 = "#ff9f43"  # orange
base0A = "#ffe66d"  # yellow
base0B = "#69db7c"  # green
base0C = "#5fe4ff"  # cyan
base0D = "#74b9ff"  # blue
base0E = "#a29bfe"  # magenta
base0F = "#ff7675"  # brown

[colors.hyprland]
border_active = "{{colors.base0D}}"
border_inactive = "{{colors.base03}}"
shadow = "{{colors.base00}}aa"

[colors.waybar]
background = "{{colors.base00}}"
foreground = "{{colors.base05}}"
surface = "{{colors.base01}}"
surface_hover = "{{colors.base02}}"
border = "{{colors.base03}}"
foreground_muted = "{{colors.base04}}"
primary = "{{colors.base0D}}"
primary_fg = "{{colors.base00}}"
error = "{{colors.base08}}"
error_fg = "{{colors.base00}}"
warning = "{{colors.base0A}}"
warning_fg = "{{colors.base00}}"
success = "{{colors.base0B}}"
success_fg = "{{colors.base00}}"

[components]
# Enable/disable components for this theme
hyprland = true
waybar = true
hyprwave = true
eww = true
rofi = true
kitty = true
gtk = true
dunst = true
nvim = true
```

**Key Points:**
- `name` must match the folder name
- Use `{{colors.xxx}}` references for derived colors
- All `[colors]` values are available in templates as `{{colors_key}}` (dots become underscores)
- `[components]` controls which components get switched

### 3. Add Component Configurations

#### Template-Based Components (Hyprland, Waybar, Hyprwave, Eww)

**Option A: Provide only color overrides (recommended)**

Create minimal files that work with base templates:

**`hypr/colors.conf`** (for Hyprland):
```ini
# MyTheme Hyprland color overrides
$colors = {
    active_border = #74b9ff
    inactive_border = #3a3a3a
    shadow = #1a1a1a
    bg = #1a1a1a
    fg = #ffffff
    red = #ff6b6b
    green = #69db7c
    yellow = #ffe66d
    blue = #74b9ff
    magenta = #a29bfe
    cyan = #5fe4ff
    orange = #ff9f43
}
```

**`waybar/colors.css`** (for Waybar - GTK4 @define-color syntax):
```css
/* MyTheme Waybar colors */
@define-color background #1a1a1a;
@define-color foreground #ffffff;
@define-color surface #2a2a2a;
@define-color surface_hover #3a3a3a;
@define-color border #4a4a4a;
@define-color foreground_muted #aaaaaa;
@define-color primary #74b9ff;
@define-color primary_fg #1a1a1a;
@define-color error #ff6b6b;
@define-color error_fg #1a1a1a;
@define-color warning #ffe66d;
@define-color warning_fg #1a1a1a;
@define-color success #69db7c;
@define-color success_fg #1a1a1a;
```

**`hyprwave/config.toml`** (full config or override):
```toml
# MyTheme Hyprwave config
[general]
fps = 60
width = 1920
height = 1080

[colors]
background = "#1a1a1a"
foreground = "#ffffff"
primary = "#74b9ff"
secondary = "#a29bfe"
accent = "#5fe4ff"
error = "#ff6b6b"
warning = "#ffe66d"
success = "#69db7c"
```

**`eww/eww.yuck`** and **`eww/eww.scss`** (complete files - Eww uses per-theme layouts):
```scss
// MyTheme Eww SCSS - complete file
$background: #1a1a1a;
$foreground: #ffffff;
$primary: #74b9ff;
// ... rest of variables
```

**Option B: Override base templates completely**

Place full config files in the theme folder (they'll be copied instead of rendered):
- `hypr/hyprland.conf` - full Hyprland config
- `waybar/config.jsonc` + `waybar/style.css` - full Waybar config
- `hyprwave/config.toml` - full Hyprwave config
- `eww/eww.yuck` + `eww/eww.scss` - full Eww config

#### Symlink-Based Components (Rofi, Kitty, GTK, Dunst, Neovim)

Place complete config files - they'll be symlinked to `~/.config/`:

**`rofi/config.rasi`** or **`rofi/style.rasi`**
```rasi
/* MyTheme Rofi theme */
* {
    background: #1a1a1a;
    foreground: #ffffff;
    // ...
}
```

**`kitty/kitty.conf`**
```ini
# MyTheme Kitty config
background #1a1a1a
foreground #ffffff
// ...
```

**`gtk/gtk-3.0/settings.ini`** and **`gtk/gtk-4.0/settings.ini`**
```ini
[Settings]
gtk-theme-name = MyTheme
gtk-icon-theme-name = MyTheme-icons
gtk-font-name = JetBrains Mono 11
```

**`dunst/dunst.conf`**
```ini
[global]
background = "#1a1a1a"
foreground = "#ffffff"
frame_color = "#74b9ff"
// ...
```

**`nvim/lua/themes/mytheme.lua`**
```lua
-- MyTheme Neovim colorscheme
local M = {}

M.setup = function()
  vim.cmd('hi clear')
  vim.g.colors_name = 'mytheme'
  -- Define highlights
  vim.api.nvim_set_hl(0, 'Normal', { bg = '#1a1a1a', fg = '#ffffff' })
  -- ...
end

return M
```

### 4. Test Your Theme

```bash
# Dry run to verify
./ha-theme-theme switch mytheme --dry-run

# Actual switch
./ha-theme-theme switch mytheme

# Verify specific component
./ha-theme-theme switch-waybar mytheme
```

### 5. Verify Rendered Output

```bash
# Check rendered configs
cat ~/.config/waybar/colors.css
cat ~/.config/hypr/colors.conf
cat ~/.config/hyprwave/config.toml
```

---

## Adding a New Component

### 1. Create Switch Script

Create `scripts/switch-mycomponent.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

switch_mycomponent() {
    local theme="$1"
    local theme_dir="$THEMES_DIR/$theme"
    
    mkdir -p "$HOME/.config/mycomponent"
    
    # Template-based rendering
    if [[ -d "$THEMES_DIR/_template/mycomponent" ]]; then
        local vars_file="/tmp/ha-theme_vars_$$.sh"
        prepare_theme_vars "$theme_dir" "$vars_file"
        render_template_dir "$THEMES_DIR/_template/mycomponent" "$CONFIG_DIR/mycomponent" "$vars_file"
        cp -r "$CONFIG_DIR/mycomponent"/* "$HOME/.config/mycomponent/"
        rm -f "$vars_file"
    # Symlink-based (theme provides complete config)
    elif [[ -f "$theme_dir/mycomponent/config.conf" ]]; then
        ln -sf "$theme_dir/mycomponent/config.conf" "$HOME/.config/mycomponent/config.conf"
    fi
    
    # Reload daemon if running
    if pgrep -x mycomponent >/dev/null; then
        mycomponent --reload 2>/dev/null || pkill mycomponent && mycomponent &
    fi
    
    log_success "MyComponent configured"
}

# Allow direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    switch_mycomponent "${1:-}"
fi
```

### 2. Register in Main Switcher

Edit `scripts/theme-switcher.sh`:

```bash
# Add to switch_theme() function:
switch_mycomponent "$theme"

# Add case for direct invocation:
switch-mycomponent) switch_mycomponent "${2:-}" ;;
```

### 3. Add Base Templates (if template-based)

```bash
mkdir -p themes/_template/mycomponent
# Add *.template files with {{colors.xxx}} placeholders
```

### 4. Add to Component Lists

In `scripts/backup-configs.sh` and `uninstall.sh`:
```bash
COMPONENTS=(... "mycomponent")
CONFIG_PATHS["mycomponent"]="$HOME/.config/mycomponent"
```

In `scripts/install-deps.sh` PKGS array for your distro.

---

## Template System Details

### Variable Resolution

Template placeholders use `{{variable_name}}` syntax. Variables come from `theme.toml` flattened:

```toml
[colors.waybar]
background = "#1a1a1a"
```

Becomes: `colors_waybar_background="#1a1a1a"` → usable as `{{colors.waybar.background}}`

### Special Variables

- `{{name}}` - theme name
- `{{display_name}}` - display name
- `{{colors.base00}}` through `{{colors.base0F}}` - base16 palette
- Any nested TOML key flattened with `_` and dots converted to `_`

### Template Functions

```bash
# In template-engine.sh
prepare_theme_vars "$theme_dir" "$vars_file"  # Creates vars file from theme.toml
render_template "$template" "$output" "$vars_file"  # Single file
render_template_dir "$template_dir" "$output_dir" "$vars_file"  # Entire directory
```

---

## Best Practices

### Theme Design
1. **Start from cyberpunk** - Copy `themes/cyberpunk/` and modify
2. **Use base16 palette** - Ensures consistency across all components
3. **Minimal overrides** - Only provide colors.conf/colors.css, let templates handle structure
4. **Test each component** - Use per-component switch commands

### Component Design
1. **Prefer templates** for complex configs (Hyprland, Waybar, Hyprwave)
2. **Use symlinks** for simple configs (Rofi, Kitty, GTK, Dunst, Neovim)
3. **Handle daemon reload** gracefully in switch script
4. **Support dry-run** by checking `$2 == "--dry-run"`

### Maintenance
1. **Keep templates updated** when upstream configs change
2. **Version themes** in theme.toml
3. **Document theme-specific quirks** in theme folder README
4. **Test on clean install** via `./install.sh`

---

## Quick Reference

| Task | Command |
|------|---------|
| List themes | `ha-theme-theme list` |
| Current theme | `ha-theme-theme current` |
| Switch theme | `ha-theme-theme switch <theme>` |
| Dry run | `ha-theme-theme switch <theme> --dry-run` |
| Switch single component | `ha-theme-theme switch-<component> <theme>` |
| Backup configs | `ha-theme-theme backup` |
| Restore backup | `ha-theme-theme restore [timestamp]` |
| Check deps | `ha-theme-theme doctor` |
| Install deps | `./scripts/install-deps.sh install` |

---

## Example: Creating "tokyonight" Theme

```bash
# 1. Copy base
cp -r themes/cyberpunk themes/tokyonight

# 2. Edit theme.toml with Tokyonight colors
# base00 = "#1a1b26", base0D = "#7aa2f7", etc.

# 3. Adjust component colors
# Edit themes/tokyonight/waybar/colors.css
# Edit themes/tokyonight/hypr/colors.conf
# ...

# 4. Test
./ha-theme-theme switch tokyonight --dry-run
./ha-theme-theme switch tokyonight
```