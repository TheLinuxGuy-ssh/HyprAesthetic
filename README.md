<img width="1500" height="525" alt="hypraesthetic" src="https://github.com/user-attachments/assets/261e14f7-dc42-4a0d-bcd6-718b5793f7b9" />

# HyprAesthetic

**A modular, extensible theming system for anime-themed Hyprland setups.**

Transform your Hyprland desktop into a cohesive anime aesthetic with one command. Built for ricers who want beautiful, maintainable, and switchable themes.

---

## Features

- **🎨 Multiple Themes** - Cyberpunk, Tokyo Night, Dracula, Gruvbox, and more (extensible)
- **🔄 Instant Switching** - `ha-theme switch <theme>` applies all components atomically
- **🧩 9 Components** - Hyprland, Waybar, Hyprwave, Eww, Rofi, Kitty, GTK, Dunst, Neovim
- **📦 Template Engine** - Base configs + color palettes = zero duplication
- **💾 Auto Backup** - Timestamped backups before every switch
- **🔧 Dependency Management** - Auto-detects distro, installs missing packages
- **🐚 Shell Integration** - `hat` alias, PATH setup, fish/zsh/bash support

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/yourusername/HyprAesthetic
cd HyprAesthetic
./install.sh

# Switch themes anytime
ha-theme switch cyberpunk
# or short alias
hat switch tokyonight
```

---

## Screenshots

### Cyberpunk Theme
![Cyberpunk](screenshots/cyberpunk.png)

*Neon-drenched Night City aesthetic with cyan/blue accents*

### Tokyo Night Theme
![Tokyo Night](screenshots/tokyonight.png)

*Elegant dark theme inspired by VS Code's Tokyo Night*

### Dracula Theme
![Dracula](screenshots/dracula.png)

*Classic purple/pink vampire aesthetic*

---

## Components

| Component | Method | Description |
|-----------|--------|-------------|
| **Hyprland** | Template | Window manager: borders, gaps, animations, colors |
| **Waybar** | Template | Status bar: modules, CSS variables (@define-color) |
| **Hyprwave** | Template | Dynamic media visualizer (Dynamic Island style) |
| **Eww** | Template | Custom widgets: bar, dashboard, system monitors |
| **Rofi/Wofi** | Symlink | Application launcher theming |
| **Kitty** | Symlink | Terminal emulator colors |
| **GTK 3/4** | Symlink | Application theming (settings.ini) |
| **Dunst** | Symlink | Notification daemon styling |
| **Neovim** | Symlink | Editor colorscheme (Lua) |

---

## Installation

### Requirements

- Hyprland ≥ 0.40
- Waybar, Hyprwave, Eww, Rofi, Kitty
- Python 3.11+ (for TOML parsing)
- `envsubst` (gettext package)

### Supported Distros

| Distro | Package Manager | Status |
|--------|----------------|--------|
| Arch / Manjaro / EndeavourOS | pacman + AUR | ✅ Full |
| Fedora / RHEL / CentOS | dnf | ✅ Full |
| Ubuntu / Debian / Mint / Pop | apt | ✅ Full |
| openSUSE | zypper | ✅ Full |
| NixOS | nix | ✅ Full |

### Install Steps

```bash
# 1. Clone
git clone https://github.com/yourusername/HyprAesthetic ~/.local/share/HyprAesthetic
cd ~/.local/share/HyprAesthetic

# 2. Run installer (installs deps, backs up configs, applies theme)
./install.sh

# 3. Restart shell
source ~/.zshrc  # or .bashrc / .config/fish/config.fish

# 4. Enjoy! Switch themes anytime:
hat switch cyberpunk
```

---

## Usage

### Theme Management

```bash
# List available themes
hat list

# Show current theme
hat current

# Switch theme (with preview)
hat switch cyberpunk --dry-run
hat switch cyberpunk

# Switch single component
hat switch-waybar tokyonight
hat switch-hyprland dracula
```

### Backup & Restore

```bash
# Create backup
hat backup

# List backups
hat restore  # shows available timestamps

# Restore specific backup
hat restore 2026-09-15_14-30-00
```

### System Health

```bash
# Check all dependencies
hat doctor

# Manual dependency install/check
./scripts/install-deps.sh install
./scripts/install-deps.sh check
```

### Uninstall

```bash
# Removes symlinks, restores backups
./uninstall.sh
```

---

## Project Structure

```
HyprAesthetic/
├── install.sh              # Main installer
├── uninstall.sh            # Clean uninstaller
├── ha-theme                # CLI entry point (symlink)
├── scripts/
│   ├── theme-switcher.sh   # Core switching logic
│   ├── switch-*.sh         # Per-component scripts
│   ├── backup-configs.sh   # Backup/restore utility
│   ├── install-deps.sh     # Dependency installer
│   └── lib/
│       ├── common.sh       # Shared functions
│       ├── template-engine.sh  # Template rendering
│       └── distro-detect.sh    # Distro/package detection
├── themes/
│   ├── _template/          # Base templates
│   │   ├── hypr/
│   │   ├── waybar/
│   │   ├── hyprwave/
│   │   └── eww/
│   ├── cyberpunk/          # Example theme
│   ├── tokyonight/
│   ├── dracula/
│   └── gruvbox/
└── config/                 # Rendered output (gitignored)
```

---

## Creating Themes

Creating a new theme is as simple as:

```bash
# 1. Copy an existing theme
cp -r themes/cyberpunk themes/mytheme

