# Theme store

The store is an index of theme packages. Official themes are `source = "builtin"` and are applied in place. Community themes use a git URL; `hat store install` clones them. You can also install a package without the index using `hat install-theme`.

The bundled index is [data/store-index.toml](../data/store-index.toml).

```bash
hat store list
hat store search <query>
hat store install <name-or-url>
hat store refresh [url]
```

Examples:

```bash
hat store search community
hat store search https://github.com/someone/community-dark.git
hat store install community-dark
hat store refresh https://example.com/hypraesthetic-index.toml
```

`store list` prints name, display name, and `builtin` or `remote`. `store search` matches name, display name, author, or source; a git URL is treated as a remote entry even if it is not in the index. `store install` takes a catalog name or a git URL: builtins apply in place, remotes clone (same path as `hat install-theme`). `store refresh` writes `~/.config/HyprAesthetic/store-index.toml`. Set `prefs.store_url` to refresh without an argument.

## Listing a theme

1. Put the theme in the [theme package format](theme-package.md).
2. Host it as a git repository with `theme.toml` at the root (or one directory down).
3. Add an entry:

```toml
[[themes]]
name = "community-dark"
display_name = "Community Dark"
description = "A ported rice"
author = "someone"
source = "https://github.com/someone/community-dark.git"
preview = "https://example.com/preview.png"
```

`preview` may be a local file (`preview.png`, `preview.gif`, jpeg, or webp) or a URL to the same kinds of image.

The GTK Store page uses the same index. Search a name, a `site/theme` slug, or a git URL. Builtin themes apply in place; remote themes clone and apply.
