#!/usr/bin/bash
# HyprAesthetic Auto-Installer for Arch Linux / CachyOS
# Run on a minimal installation as a regular user (not root)

set -euo pipefail

USER_NAME=$(whoami)
REPO_URL="https://github.com/TheLinuxGuy-ssh/HyprAesthetic"
REPO_DIR="HyprAesthetic"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err() { echo -e "${RED}[ERR]${NC} $*"; }

# ─── Pre-flight checks ──────────────────────────────────────────────

check_os() {
    if [[ ! -f /etc/os-release ]]; then
        log_err "Cannot detect OS (/etc/os-release missing)"
        exit 1
    fi
    . /etc/os-release
    if [[ "$ID" != "arch" && "$ID" != "cachyos" ]]; then
        log_err "Unsupported OS: $ID (only Arch Linux and CachyOS supported)"
        exit 1
    fi
    log_ok "OS detected: $PRETTY_NAME"
}

check_not_root() {
    if [[ "$USER_NAME" == "root" ]]; then
        log_err "Do not run as root. Run as your regular user."
        exit 1
    fi
    log_ok "Running as user: $USER_NAME"
}

check_internet() {
    if ! ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
        log_err "No internet connection. Please connect and retry."
        exit 1
    fi
    log_ok "Internet connectivity verified"
}

# ─── AUR helper selection ───────────────────────────────────────────

select_aur_helper() {
    # First, check if yay or paru is already installed
    if command -v yay &>/dev/null; then
        AUR_HELPER="yay"
        log_ok "Found existing AUR helper: yay"
        return
    elif command -v paru &>/dev/null; then
        AUR_HELPER="paru"
        log_ok "Found existing AUR helper: paru"
        return
    fi

    # Neither installed - prompt user
    echo
    echo "Select AUR helper to install:"
    echo "  1) yay  (default, written in Go)"
    echo "  2) paru (written in Rust, faster)"
    echo
    read -rp "Choice [1-2] (default: 1): " choice
    choice=${choice:-1}

    case "$choice" in
        1) AUR_HELPER="yay" ;;
        2) AUR_HELPER="paru" ;;
        *) log_err "Invalid choice"; exit 1 ;;
    esac
    log_ok "Selected AUR helper: $AUR_HELPER"
}

install_aur_helper() {
    if command -v "$AUR_HELPER" &>/dev/null; then
        log_ok "$AUR_HELPER already installed"
        return
    fi

    log_info "Installing $AUR_HELPER..."
    sudo pacman -S --needed --noconfirm base-devel git

    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir"
    git clone "https://aur.archlinux.org/$AUR_HELPER.git"
    cd "$AUR_HELPER"
    makepkg -si --noconfirm
    cd /
    rm -rf "$tmpdir"

    if ! command -v "$AUR_HELPER" &>/dev/null; then
        log_err "Failed to install $AUR_HELPER"
        exit 1
    fi
    log_ok "$AUR_HELPER installed"
}

# ─── Package installation ───────────────────────────────────────────

install_packages() {
    local pkgs=("$@")
    log_info "Installing ${#pkgs[@]} packages via pacman..."
    sudo pacman -S --needed --noconfirm "${pkgs[@]}"
}

