# Contributing to HyprAesthetic

## Ways to contribute

- Add a theme package (`themes/<name>/theme.toml`) — see [ADDING_THEMES.md](ADDING_THEMES.md)
- Improve shared layouts in `layouts/default/`
- Extend the Python core in `src/hypraesthetic/`
- Add control-center pages in `src/hypraesthetic_gui/`
- Distro package names in `data/packages.toml`

## Issues and pull requests

- Open issues with the templates under `.github/ISSUE_TEMPLATE/`
- PRs use `.github/PULL_REQUEST_TEMPLATE.md`
- Do not open public issues for security — see [SECURITY.md](SECURITY.md)
- This project follows the [Code of Conduct](CODE_OF_CONDUCT.md)

Theme previews may be `preview.png` or `preview.gif` (and jpeg/webp); wallpapers the same.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash scripts/ci/run-checks.sh
```

Write a failing test before changing apply/theme/catalog/installer behavior.

## Code style

- Python 3.11+, 4-space indent, type hints on public functions
- Shell scripts: `set -euo pipefail`, `log_*` from `scripts/lib/common.sh`
- Do not overwrite `~/.config/hypr/custom.lua` after the first apply
