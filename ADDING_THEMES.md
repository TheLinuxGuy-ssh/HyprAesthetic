# Adding themes

HyprAesthetic themes are packages. You do **not** copy a 200-file rice for a new palette.

1. Create `themes/mytheme/theme.toml` using schema 2 (see [docs/theme-package.md](docs/theme-package.md)).
2. Add a preview image (`preview.png`, `preview.gif`, jpeg, or webp) and a wallpaper (same extensions, or a file in `~/.wallpapers` named in `[misc]`).
3. Only add `overrides/` if you need a different Waybar/eww layout than `layouts/default/`.
4. Validate and switch:

```bash
hat validate mytheme
hat switch mytheme --dry-run
hat switch mytheme
```

To ship it for other people:

```bash
hat install-theme ./themes/mytheme
# or publish the folder as a git repo and add it to data/store-index.toml
```

See [docs/store.md](docs/store.md).
