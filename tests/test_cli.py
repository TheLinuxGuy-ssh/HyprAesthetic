#!/usr/bin/env python3

from __future__ import annotations

import os
import unittest
from pathlib import Path

from hypraesthetic.cli import main
from hypraesthetic.paths import REPO_ROOT


class CliTests(unittest.TestCase):
    def _run(self, args: list[str]) -> tuple[int, str]:
        os.environ["HYPRAESTHETIC_ROOT"] = str(REPO_ROOT)
        from io import StringIO
        import sys

        buf = StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            code = main(args)
        finally:
            sys.stdout = old
        return code, buf.getvalue()

    def test_help_exits_zero(self) -> None:
        code, out = self._run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("ha-theme", out)

    def test_list_includes_toji(self) -> None:
        code, out = self._run(["list"])
        self.assertEqual(code, 0)
        self.assertIn("toji", out)

    def test_validate_official_themes(self) -> None:
        code, out = self._run(["validate"])
        self.assertEqual(code, 0)
        self.assertIn("toji", out)


if __name__ == "__main__":
    unittest.main()
