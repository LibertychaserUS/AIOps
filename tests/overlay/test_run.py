from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from overlay import EXIT_CONTRACT, EXIT_OK, EXIT_RUN
from tests.overlay.support import LG, REPO, run_overlay, write_generic_root

PY = sys.executable

HTTP_MODULES = {
    "http",
    "http.client",
    "urllib.request",
    "requests",
    "httpx",
    "aiohttp",
    "openai",
}


def _set_command(root: Path, command: str | None) -> None:
    path = root / "suites" / "checkout-retry" / "suite.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["product_command"] = command
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


class RunTests(unittest.TestCase):
    def test_help_lists_run(self) -> None:
        result = run_overlay("run", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--write-receipt", result.stdout)
        self.assertIn("--workdir", result.stdout)

    def test_run_without_receipt_is_usage_error(self) -> None:
        result = run_overlay("run", "--branch", "main", "--root", str(LG))
        self.assertNotEqual(result.returncode, 0)

    def test_skip_when_command_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            dest = Path(tmp) / "receipts"
            result = run_overlay(
                "run",
                "--branch",
                "main",
                "--root",
                str(root),
                "--write-receipt",
                str(dest),
                "--workdir",
                str(root),
            )
            self.assertEqual(result.returncode, EXIT_OK, result.stderr)
            self.assertIn("skipped_no_command", result.stdout + result.stderr)
            data = _one_receipt(dest)
            self.assertEqual(data["wrote_by"], "run")
            types = [event["type"] for event in data["events"]]
            self.assertIn("skipped_no_command", types)
            self.assertNotIn("ran", types)

    def test_success_command_writes_ran(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            marker = Path(tmp) / "ran.txt"
            _set_command(root, f"{PY} -c \"from pathlib import Path; Path({str(marker)!r}).write_text('ok')\"")
            dest = Path(tmp) / "receipts"
            result = run_overlay(
                "run",
                "--branch",
                "main",
                "--root",
                str(root),
                "--write-receipt",
                str(dest),
                "--workdir",
                str(root),
            )
            self.assertEqual(result.returncode, EXIT_OK, result.stderr + result.stdout)
            self.assertTrue(marker.is_file(), result.stderr)
            data = _one_receipt(dest)
            self.assertEqual(data["wrote_by"], "run")
            ran = [event for event in data["events"] if event["type"] == "ran"]
            self.assertEqual(len(ran), 1)
            self.assertEqual(ran[0]["suite"], "checkout-retry")
            self.assertEqual(ran[0]["exit_code"], 0)
            self.assertEqual(ran[0]["function_id"], "FN-login-retry")

    def test_failed_command_is_exit_5_and_still_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _set_command(root, f"{PY} -c \"raise SystemExit(1)\"")
            dest = Path(tmp) / "receipts"
            result = run_overlay(
                "run",
                "--branch",
                "main",
                "--root",
                str(root),
                "--write-receipt",
                str(dest),
                "--workdir",
                str(root),
            )
            self.assertEqual(result.returncode, EXIT_RUN, result.stderr + result.stdout)
            data = _one_receipt(dest)
            ran = [event for event in data["events"] if event["type"] == "ran"]
            self.assertEqual(ran[0]["exit_code"], 1)

    def test_forbid_hosts_in_command_is_exit_2_and_does_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            marker = Path(tmp) / "should-not-exist"
            _set_command(
                root,
                f"{PY} -c \"from pathlib import Path; Path({str(marker)!r}).write_text('no')\" "
                f"# https://prod.example.com/pay",
            )
            dest = Path(tmp) / "receipts"
            result = run_overlay(
                "run",
                "--branch",
                "main",
                "--root",
                str(root),
                "--write-receipt",
                str(dest),
                "--workdir",
                str(root),
            )
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr + result.stdout)
            self.assertFalse(marker.exists())
            data = _one_receipt(dest)
            refused = [event for event in data["events"] if event["type"] == "refused"]
            self.assertEqual(refused[0]["rule"], "forbid_hosts")

    def test_learning_guide_run_skips_armed_without_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "receipts"
            result = run_overlay(
                "run",
                "--branch",
                "main",
                "--root",
                str(LG),
                "--write-receipt",
                str(dest),
                "--workdir",
                str(REPO),
            )
            self.assertEqual(result.returncode, EXIT_OK, result.stderr + result.stdout)
            self.assertIn("my-learning skipped_no_command", result.stdout)
            self.assertNotIn("payment ", result.stdout)
            self.assertNotIn("login ", result.stdout)
            data = _one_receipt(dest)
            dropped = {
                event["suite"]: event["rule"]
                for event in data["events"]
                if event["type"] == "dropped"
            }
            self.assertEqual(dropped.get("payment"), "never_red_statuses")
            self.assertEqual(dropped.get("login"), "never_red_statuses")

    def test_unknown_branch_is_empty_and_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "receipts"
            result = run_overlay(
                "run",
                "--branch",
                "does-not-exist",
                "--root",
                str(LG),
                "--write-receipt",
                str(dest),
            )
            self.assertEqual(result.returncode, EXIT_OK, result.stderr)
            self.assertIn("selected=0", result.stderr)

    def test_workshop_commands_are_not_recursive(self) -> None:
        for name in ("overlay-select", "forge-apply"):
            text = (REPO / "suites" / name / "suite.yaml").read_text(encoding="utf-8")
            self.assertIn("product_command:", text)
            self.assertNotIn("python -m overlay run", text)

    def test_run_module_has_no_http_client(self) -> None:
        path = REPO / "overlay" / "run.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertTrue(imported.isdisjoint(HTTP_MODULES), imported)
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("urlopen", text)
        self.assertNotIn("openai", text.lower())


def _one_receipt(directory: Path) -> dict:
    files = list(directory.glob("*.yaml"))
    if len(files) != 1:
        raise AssertionError(files)
    data = yaml.safe_load(files[0].read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(data)
    return data


if __name__ == "__main__":
    unittest.main()
