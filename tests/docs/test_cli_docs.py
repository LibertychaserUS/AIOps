"""docs/cli.md must match scripts/gen_cli_docs.py output."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "gen_cli_docs.py"
CLI_MD = ROOT / "docs" / "cli.md"


class CliDocsTests(unittest.TestCase):
    def test_cli_md_matches_current_help(self) -> None:
        self.assertTrue(SCRIPT.is_file(), SCRIPT)
        self.assertTrue(CLI_MD.is_file(), CLI_MD)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
