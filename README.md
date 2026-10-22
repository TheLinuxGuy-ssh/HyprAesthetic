# HyprAesthetic

HyprAesthetic is an installer, a theme engine, and a GTK control center for Hyprland. It is not a distro. This release supports Hyprland only.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blue.svg)](https://github.com/thelinuxguy-ssh/HyprAesthetic/actions)

### Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Control center](#control-center)
- [Components](#components)
- [Creating Themes](#creating-themes)
- [Configuration](#configuration)
- [Distros](#distros)
- [Development](#development)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## Features

- Installer with Automatic and Custom modes. Automatic uses the built-in defaults (Hyprland, Waybar, widgets, Kitty, Nautilus, and the project fonts). Custom asks for the bar, widgets, file manager, and terminal.
- Theme packages: a `theme.toml` palette, with optional files under `overrides/` when a theme needs a different layout than `layouts/default/`.
- GTK4/libadwaita control center (`hat gui`).
- CLI. The installer puts `ha-theme` and `hat` in `~/.local/bin`. `hat` execs `ha-theme`.
- Wallpaper and theme previews in GIF, PNG, JPEG, and WebP.
- Per-theme widget layout from `[layout].widgets` in the theme package. The Widgets page can change placement after install.
- Doctor (`hat doctor`) reports required and optional programs. Optional gaps are listed and do not fail the report.

## Installation

```bash
git clone https://github.com/thelinuxguy-ssh/HyprAesthetic ~/.local/share/HyprAesthetic
cd ~/.local/share/HyprAesthetic
./install.sh
```

The installer asks Automatic or Custom, installs packages for the detected distro, backs up the managed config directories (`hypr`, `waybar`, `hyprwave`, `eww`, `rofi`, `kitty`, `gtk-3.0`, `gtk-4.0`, `dunst`, `nvim`), applies a theme, and writes `~/.config/HyprAesthetic/prefs.toml`. It also links `ha-theme`, `hat`, and `hyprwall` into `~/.local/bin`. Custom mode without `--yes` asks before installing packages. Declining, or running it without a terminal, leaves those packages uninstalled and reports an incomplete install.

On a first compositor install, log out and select Hyprland in the display manager.

## Usage

Commands match `ha-theme` usage. `hat` accepts the same arguments.

```bash
hat list
hat current
hat switch <theme> [--dry-run] [--restart]
hat switch-<component> <theme> [--restart]
hat validate [theme]
hat doctor
hat backup
hat restore [timestamp]
hat menu [--restart]
hat wallpaper-menu
hat session-start
hat install [--mode automatic|custom] [--theme NAME] [--yes]
hat install-theme <path-or-git-url>
hat store list
hat store search <query>
hat store install <name-or-url>
hat store refresh [url]
hat prefs get [key]
hat prefs set <key> <value>
hat gui
hat version
```

`switch-<component>` applies one component (for example `switch-waybar` or `switch-wallpaper`). `menu` is the Rofi theme picker. `wallpaper-menu` is the Rofi wallpaper picker (`hyprwall` on `PATH` is that script). `session-start` runs once per Hyprland session. It always applies the wallpaper. It starts cliphist when `wl-paste` and `cliphist` are installed. Waybar, eww, and Hyprwave follow prefs, and start only when those prefs enable them and the binaries exist.

## Control center

`hat gui` needs GTK4, libadwaita, and Python GObject. Pages, in sidebar order:

| Page | What it does |
| --- | --- |
| Presets | Theme tiles. Clicking a tile applies that theme. |
| Bar | Waybar layout, independent of the theme palette. |
| Widgets | Desktop overlays and placement. |
| Fonts | Interface, bar, and terminal fonts. |
| Apps | Default file manager, terminal, browser, and launcher. |
| Look | Wallpaper tiles, GTK theme, icon theme, Hyprwave. |
| Store | Search and install themes. |
| Doctor | Required and optional package checks. Install missing packages runs `hat install --mode automatic --yes`. |

Theme tiles and Look wallpaper tiles show a still image, or an animated GIF when the file is a GIF. Tiles load through GdkPixbuf. A GIF that is static, larger than 8 MB, or larger than 8 million pixels stays on its first frame.

## Components

With `[components]` enabled in `theme.toml`, apply writes Hyprland, Waybar, eww, Hyprwave, Rofi, Kitty, GTK, Dunst, and Neovim. Turning a key off (`waybar = false`, for example) skips that component for the theme. Default apps are a prefs overlay (`~/.config/hypr/hypraesthetic-apps.lua`), not a copy stored inside each theme.

## Creating Themes

Read [ADDING_THEMES.md](ADDING_THEMES.md) and [docs/theme-package.md](docs/theme-package.md).

Official presets shipped in `themes/`:

toji, toji_2, a70, cyberpunk, choso, jjk, sky, tanjiro, tojivsukuna.

A small package:

```text
mytheme/
  theme.toml
  preview.gif     # or preview.png
  wallpaper.gif   # or wallpaper.jpg
```

Shared Waybar, eww, Rofi, and Hyprland files live in `layouts/default/`. Add `overrides/` only when this theme must replace those files.

## Configuration

Preferences are stored in `~/.config/HyprAesthetic/prefs.toml` (`hat prefs get` / `hat prefs set`).

User keybinds and monitor tweaks go in `~/.config/hypr/custom.lua`. The first apply copies a starter file if none exists. Later theme switches do not overwrite it.

Super+A runs the theme picker (`ha-theme menu --restart`). Super+W runs the wallpaper picker (`hyprwall`).

## Distros

Package names cover the Arch family (Arch, Manjaro, EndeavourOS, Garuda), Fedora (including Fedora Asahi Remix), Ubuntu/Debian, openSUSE, and NixOS. The map is [data/packages.toml](data/packages.toml). Hyprwave and eww are optional. On distros with an empty package list for those components, Doctor reports them as optional.

## Development

Requires Python 3.11 or newer (`tomllib`).

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash scripts/ci/run-checks.sh
```

Python sources live in `src/hypraesthetic/` (theme package, apply, prefs, catalog, installer, store) and `src/hypraesthetic_gui/` (the control center). `ha-theme` is the CLI entry point.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md). Report vulnerabilities through a private GitHub advisory or the maintainer email in that file. Do not open a public issue for a security report.

## License

MIT. See [LICENSE](LICENSE).
