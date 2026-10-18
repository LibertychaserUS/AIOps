"""Hostile inputs for run / cover / generate / migrate / validate: no tracebacks, no false greens."""

from __future__ import annotations

import http.client
import io
import json
import subprocess
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path

import yaml
from overlay.generate import OPENROUTER_BASE, chat_url, run_generate

from overlay import EXIT_CONTRACT, EXIT_OK
from tests.overlay.support import run_overlay, write, write_generic_root
from tests.overlay.test_generate import CASES, EXTRACT, FakeTransport


def _set_command(root: Path, command: str) -> None:
    path = root / "suites" / "checkout-retry" / "suite.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["product_command"] = command
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _run(root: Path, dest: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_overlay(
        "run",
        "--branch",
        "main",
        "--root",
        str(root),
        "--write-receipt",
        str(dest),
        "--workdir",
        str(root),
        *extra,
    )


def _generate(root: Path, transport, environ=None, force=False) -> tuple[int, str]:
    err = io.StringIO()
    code = run_generate(
        root,
        "inbox/checkout-retry.md",
        force=force,
        stdout=io.StringIO(),
        stderr=err,
        environ=environ or {"OPENAI_API_KEY": "test-key"},
        urlopen=transport,
    )
    return code, err.getvalue()


class RunHardeningTests(unittest.TestCase):
    def test_non_utf8_output_still_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _set_command(root, r"printf '\377\376 bad\n'")
            dest = Path(tmp) / "receipts"
            result = _run(root, dest)
            self.assertEqual(result.returncode, EXIT_OK, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(len(list(dest.glob("*.yaml"))), 1)

    def test_timeout_kills_tree_and_keeps_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            marker = Path(tmp) / "late"
            _set_command(root, f"echo partial-progress; sleep 3; touch {marker}")
            dest = Path(tmp) / "receipts"
            result = _run(root, dest, "--timeout", "1")
            self.assertIn("partial-progress", result.stdout)
            time.sleep(3)
            self.assertFalse(marker.exists(), "child outlived the timeout")

    def test_command_gets_no_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _set_command(root, "read -r line; echo got=$?")
            dest = Path(tmp) / "receipts"
            result = _run(root, dest, "--timeout", "5")
            self.assertIn("got=1", result.stdout)


class CoverHardeningTests(unittest.TestCase):
    def test_non_list_relates_is_contract_error_not_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            inbox = root / "inbox" / "checkout-retry.md"
            inbox.write_text(
                inbox.read_text(encoding="utf-8").replace(
                    "- FN-login-retry Retry on the failure page.\n",
                    "- FN-login-retry Retry on the failure page.\n- FN-two Second leaf.\n",
                ),
                encoding="utf-8",
            )
            cases = root / "suites" / "checkout-retry" / "cases.md"
            text = cases.read_text(encoding="utf-8")
            second = text[text.index("## FN-login-retry") :].replace("FN-login-retry", "FN-two")
            cases.write_text(text + "\n" + second, encoding="utf-8")
            write(
                root / "suites" / "checkout-retry" / "trace.yaml",
                """\
schema: overlay-trace/v1
suite: checkout-retry
items:
  - function_id: FN-login-retry
    case_id: FN-login-retry/functional
    type: functional
    relates: 5
""",
            )
            result = run_overlay("cover", "--root", str(root))
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)


class GenerateHardeningTests(unittest.TestCase):
    def test_openrouter_key_goes_to_openrouter(self) -> None:
        self.assertTrue(chat_url({"OPENROUTER_API_KEY": "sk-or"}).startswith(OPENROUTER_BASE))
        self.assertIn("api.openai.com", chat_url({"OPENAI_API_KEY": "sk", "OPENROUTER_API_KEY": "x"}))
        self.assertIn(
            "example.test",
            chat_url({"OPENROUTER_API_KEY": "sk-or", "OPENAI_BASE_URL": "https://example.test/v1"}),
        )

    def _fresh_root(self, tmp: str) -> Path:
        root = write_generic_root(Path(tmp))
        for path in (root / "suites" / "checkout-retry").iterdir():
            path.unlink()
        (root / "suites" / "checkout-retry").rmdir()
        return root

    def test_bad_base_url_is_one_line_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fresh_root(tmp)
            env = {"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": "api.example.com/v1"}
            code, err = _generate(root, FakeTransport([EXTRACT, CASES]), environ=env)
            self.assertEqual(code, EXIT_CONTRACT)
            self.assertIn("http(s)://", err)

    def test_http_errors_are_named_not_traceback(self) -> None:
        def http_401(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

        def incomplete(request, timeout=None):
            raise http.client.IncompleteRead(b"partial")

        for opener, needle in ((http_401, "HTTP 401"), (incomplete, "IncompleteRead")):
            with self.subTest(needle=needle), tempfile.TemporaryDirectory() as tmp:
                root = self._fresh_root(tmp)
                code, err = _generate(root, opener)
                self.assertEqual(code, EXIT_CONTRACT)
                self.assertIn(needle, err)
                self.assertFalse((root / "suites" / "checkout-retry").exists())

    def test_heading_in_leaf_text_writes_nothing(self) -> None:
        bad = json.loads(CASES)
        bad["functions"][0]["edge"] = "- ok\n## INJECTED-99 new leaf\n### Functional\n- x"
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fresh_root(tmp)
            code, err = _generate(root, FakeTransport([EXTRACT, json.dumps(bad)]))
            self.assertEqual(code, EXIT_CONTRACT, err)
            self.assertFalse((root / "suites" / "checkout-retry").exists())

    def test_force_refuses_unparseable_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            suite = root / "suites" / "checkout-retry" / "suite.yaml"
            broken = suite.read_text(encoding="utf-8").replace(
                "status: active", "status: blocked"
            ).replace("product_command: null", 'product_command: "unterminated')
            suite.write_text(broken, encoding="utf-8")
            code, err = _generate(root, FakeTransport([EXTRACT, CASES]), force=True)
            self.assertEqual(code, EXIT_CONTRACT, err)
            self.assertEqual(suite.read_text(encoding="utf-8"), broken)

    def test_orphan_cases_md_needs_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            (root / "suites" / "checkout-retry" / "suite.yaml").unlink()
            cases = root / "suites" / "checkout-retry" / "cases.md"
            cases.write_text("HUMAN WORK\n", encoding="utf-8")
            code, err = _generate(root, FakeTransport([EXTRACT, CASES]))
            self.assertEqual(code, EXIT_CONTRACT, err)
            self.assertEqual(cases.read_text(encoding="utf-8"), "HUMAN WORK\n")


class MigrateHardeningTests(unittest.TestCase):
    def test_blocked_reason_without_ref_is_left_as_todo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = (
                path.read_text(encoding="utf-8")
                .replace("schema: overlay-suite/v2\n", "")
                .replace("status: active", "status: blocked")
                .replace("blocked_reason: null", "blocked_reason: waiting on vendor")
                + "reviewed_by: fixture\n"
            )
            path.write_text(text, encoding="utf-8")
            result = run_overlay("migrate", "--root", str(root))
            self.assertEqual(path.read_text(encoding="utf-8"), text)
            self.assertIn("待办", result.stderr)

    def test_quoted_draft_item_removed_from_never_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            overlay = root / "overlay.yaml"
            overlay.write_text(
                overlay.read_text(encoding="utf-8").replace(
                    "never_red_statuses:\n  - blocked\n",
                    'never_red_statuses:\n  - "draft"\n  - blocked\n',
                ),
                encoding="utf-8",
            )
            result = run_overlay("migrate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_OK, result.stderr)
            self.assertNotIn("draft", overlay.read_text(encoding="utf-8"))


class ValidateHardeningTests(unittest.TestCase):
    def test_duplicate_function_id_in_one_cases_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            cases = root / "suites" / "checkout-retry" / "cases.md"
            cases.write_text(
                cases.read_text(encoding="utf-8") + "\n## FN-login-retry again\n\nbare\n",
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertIn("duplicate", result.stderr)


if __name__ == "__main__":
    unittest.main()