install_aur_packages() {
    local pkgs=("$@")
    if [[ ${#pkgs[@]} -eq 0 ]]; then
        return
    fi
    log_info "Installing ${#pkgs[@]} AUR packages via $AUR_HELPER..."
    "$AUR_HELPER" -S --needed --noconfirm "${pkgs[@]}"
}

# ─── Main package lists ─────────────────────────────────────────────

# Base required packages (from data/packages.toml -> arch family)
BASE_PACKAGES=(
    # Hyprland core
    hyprland
    xdg-desktop-portal-hyprland
    xdg-desktop-portal
    polkit-gnome

    # Fonts & icons
    ttf-jetbrains-mono-nerd
    ttf-iosevka-nerd
    noto-fonts-emoji
    papirus-icon-theme

    # Wayland utilities
    wl-clipboard
    cliphist
    grim
    slurp
    hyprpicker

    # GTK
    gtk3
    gtk4

    # Python
    python

    # Wallpaper daemon
    swww

    # Display manager
    gdm

    # System services
    networkmanager
    bluez
    bluez-utils

    # Audio (PipeWire)
    pipewire

    # Utils
    nano
    git
    pacman-contrib
)

# Automatic selection packages (from data/packages.toml -> arch family)
AUTO_PACKAGES=(
    waybar
    rofi-wayland
    kitty
    nautilus
    dunst
    neovim
    python-gobject
    libadwaita
)

# AUR packages for automatic selection
AUR_AUTO_PACKAGES=(
    eww-git
    hyprwave
)

# ─── GDM setup ──────────────────────────────────────────────────────

setup_gdm() {
    log_info "Configuring GDM..."
    sudo systemctl enable gdm
    log_ok "GDM enabled"
}

# ─── Clone repo & deploy configs ──────────────────────────────

clone_and_install() {
    # Check if we're already in the HyprAesthetic repo root
    if [[ -f "ha-theme" ]] && git remote get-url origin 2>/dev/null | grep -q "HyprAesthetic"; then
        log_info "Already in HyprAesthetic repo, using current directory..."
        REPO_DIR="."
    else
        log_info "Cloning HyprAesthetic..."
        if [[ -d "$REPO_DIR" ]]; then
            log_warn "Directory $REPO_DIR exists, pulling latest..."
            cd "$REPO_DIR"
            git pull
        else
            git clone "$REPO_URL"
            cd "$REPO_DIR"
        fi
    fi

    # Fix toji_2 wallpaper filename mismatch
    if [[ -f "themes/toji_2/toji_2.png" && ! -f "themes/toji_2/toji_red.png" ]]; then
        log_info "Fixing toji_2 wallpaper filename..."
        mv "themes/toji_2/toji_2.png" "themes/toji_2/toji_red.png"
    fi

    chmod +x ha-theme

    # 1. Save AUTOMATIC_SELECTION to prefs.toml
    log_info "Saving automatic selection to prefs.toml..."
    python3 -c "
import sys
sys.path.insert(0, 'src')
from hypraesthetic.prefs import Prefs, AUTOMATIC_SELECTION
prefs = Prefs.load()
for k, v in AUTOMATIC_SELECTION.items():
    prefs.set(k, v)
prefs.save()
print('Saved automatic selection to prefs.toml')
"

    # 2. Create CLI symlinks and add to PATH
    log_info "Creating CLI symlinks..."
    mkdir -p ~/.local/bin
    ln -sf "$(pwd)/ha-theme" ~/.local/bin/ha-theme
    cat > ~/.local/bin/hat <<'EOF'
#!/usr/bin/env bash
exec ha-theme "$@"
EOF
    chmod +x ~/.local/bin/hat
    if [[ -f "$(pwd)/scripts/rofi-wallpaper-menu.sh" ]]; then
        ln -sf "$(pwd)/scripts/rofi-wallpaper-menu.sh" ~/.local/bin/hyprwall
    fi

    # Add ~/.local/bin to shell rc files if not already present
    for rc in ~/.bashrc ~/.zshrc; do
        if [[ -f "$rc" ]] && ! grep -q '\.local/bin' "$rc" 2>/dev/null; then
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$rc"
            log_info "Added ~/.local/bin to PATH in $rc"
        fi
    done

    # 3. Write root config
    log_info "Writing root config..."
    mkdir -p ~/.config/HyprAesthetic
    pwd > ~/.config/HyprAesthetic/root

    # 4. Write session/desktop files
    log_info "Writing session/desktop files..."
    mkdir -p ~/.local/share/applications
    mkdir -p ~/.local/share/wayland-sessions
    cat > ~/.local/share/applications/hyprland.desktop <<'EOF'
[Desktop Entry]
Name=Hyprland
Comment=Hyprland Wayland compositor
Exec=Hyprland
Type=Application
DesktopNames=Hyprland
Keywords=tiling;wayland;compositor;
EOF

    cat > ~/.local/share/applications/hypraesthetic.desktop <<'EOF'
[Desktop Entry]
Name=HyprAesthetic
Comment=Hyprland made easy
Exec=ha-theme gui
Icon=preferences-desktop-theme
Terminal=false
Type=Application
Categories=Settings;DesktopSettings;
EOF

    cp ~/.local/share/applications/hyprland.desktop ~/.local/share/wayland-sessions/hyprland.desktop

    # 5. Run backup before config deploy
    log_info "Running backup..."
    ./scripts/backup-configs.sh backup

    # 6. Deploy configs via ApplyEngine (sky theme)
    log_info "Deploying HyprAesthetic configs (automatic mode, sky theme)..."
    python3 -c "
import sys
sys.path.insert(0, 'src')
from hypraesthetic.apply import ApplyEngine
from pathlib import Path

engine = ApplyEngine(live=True, repo_root=Path('.'))
result = engine.apply('sky', restart=False)
if result.errors:
    for err in result.errors:
        print(f'error: {err}', file=sys.stderr)
    sys.exit(1)
print('Theme applied:', result.theme)
print('Components:', ', '.join(result.applied))
"

    log_ok "HyprAesthetic installed"
}

# ─── Enable services ────────────────────────────────────────────────

enable_services() {
    log_info "Enabling system services..."
    sudo systemctl enable NetworkManager
    sudo systemctl enable bluetooth
    log_ok "Services enabled"
}

# ─── Final steps ────────────────────────────────────────────────────

print_summary() {
    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  HyprAesthetic installation complete!                     ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo
    echo "What was installed:"
    echo "  • Hyprland + required portals & polkit"
    echo "  • Waybar, Rofi, Kitty, Nautilus, Dunst, Neovim"
    echo "  • Eww (widgets) + Hyprwave (media island) from AUR"
    echo "  • Fonts: JetBrainsMono Nerd, Iosevka Nerd, Noto Emoji"
    echo "  • Wallpaper daemon (swww) with session-start autostart"
    echo "  • GDM display manager (enabled)"
    echo "  • NetworkManager, Bluetooth (enabled)"
    echo
    echo "Default theme: sky"
    echo
    echo "Next steps:"
    echo "  1. Reboot into GDM → select Hyprland session"
    echo "  2. Run 'ha-theme gui' for the control center"
    echo "  3. Run 'hyprwall' to pick wallpapers"
    echo
}

prompt_reboot() {
    echo
    read -rp "$(echo -e "${YELLOW}Reboot now? [y/N]: ${NC}")" reboot_choice
    if [[ "$reboot_choice" =~ ^[Yy]$ ]]; then
        log_info "Rebooting..."
        sudo reboot
    else
        log_info "Reboot skipped. Run 'sudo reboot' when ready."
    fi
}

# ─── Main ───────────────────────────────────────────────────────────

main() {
    clear
    cat <<'EOF'
██╗  ██╗██╗   ██╗██████╗ ██████╗  █████╗ ███████╗███████╗████████╗██╗  ██╗███████╗████████╗██╗ ██████╗
██║  ██║╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝╚══██╔══╝██║  ██║██╔════╝╚══██╔══╝██║██╔════╝
███████║ ╚████╔╝ ██████╔╝██████╔╝███████║█████╗  ███████╗   ██║   ███████║█████╗     ██║   ██║██║     
██╔══██║  ╚██╔╝  ██╔═══╝ ██╔══██╗██╔══██║██╔══╝  ╚════██║   ██║   ██╔══██║██╔══╝     ██║   ██║██║     
██║  ██║   ██║   ██║     ██║  ██║██║  ██║███████╗███████║   ██║   ██║  ██║███████╗   ██║   ██║╚██████╗
╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝ ╚═════╝
                                                                                                      

       HyprAesthetic Auto-Installer for Arch / CachyOS
EOF
    echo

    check_os
    check_not_root
    check_internet

    select_aur_helper

    echo
    read -rp "$(echo -e "${YELLOW}Proceed with installation? [y/N]: ${NC}")" confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled."
        exit 0
    fi

    log_info "Updating package databases..."
    sudo pacman -Sy

    install_aur_helper

    install_packages "${BASE_PACKAGES[@]}"
    install_packages "${AUTO_PACKAGES[@]}"
    install_aur_packages "${AUR_AUTO_PACKAGES[@]}"

    setup_gdm
    enable_services
    clone_and_install

    print_summary
    prompt_reboot
}

main "$@"