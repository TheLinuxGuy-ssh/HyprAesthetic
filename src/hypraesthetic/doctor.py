"""Non-fatal dependency report."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from typing import Callable

from hypraesthetic.packages import PackageCatalog
from hypraesthetic.prefs import Prefs


@dataclass
class DoctorCheck:
    id: str
    ok: bool
    required: bool
    detail: str = ""
    friendly: str = ""


@dataclass
class DoctorReport:
    checks: list[DoctorCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok or not check.required for check in self.checks)

    @property
    def missing_required(self) -> list[DoctorCheck]:
        return [check for check in self.checks if check.required and not check.ok]


WhichFn = Callable[[str], str | None]


class Doctor:
    def __init__(
        self,
        catalog_commands: dict[str, list[str]] | None = None,
        required: set[str] | None = None,
        which: WhichFn | None = None,
        catalog: PackageCatalog | None = None,
        selection: dict | None = None,
    ):
        self.catalog_commands = catalog_commands
        self.required_ids = required
        self.which = which or shutil.which
        self.catalog = catalog
        self.selection = selection

    def run(self) -> DoctorReport:
        report = DoctorReport()
        if self.catalog_commands is not None:
            required = self.required_ids or set()
            for cid, commands in self.catalog_commands.items():
                report.checks.append(self._probe(cid, cid, commands, cid in required))
            return report

        catalog = self.catalog or PackageCatalog.load()
        selection = self.selection
        if selection is None:
            selection = Prefs.load().selection()
        for item in catalog.selected_components(selection):
            report.checks.append(
                self._probe(item.id, item.friendly, item.commands, item.required)
            )
        return report

    def _probe(self, cid: str, friendly: str, commands: list[str], required: bool) -> DoctorCheck:
        if not commands:
            return DoctorCheck(
                id=cid,
                ok=True,
                required=required,
                detail="no command probe",
                friendly=friendly,
            )
        missing = [cmd for cmd in commands if not self.which(cmd)]
        if missing:
            return DoctorCheck(
                id=cid,
                ok=False,
                required=required,
                detail="missing: " + ", ".join(missing),
                friendly=friendly,
            )
        return DoctorCheck(
            id=cid,
            ok=True,
            required=required,
            detail="found",
            friendly=friendly,
        )
