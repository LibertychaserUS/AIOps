from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import yaml
from overlay.receipt import ALLOWED_WROTE_BY, ReceiptError, build_receipt, receipt_filename

from tests.overlay.support import LG, REPO, run_overlay, write_generic_root

HTTP_MODULES = {
    "http",
    "http.client",
    "urllib",
    "urllib.request",
    "urllib.error",
    "urllib.parse",
    "requests",
    "httpx",
    "aiohttp",
}


class ReceiptTests(unittest.TestCase):
    def test_select_writes_receipt_as_select(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "receipts"
            result = run_overlay(
                "select",
                "--branch",
                "main",
                "--root",
                str(LG),
                "--write-receipt",
                str(dest),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            files = list(dest.glob("*.yaml"))
            self.assertEqual(len(files), 1, files)
            data = yaml.safe_load(files[0].read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], "overlay-receipt/v1")
            self.assertEqual(data["wrote_by"], "select")
            self.assertEqual(data["branch"], "main")
            types = [event["type"] for event in data["events"]]
            self.assertIn("selected", types)
            self.assertIn("dropped", types)
            selected = [event for event in data["events"] if event["type"] == "selected"]
            self.assertEqual([event["suite"] for event in selected], ["my-learning"])
            dropped = {event["suite"]: event["rule"] for event in data["events"] if event["type"] == "dropped"}
            self.assertEqual(dropped.get("payment"), "never_red_statuses")
            self.assertEqual(dropped.get("login"), "never_red_statuses")
            self.assertFalse(
                any(item.get("type") == "human-review" for item in data["evidence"]),
                data["evidence"],
            )

    def test_build_receipt_rejects_model(self) -> None:
        with self.assertRaises(ReceiptError):
            build_receipt(
                wrote_by="model",
                git_sha="abc",
                branch="main",
                events=[],
                evidence=[],
            )
        self.assertEqual(ALLOWED_WROTE_BY, frozenset({"select", "run"}))

    def test_receipt_module_has_no_http_client(self) -> None:
        path = REPO / "overlay" / "receipt.py"
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

    def test_receipt_filename_uses_branch_string(self) -> None:
        self.assertEqual(receipt_filename(None, "abc"), "unknown-abc.yaml")
        self.assertEqual(receipt_filename("", "abc"), "unknown-abc.yaml")
        self.assertEqual(
            receipt_filename("dev/feature", "0123456789abcdef"),
            "dev-feature-0123456789ab.yaml",
        )
        self.assertEqual(receipt_filename(None, "abc", "99"), "99.yaml")

    def _select_receipt(self, root: Path, dest: Path, env: dict[str, str]):
        merged = {
            "GITHUB_RUN_ID": "",
            "GITHUB_SHA": "abc123def4567890",
            **env,
        }
        return run_overlay(
            "select",
            "--root",
            str(root),
            "--write-receipt",
            str(dest),
            env=merged,
        )

    def test_omitted_branch_receipt_uses_base_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "receipts"
            result = self._select_receipt(
                LG,
                dest,
                {"GITHUB_BASE_REF": "hotfix", "GITHUB_REF_NAME": "cursor/ignored"},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data, name = _one(dest)
            self.assertEqual(data["branch"], "hotfix")
            self.assertTrue(name.startswith("hotfix-"), name)

    def test_omitted_branch_receipt_uses_configured_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "receipts"
            result = self._select_receipt(
                LG,
                dest,
                {"GITHUB_BASE_REF": "", "GITHUB_REF_NAME": "hotfix"},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data, name = _one(dest)
            self.assertEqual(data["branch"], "hotfix")
            self.assertTrue(name.startswith("hotfix-"), name)

    def test_omitted_branch_receipt_uses_branches_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            dest = Path(tmp) / "receipts"
            result = self._select_receipt(
                root,
                dest,
                {"GITHUB_BASE_REF": "", "GITHUB_REF_NAME": "cursor/not-configured"},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("branches.default", result.stderr)
            data, name = _one(dest)
            self.assertEqual(data["branch"], "default")
            self.assertTrue(name.startswith("default-"), name)

    def test_omitted_branch_receipt_uses_main_when_ref_is_unconfigured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "receipts"
            result = self._select_receipt(
                LG,
                dest,
                {"GITHUB_BASE_REF": "", "GITHUB_REF_NAME": "cursor/not-configured"},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("using main", result.stderr)
            data, name = _one(dest)
            self.assertEqual(data["branch"], "main")
            self.assertTrue(name.startswith("main-"), name)


def _one(dest: Path) -> tuple[dict, str]:
    files = list(dest.glob("*.yaml"))
    if len(files) != 1:
        raise AssertionError(files)
    data = yaml.safe_load(files[0].read_text(encoding="utf-8"))
    return data, files[0].name


if __name__ == "__main__":
    unittest.main()
