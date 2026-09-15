# Contributing to Hypraesthetic

Thank you for your interest in contributing! This guide will help you get started.

## Ways to Contribute

- **Add a new theme** - Create a theme folder in `themes/`
- **Add a new component** - Implement support for another application
- **Improve templates** - Update base templates for better defaults
- **Fix bugs** - Report and fix issues
- **Documentation** - Improve README, ADDING_THEMES.md, or add comments
- **Testing** - Test on different distros/hardware

## Adding a Theme

See [ADDING_THEMES.md](ADDING_THEMES.md) for complete instructions.

**Quick checklist:**
- [ ] Copy `themes/cyberpunk/` to `themes/yourtheme/`
- [ ] Update `theme.toml` with your colors (base16 palette)
- [ ] Adjust component color files (`waybar/colors.css`, `hypr/colors.conf`, etc.)
- [ ] Test with `./Hypraesthetic-theme switch yourtheme --dry-run`
- [ ] Test full switch: `./Hypraesthetic-theme switch yourtheme`
- [ ] Add screenshot to `screenshots/yourtheme.png` (optional but appreciated)
- [ ] Submit PR with title: `Add theme: yourtheme`

## Adding a Component

1. Create `scripts/switch-yourcomponent.sh` following existing patterns
2. Add base templates to `themes/_template/yourcomponent/` (if template-based)
3. Register in `scripts/theme-switcher.sh`:
   - Add to `switch_theme()` function
   - Add case for direct invocation
4. Add to backup/uninstall lists in `scripts/backup-configs.sh` and `uninstall.sh`
5. Add package names to `scripts/install-deps.sh` PKGS array
6. Test thoroughly

## Code Style

### Shell Scripts
- Use `#!/usr/bin/env bash` shebang
- `set -euo pipefail` at top
- 4-space indentation
- Functions named `snake_case`
- Variables: `SCREAMING_SNAKE_CASE` for globals, `snake_case` for locals
- Use `log_info`, `log_success`, `log_warn`, `log_error` from `lib/common.sh`
- Source libraries with `source "$SCRIPT_DIR/lib/common.sh"`

### Templates
- Use `{{variable_name}}` for placeholders
- Keep templates minimal - only structure, no colors
- Document required variables in template header comment

### TOML (theme.toml)
- Use base16 color names (base00-base0F)
- Group related colors in subtables (`[colors.hyprland]`, `[colors.waybar]`)
- Use references: `border_active = "{{colors.base0D}}"`
- Boolean for component toggles in `[components]`

## Testing

Before submitting:
```bash
# Test on clean system (VM recommended)
./install.sh

# Test theme switching
./Hypraesthetic-theme list
./Hypraesthetic-theme switch cyberpunk --dry-run
./Hypraesthetic-theme switch cyberpunk

# Test individual components
./Hypraesthetic-theme switch-waybar tokyonight
./Hypraesthetic-theme switch-hyprwave dracula

# Test backup/restore
./Hypraesthetic-theme backup
./Hypraesthetic-theme restore

# Check dependencies
./Hypraesthetic-theme doctor
./scripts/install-deps.sh check
```

Test on multiple distros if possible (Arch, Fedora, Ubuntu, NixOS).

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b add-theme-tokyonight`
3. Make your changes
4. Test thoroughly (see Testing section)
5. Update documentation if needed
6. Commit with clear messages:
   ```
   feat: add tokyonight theme

   - Add base16 color palette
   - Configure all 9 components
   - Tested on Arch and Fedora
   ```
7. Push and open PR

## Commit Message Format

```
<type>(<scope>): <description>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(themes): add gruvbox theme
fix(waybar): use @define-color for GTK4 compatibility
docs: update ADDING_THEMES.md with template examples
```

## Theme Guidelines

- **Base16 palette** - Use all 16 base colors for consistency
- **Derived colors** - Define Hyprland/Waybar colors via references
- **Minimal overrides** - Only provide color files, not full configs
- **Complete components** - All 9 components should work
- **No hardcoded paths** - Use variables from theme.toml
- **Screenshot** - Include 1920x1080 screenshot if possible

## Component Guidelines

- **Template-first** - Prefer template rendering over symlinks
- **Graceful reload** - Handle daemon restart properly
- **Dry-run support** - Respect `--dry-run` flag
- **Error handling** - Use `die` for fatal errors, `log_warn` for recoverable
- **Idempotent** - Running twice should be safe

## Reporting Issues

Use GitHub Issues with:
- **Bug reports**: Steps to reproduce, expected vs actual, logs
- **Feature requests**: Use case, proposed solution
- **Theme issues**: Theme name, component, error output

## Code of Conduct

Be respectful, inclusive, and constructive. This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

## Questions?

Open a GitHub Discussion or ask in the Hyprland Discord (#ricing channel).