#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CiWorkflowTests(unittest.TestCase):
    def test_run_checks_does_not_fail_info_sc1091(self) -> None:
        text = (ROOT / "scripts/ci/run-checks.sh").read_text(encoding="utf-8")
        self.assertIn("shellcheck -x -e SC1091", text)

    def test_install_uninstall_declare_common_source(self) -> None:
        for name in ("install.sh", "uninstall.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("# shellcheck source=scripts/lib/common.sh", text)
            self.assertIn("scripts/lib/common.sh", text)

    def test_workflow_runs_checks_and_fails_docs(self) -> None:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("bash scripts/ci/run-checks.sh", text)
        self.assertIn("set -euo pipefail", text)
        self.assertIn("exit 1", text)

    def test_workflow_installs_gtk_typelibs_for_gui_tests(self) -> None:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for pkg in ("python3-gi", "gir1.2-gtk-4.0", "gir1.2-adw-1", "xvfb"):
            self.assertIn(pkg, text)

    def test_run_checks_uses_xvfb_for_gtk_tests(self) -> None:
        text = (ROOT / "scripts/ci/run-checks.sh").read_text(encoding="utf-8")
        self.assertIn("xvfb-run", text)

    def test_gui_test_modules_import_when_gtk_namespace_missing(self) -> None:
        script = f"""
import sys
import types
from pathlib import Path

root = Path({str(ROOT)!r})
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "tests"))

class FakeGi(types.ModuleType):
    def require_version(self, ns, ver):
        raise ValueError(f"Namespace {{ns}} not available")

sys.modules["gi"] = FakeGi("gi")
sys.modules["gi.repository"] = types.ModuleType("gi.repository")

import test_dirty
import test_gui_pages
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
