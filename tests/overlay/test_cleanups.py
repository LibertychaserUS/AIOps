"""Hardening batch 3: generate --force keeps wiring, run scrubs the tool from PYTHONPATH, --timeout > 0."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path

import yaml
from overlay.generate import run_generate
from overlay.run import child_environ, tool_root

from overlay import EXIT_OK
from tests.overlay.support import REPO, run_overlay, write, write_generic_root
from tests.overlay.test_generate import CASES, EXTRACT, FakeTransport


def _set_command(root: Path, command: str) -> None:
    path = root / "suites" / "checkout-retry" / "suite.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["product_command"] = command
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


class GenerateForceTests(unittest.TestCase):
    def test_force_keeps_product_command_and_warns_about_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _set_command(root, "npm test -- --grep 'checkout'")
            write(
                root / "suites" / "checkout-retry" / "trace.yaml",
                "schema: overlay-trace/v1\nsuite: checkout-retry\nitems: []\n",
            )
            out, err = io.StringIO(), io.StringIO()
            code = run_generate(
                root,
                "inbox/checkout-retry.md",
                force=True,
                stdout=out,
                stderr=err,
                environ={"OPENAI_API_KEY": "test-key"},
                urlopen=FakeTransport([EXTRACT, CASES]),
            )
            self.assertEqual(code, EXIT_OK, err.getvalue())
            data = yaml.safe_load(
                (root / "suites" / "checkout-retry" / "suite.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(data["product_command"], "npm test -- --grep 'checkout'")
            self.assertEqual(data["status"], "active")
            self.assertIn("product_command=kept", out.getvalue())
            self.assertIn("trace.yaml", err.getvalue())
            self.assertTrue((root / "suites" / "checkout-retry" / "trace.yaml").is_file())


class ChildEnvironTests(unittest.TestCase):
    def test_tool_root_is_removed_from_pythonpath(self) -> None:
        root = str(tool_root())
        env = child_environ(
            {"PYTHONPATH": os.pathsep.join([root, "/opt/product/lib"]), "KEEP": "1"}
        )
        self.assertEqual(env["PYTHONPATH"], "/opt/product/lib")
        self.assertEqual(env["KEEP"], "1")
        self.assertNotIn("PYTHONPATH", child_environ({"PYTHONPATH": root}))
        self.assertNotIn("PYTHONPATH", child_environ({}))

    def test_product_command_does_not_see_the_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _set_command(root, "echo PP=${PYTHONPATH-unset}")
            result = run_overlay(
                "run",
                "--branch",
                "main",
                "--root",
                str(root),
                "--write-receipt",
                str(Path(tmp) / "receipts"),
                "--workdir",
                str(root),
            )
            self.assertEqual(result.returncode, EXIT_OK, result.stderr)
            self.assertIn("PP=unset", result.stdout)
            self.assertNotIn(str(REPO), result.stdout)


class TimeoutFlagTests(unittest.TestCase):
    def test_zero_and_negative_timeout_are_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            for value in ("0", "-5", "abc"):
                with self.subTest(value=value):
                    result = run_overlay(
                        "run", "--root", str(root), "--write-receipt", tmp, "--timeout", value
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("--timeout", result.stderr)


if __name__ == "__main__":
    unittest.main()
