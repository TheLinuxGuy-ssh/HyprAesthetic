# Security Policy

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in HyprAesthetic, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Open a private [GitHub Security Advisory](https://github.com/thelinuxguy-ssh/HyprAesthetic/security/advisories/new)
3. Or email the maintainers at: mr.linux.0@protonmail.com
4. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a timeline for fix.

## Security Considerations

### What This Project Does
- Reads theme configuration files (TOML)
- Renders templates with color values via the Python renderer (`hat`)
- Creates symlinks in `~/.config/`
- Backs up existing configs to `~/.config.backup/`
- Installs system packages via package manager (with user confirmation)

### What This Project Does NOT Do
- Execute arbitrary code from theme files
- Download or execute remote scripts
- Modify system files outside `~/.config/`
- Run as root unless the user confirms the warning; package installs use sudo from a normal user

### Threat Model

**Trust Boundaries:**
- Theme files are trusted (user-created or from this repo)
- Template files are trusted (part of this repo)
- User's existing configs are backed up before modification

**Potential Risks:**
1. **Symlink attacks** - Malicious theme could symlink outside `~/.config/`
   - Mitigation: `hat` validates paths, only creates symlinks to theme dir
2. **Template injection** - Malicious TOML could inject shell commands
   - Mitigation: Python renderer only does string substitution, no eval
3. **Package installation** - Supply chain via package manager
   - Mitigation: Uses official distro repos, user confirms before install
4. **Backup exposure** - Backups contain user's config files
   - Mitigation: Stored in user-only accessible `~/.config.backup/`

### Safe Practices for Users

- Only install themes from trusted sources
- Review `theme.toml` and config files before switching
- Run `hat switch <theme> --dry-run` first
- Keep backups (automatic) and know how to restore

### For Theme Authors

- Do not include executable scripts in theme folders
- Do not use absolute paths outside theme directory
- Keep themes self-contained
- Test on clean system before publishing

## Dependency Security

We regularly update:
- Base templates to match upstream config changes
- Package lists in `install-deps.sh` for latest versions
- Python version requirement (3.11+ for `tomllib`)

## Contact

Security contact: mr.linux.0@protonmail.com
