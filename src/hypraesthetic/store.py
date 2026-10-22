"""Local/remote theme store index."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from hypraesthetic.install_theme import ThemeInstaller, _git_name, _looks_like_git
from hypraesthetic.paths import data_dir, repo_root
from hypraesthetic.theme import ThemePackage


@dataclass
class StoreEntry:
    name: str
    display_name: str
    description: str
    author: str
    source: str
    preview: str = ""

    @property
    def is_remote(self) -> bool:
        src = self.source
        return src not in {"", "builtin"} and (
            src.startswith("http://") or src.startswith("https://") or src.endswith(".git")
        )


class ThemeStore:
    def __init__(self, index_path: Path | None = None):
        self.index_path = index_path or _default_index()
        self.entries = _load_index(self.index_path)

    def list(self) -> list[StoreEntry]:
        return list(self.entries)

    def get(self, name: str) -> StoreEntry:
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise KeyError(name)

    def refresh(self, url: str, dest: Path | None = None) -> Path:
        target = dest or self.index_path
        with urlopen(url, timeout=20) as response:  # noqa: S310 - user-configured catalog URL
            payload = response.read()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        self.entries = _load_index(target)
        return target

    def install(self, name: str, installer: ThemeInstaller | None = None) -> ThemePackage:
        entry = self.get(name)
        worker = installer or ThemeInstaller()
        if not entry.is_remote:
            raise ValueError(f"{name} is a builtin theme; use hat switch {name}")
        return worker.install(entry.source)

    def search(self, query: str) -> list[StoreEntry]:
        q = (query or "").strip()
        if not q:
            return self.list()
        if _looks_like_git(q) or q.startswith("http://") or q.startswith("https://"):
            slug = _git_name(q)
            return [
                StoreEntry(
                    name=slug,
                    display_name=slug.replace("-", " ").title(),
                    description=q,
                    author="",
                    source=q,
                )
            ]
        needle = q.lower().rsplit("/", 1)[-1]
        hits = []
        for entry in self.entries:
            blob = f"{entry.name} {entry.display_name} {entry.author} {entry.source}".lower()
            if needle in blob or q.lower() in blob:
                hits.append(entry)
        return hits

    def resolve(self, query: str) -> StoreEntry:
        hits = self.search(query)
        if not hits:
            raise KeyError(query)
        return hits[0]


def _default_index() -> Path:
    bundled = data_dir() / "store-index.toml"
    if bundled.is_file():
        return bundled
    return repo_root() / "data" / "store-index.toml"


def _load_index(path: Path) -> list[StoreEntry]:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    entries = []
    for item in raw.get("themes") or []:
        entries.append(
            StoreEntry(
                name=str(item.get("name") or ""),
                display_name=str(item.get("display_name") or item.get("name") or ""),
                description=str(item.get("description") or ""),
                author=str(item.get("author") or ""),
                source=str(item.get("source") or "builtin"),
                preview=str(item.get("preview") or ""),
            )
        )
    return entries
