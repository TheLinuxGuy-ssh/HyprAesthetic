#!/usr/bin/env python3

from __future__ import annotations

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
