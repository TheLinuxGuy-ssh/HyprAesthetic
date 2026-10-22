"""Distro package catalog."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hypraesthetic.paths import data_dir, repo_root


@dataclass
class DistroFamily:
    name: str
    ids: list[str]
    manager: str


@dataclass
class ComponentSpec:
    id: str
    friendly: str
    required: bool = False
    commands: list[str] = field(default_factory=list)
    packages: dict[str, list[str]] = field(default_factory=dict)
    choice_group: str | None = None
    choice_value: str | None = None

    def packages_for(self, family_name: str) -> list[str]:
        return list(self.packages.get(family_name) or [])


class PackageCatalog:
    def __init__(self, families: dict[str, DistroFamily], components: dict[str, ComponentSpec]):
        self.families = families
        self.components = components
        self._id_to_family = {
            distro_id: family
            for family in families.values()
            for distro_id in family.ids
        }

    @classmethod
    def load(cls, path: Path | None = None) -> PackageCatalog:
        catalog_path = path or data_dir() / "packages.toml"
        if not catalog_path.is_file():
            catalog_path = repo_root() / "data" / "packages.toml"
        with catalog_path.open("rb") as handle:
            raw = tomllib.load(handle)
        families = {
            name: DistroFamily(
                name=name,
                ids=list(body.get("ids") or []),
                manager=str(body.get("manager") or ""),
            )
            for name, body in (raw.get("families") or {}).items()
        }
        components: dict[str, ComponentSpec] = {}
        for name, body in (raw.get("components") or {}).items():
            components[name] = ComponentSpec(
                id=str(body.get("id") or name),
                friendly=str(body.get("friendly") or name),
                required=bool(body.get("required")),
                commands=list(body.get("commands") or []),
                packages={
                    family: list(pkgs)
                    for family, pkgs in (body.get("packages") or {}).items()
                },
                choice_group=body.get("choice_group"),
                choice_value=body.get("choice_value"),
            )
        return cls(families, components)

    def family_for(self, distro_id: str) -> DistroFamily:
        if distro_id in self._id_to_family:
            return self._id_to_family[distro_id]
        for family in self.families.values():
            if distro_id.startswith(family.name):
                return family
        raise KeyError(distro_id)

    def component(self, component_id: str) -> ComponentSpec:
        return self.components[component_id]

    def required(self) -> list[ComponentSpec]:
        return [item for item in self.components.values() if item.required]

    def selected_components(self, selection: dict[str, Any]) -> list[ComponentSpec]:
        extras = set(selection.get("extras") or [])
        widgets = selection.get("widgets")
        if widgets:
            extras.add("eww")
        wanted: list[ComponentSpec] = []
        for item in self.components.values():
            if item.required:
                wanted.append(item)
                continue
            if item.choice_group:
                selected = selection.get(item.choice_group)
                if item.choice_group == "widgets":
                    if selected:
                        wanted.append(item)
                elif selected == item.choice_value:
                    wanted.append(item)
                continue
            if item.id in extras:
                wanted.append(item)
        return wanted

    def packages_for_selection(self, distro_id: str, selection: dict[str, Any]) -> list[str]:
        family = self.family_for(distro_id)
        packages: list[str] = []
        seen: set[str] = set()
        for item in self.selected_components(selection):
            for pkg in item.packages_for(family.name):
                if pkg not in seen:
                    seen.add(pkg)
                    packages.append(pkg)
        return packages
