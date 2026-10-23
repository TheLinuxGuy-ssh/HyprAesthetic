# Theme package format

A HyprAesthetic theme is a folder with a `theme.toml` manifest. Layouts (Waybar, eww, Rofi, Hyprland chrome) are shared. Most themes only need a palette, wallpaper, and preview.

```
mytheme/
  theme.toml          # required
  preview.png         # or preview.gif (store / thumb)
  desktop.png         # Presets page: 2560×1600 or same 16:10 aspect (e.g. 1280×800)
  wallpaper.jpg       # jpg, png, gif, or webp; or set [misc].wallpaper to a file in ~/.wallpapers
  assets/             # optional character images, quotes
  overrides/          # optional files that replace the shared layout
    waybar/style.css
    eww/eww.yuck
```

Install:

```bash
hat install-theme ./mytheme
hat install-theme https://github.com/you/mytheme.git
hat switch mytheme
```

## theme.toml (schema 2)

```toml
schema = 2
name = "mytheme"                 # must match the folder name
display_name = "My Theme"
description = "One line"
author = "you"
version = "1.0.0"
license = "MIT"
min_hypraesthetic = "0.2.0"
preview = "preview.png"
source = "https://github.com/you/mytheme.git"  # optional, for the store

[misc]
wallpaper = "mytheme.png"
hw_theme = "octane"              # hyprwave CSS name, if you use one

[palette]
base00 = "#0d0d0d"               # background
base01 = "#1a1a1a"               # surface
base02 = "#2a2a2a"
base03 = "#3a3a3a"               # border
base04 = "#cccccc"               # muted text
base05 = "#ffffff"               # text
base06 = "#ffffff"
base07 = "#ffffff"
base08 = "#ff6b6b"
base09 = "#ff9f43"
base0A = "#ffe66d"
base0B = "#69db7c"
base0C = "#5fe4ff"
base0D = "#74b9ff"               # accent
base0E = "#a29bfe"
base0F = "#ff7675"

[colors.hyprland]
border_active = "{{palette.base0D}}"
border_inactive = "{{palette.base03}}"
shadow = "{{palette.base00}}aa"

[colors.waybar]
background = "{{palette.base00}}"
foreground = "{{palette.base05}}"
primary = "{{palette.base0D}}"
# omitted keys fill from the palette

[colors.eww]
background = "{{palette.base00}}"
foreground = "{{palette.base05}}"

[layout]
bar = "waybar"
launcher = "rofi"
widgets = ["clock", "system", "matrix", "wakatime", "toji"]

[defaults]
file_manager = "nautilus"
terminal = "kitty"

[components]
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

`[components]` is honored. `waybar = false` means that theme will not deploy a bar.

Component colors that should not follow the palette (light bar on a dark terminal palette, for example) can be literal hex.

## Validation

```bash
hat validate mytheme
```

Required: identity fields, full base00–base0F palette, resolvable color references.
