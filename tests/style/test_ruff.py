"""Machine lock for the Python kernel style. No new GitHub check name."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RuffTests(unittest.TestCase):
    def test_kernel_is_clean(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "forge",
                "overlay",
                "schema",
                "tests",
                "scripts",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            proc.returncode,
            0,
            (proc.stdout or "") + (proc.stderr or ""),
        )


if __name__ == "__main__":
    unittest.main()
