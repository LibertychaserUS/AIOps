"""Hardening batch 1: config schema, triad parsing, guarded writes, forbid_hosts, CI wiring."""

from __future__ import annotations

import io
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from overlay.review import run_review
from overlay.validate import forbid_host_hits, forbid_host_url_hits

from overlay import EXIT_CONTRACT, EXIT_OK
from tests.overlay.support import REPO, run_overlay, write, write_generic_root
from tests.overlay.test_review import _init


def _set_command(root: Path, suite_id: str, command: str) -> None:
    path = root / "suites" / suite_id / "suite.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["product_command"] = command
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _run(root: Path, dest: Path) -> subprocess.CompletedProcess[str]:
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
    )


def _add_second_suite(root: Path) -> None:
    """Clone checkout-retry into second-slice so two suites are selected on main."""
    for rel in (
        "inbox/checkout-retry.md",
        "suites/checkout-retry/suite.yaml",
        "suites/checkout-retry/cases.md",
    ):
        text = (root / rel).read_text(encoding="utf-8")
        text = text.replace("checkout-retry", "second-slice").replace("FN-login-retry", "FN-second")
        write(root / rel.replace("checkout-retry", "second-slice"), text)


class ConfigSchemaTests(unittest.TestCase):
    def test_unknown_key_is_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            overlay = root / "overlay.yaml"
            overlay.write_text(
                overlay.read_text(encoding="utf-8") + "require_comand: true\n", encoding="utf-8"
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertIn("unknown field 'require_comand'", result.stderr)

    def test_unknown_branch_key_is_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            overlay = root / "overlay.yaml"
            overlay.write_text(
                overlay.read_text(encoding="utf-8").replace(
                    "  main:\n    run: [functional, regression]\n",
                    "  main:\n    run: [functional, regression]\n    runs: [edge]\n",
                ),
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertIn("unknown field 'runs'", result.stderr)


class TriadTests(unittest.TestCase):
    def test_headings_inside_fence_are_not_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            cases = root / "suites" / "checkout-retry" / "cases.md"
            cases.write_text(
                cases.read_text(encoding="utf-8")
                + "\nTemplate:\n\n```markdown\n## FN-not-real Example\n### Functional\n- x\n```\n",
                encoding="utf-8",
            )
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_OK, result.stderr)

    def test_fenced_technique_heading_does_not_satisfy_triad(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            cases = root / "suites" / "checkout-retry" / "cases.md"
            text = cases.read_text(encoding="utf-8")
            start = text.index("### Edge")
            cases.write_text(text[:start] + "```\n" + text[start:] + "```\n", encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertIn("edge", result.stderr.lower())

    def test_empty_technique_section_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            cases = root / "suites" / "checkout-retry" / "cases.md"
            text = cases.read_text(encoding="utf-8")
            start = text.index("### Edge")
            cases.write_text(text[:start] + "### Edge\n", encoding="utf-8")
            result = run_overlay("validate", "--root", str(root))
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)


class GuardedWriteTests(unittest.TestCase):
    def test_review_refuses_unparseable_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            broken = path.read_text(encoding="utf-8").replace(
                "product_command: null", 'product_command: "unterminated'
            )
            path.write_text(broken, encoding="utf-8")
            _init(root, "dev")
            err = io.StringIO()
            code = run_review(
                root=root,
                i_am="ada",
                suite="checkout-retry",
                status="blocked",
                reason="#12",
                stderr=err,
            )
            self.assertEqual(code, EXIT_CONTRACT)
            self.assertEqual(path.read_text(encoding="utf-8"), broken)
            self.assertIn("refusing", err.getvalue())

    def test_migrate_refuses_rewrite_that_touches_block_scalar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            text = (
                path.read_text(encoding="utf-8")
                .replace("schema: overlay-suite/v2\n", "")
                .replace("status: active", "status: armed")
                .replace(
                    "product_command: null", "product_command: |\n  echo begin\n  status: armed\n"
                )
            )
            path.write_text(text, encoding="utf-8")
            result = run_overlay("migrate", "--root", str(root))
            self.assertEqual(path.read_text(encoding="utf-8"), text)
            self.assertIn("product_command", result.stderr)
            self.assertIn("skipped=1", result.stdout)

    def test_review_leaves_no_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _init(root, "dev")
            code = run_review(
                root=root, i_am="ada", suite="checkout-retry", status="blocked", reason="#12"
            )
            self.assertEqual(code, EXIT_OK)
            names = sorted(p.name for p in (root / "suites" / "checkout-retry").iterdir())
            self.assertEqual(names, ["cases.md", "suite.yaml"])


class ForbidHostsTests(unittest.TestCase):
    def test_host_boundary_matching(self) -> None:
        hosts = ["prod.example.com", "example.com"]
        for text in (
            "curl prod.example.com/pay",
            "https://api.prod.example.com/x",
            "https://user@prod.example.com/x",
            "PROD.EXAMPLE.COM",
        ):
            with self.subTest(text=text):
                self.assertIn("prod.example.com", forbid_host_hits(text, hosts))
        for text in ("https://example.community", "notexample.com", "https://example.org"):
            with self.subTest(text=text):
                self.assertNotIn("example.com", forbid_host_hits(text, hosts))

    def test_inbox_prose_mention_is_not_a_url_hit(self) -> None:
        hosts = ["prod.example.com"]
        self.assertEqual(forbid_host_url_hits("Never hit prod.example.com.", hosts), [])
        self.assertEqual(forbid_host_url_hits("see https://a.prod.example.com", hosts), hosts)

    def test_bare_host_in_command_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            marker = Path(tmp) / "ran"
            _set_command(root, "checkout-retry", f"touch {marker} && curl -s prod.example.com/")
            result = _run(root, Path(tmp) / "receipts")
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertFalse(marker.exists())

    def test_one_forbidden_command_starts_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            _add_second_suite(root)
            marker = Path(tmp) / "second-ran"
            _set_command(root, "checkout-retry", "curl https://prod.example.com/pay")
            _set_command(root, "second-slice", f"touch {marker}")
            dest = Path(tmp) / "receipts"
            result = _run(root, dest)
            self.assertEqual(result.returncode, EXIT_CONTRACT, result.stderr)
            self.assertFalse(marker.exists())
            receipt = yaml.safe_load(next(dest.glob("*.yaml")).read_text(encoding="utf-8"))
            types = {
                event["suite"]: event["type"]
                for event in receipt["events"]
                if "suite" in event and event["type"] in {"refused", "not_started"}
            }
            self.assertEqual(types, {"checkout-retry": "refused", "second-slice": "not_started"})


class WorkflowWiringTests(unittest.TestCase):
    WORKFLOW = REPO / ".github" / "workflows" / "overlay.yml"
    DOC = REPO / "docs" / "overlay-ci.md"

    def test_tool_checkout_never_falls_back_to_caller_sha(self) -> None:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("|| github.workflow_sha", text)
        self.assertEqual(text.count("name: Require tool_ref"), 3)

    def test_tool_requirements_installed_before_callers(self) -> None:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        blocks = re.findall(r"name: Install Overlay\n\s+run: \|\n(.*?)\n\n", text, re.S)
        self.assertEqual(len(blocks), 3)
        for block in blocks:
            self.assertLess(
                block.index("_aiops/requirements.txt"), block.index("-r requirements.txt")
            )
            self.assertNotIn("elif", block)

    def test_every_doc_snippet_passes_tool_ref(self) -> None:
        text = self.DOC.read_text(encoding="utf-8")
        snippets = re.findall(
            r"uses: <tool-repo>/\.github/workflows/overlay\.yml@\S+\n    with:\n(.*?)```",
            text,
            re.S,
        )
        self.assertGreaterEqual(len(snippets), 5)
        for snippet in snippets:
            self.assertIn("tool_ref:", snippet)


if __name__ == "__main__":
    unittest.main()