# 2. Edit the color palette
vim themes/mytheme/theme.toml

# 3. Tweak component colors (optional)
vim themes/mytheme/waybar/colors.css
vim themes/mytheme/hypr/colors.conf

# 4. Test
hat switch mytheme --dry-run
hat switch mytheme
```

See [ADDING_THEMES.md](ADDING_THEMES.md) for complete documentation on:
- Theme.toml structure
- Template vs symlink components
- Adding new components
- Template variable reference
- Best practices

---

## Architecture

### Hybrid Switching Strategy

```
┌─────────────────────────────────────────────────────────┐
│                  ha-theme                      │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Template-    │   │  Template-    │   │  Symlink-     │
│  Based        │   │  Based        │   │  Based        │
│               │   │               │   │               │
│ • Hyprland    │   │ • Hyprwave    │   │ • Rofi        │
│ • Waybar      │   │ • Eww         │   │ • Kitty       │
│               │   │               │   │ • GTK         │
└───────────────┘   └───────────────┘   │ • Dunst       │
                                        │ • Neovim      │
                                        └───────────────┘
```

**Template-based:** Render from base templates + theme color palette
**Symlink-based:** Link theme's complete config files directly

### Template Engine

- Simple `{{VARIABLE}}` substitution via Python
- Theme TOML → flattened key=value → template rendering
- Base templates in `themes/_template/`
- Themes provide only color overrides (minimal maintenance)

---

## Configuration

### Theme.toml Schema

```toml
name = "theme-folder-name"
display_name = "Pretty Name"
description = "Description"
author = "you"
version = "1.0.0"

[colors]           # Base16 palette (16 colors)
base00 = "#..."    # background
base01 = "#..."    # surface
# ... base02-base0F

[colors.hyprland]  # Hyprland-specific derived colors
border_active = "{{colors.base0D}}"
border_inactive = "{{colors.base03}}"
shadow = "{{colors.base00}}aa"

[colors.waybar]    # Waybar CSS variables
background = "{{colors.base00}}"
# ... surface, primary, error, warning, success

[components]       # Enable/disable per theme
hyprland = true
waybar = true
# ...
```

---

## Troubleshooting

### Waybar CSS Errors

**Problem:** `Invalid name of pseudo-class` or `Expected semicolon`

**Solution:** Waybar uses GTK's `@define-color` syntax, not CSS custom properties. Use:
```css
@define-color background #1a1a1a;
background: @background;  /* not var(--background) */
```

### Hyprwave Not Found

**Problem:** `hyprwave (missing)` on Fedora/Ubuntu

**Solution:** Hyprwave isn't in default repos. Install manually:
```bash
# Fedora
sudo dnf copr enable solopasha/hyprland
sudo dnf install hyprwave

# Ubuntu/Debian
# Build from source or use Flatpak
```

### Dunst Not Reloading

**Problem:** Theme applied but notifications still old colors

**Solution:** Dunst doesn't support live reload. The switcher restarts it:
```bash
pkill dunst && dunst &
```

### Fonts Missing

Install Nerd Fonts for icons:
```bash
# Arch
pacman -S ttf-jetbrains-mono-nerd noto-fonts-emoji

# Fedora
dnf install jetbrains-mono-fonts google-noto-emoji-fonts
```

---

## Contributing

1. Fork the repository
2. Create a theme in `themes/yourtheme/`
3. Add screenshots to `screenshots/`
4. Test with `./install.sh` on clean VM
5. Submit PR with theme name in title

See [ADDING_THEMES.md](ADDING_THEMES.md) for detailed guide.

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [Hyprland](https://hyprland.org) - The best Wayland compositor
- [Waybar](https://github.com/Alexays/Waybar) - Highly customizable bar
- [Hyprwave](https://github.com/hyprwm/hyprwave) - Beautiful media visualizer
- [Eww](https://github.com/elkowar/eww) - Standalone widget system
- [Base16](https://github.com/chriskempson/base16) - Color scheme standard
- All theme creators in the ricing community

---

## Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/HyprAesthetic/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/HyprAesthetic/discussions)
- **Discord:** [Hyprland Community](https://discord.gg/hyprland)

---

**Made with ❤️ for the anime ricing community**