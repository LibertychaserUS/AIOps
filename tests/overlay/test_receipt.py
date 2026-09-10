from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import yaml

from overlay.receipt import ALLOWED_WROTE_BY, ReceiptError, build_receipt
from tests.overlay.support import LG, REPO, run_overlay

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
            reviewers = {
                item["suite"]: item["reviewed_by"]
                for item in data["evidence"]
                if item.get("type") == "human-review"
            }
            self.assertEqual(reviewers.get("my-learning"), "fixture")

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


if __name__ == "__main__":
    unittest.main()
