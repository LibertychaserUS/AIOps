"""overlay generate with a fake HTTP transport. No live network."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from overlay.generate import run_generate

from overlay import EXIT_CONTRACT, EXIT_MISSING_KEY, EXIT_OK
from tests.overlay.support import run_overlay, write_generic_root

EXTRACT = json.dumps(
    {"functions": [{"id": "FN-login-retry", "intent": "Retry stays one charge"}]}
)
CASES = json.dumps(
    {
        "title": "Checkout retry",
        "functions": [
            {
                "id": "FN-login-retry",
                "heading": "Retry stays one charge",
                "functional": "- one charge",
                "negative": "- double click",
                "edge": "- finished receipt",
            }
        ],
    }
)


class _Resp:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


class FakeTransport:
    def __init__(self, contents: list[str]) -> None:
        self.contents = list(contents)
        self.bodies: list[dict] = []

    def __call__(self, request, timeout=None):
        del timeout
        self.bodies.append(json.loads(request.data.decode("utf-8")))
        content = self.contents.pop(0)
        payload = json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
        return _Resp(payload)


class GenerateTests(unittest.TestCase):
    def test_missing_api_key_exits_3_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            shutil.rmtree(root / "suites")
            called = {"n": 0}

            def _boom(*_args, **_kwargs):
                called["n"] += 1
                raise AssertionError("network")

            code = run_generate(
                root,
                "inbox/checkout-retry.md",
                environ={},
                urlopen=_boom,
                stderr=__import__("io").StringIO(),
            )
            self.assertEqual(code, EXIT_MISSING_KEY)
            self.assertEqual(called["n"], 0)
            self.assertFalse((root / "suites").exists())

    def test_cli_missing_key_exits_3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            shutil.rmtree(root / "suites")
            result = run_overlay(
                "generate",
                "--root",
                str(root),
                "--inbox",
                "inbox/checkout-retry.md",
                env={"OPENAI_API_KEY": "", "OPENROUTER_API_KEY": ""},
            )
            self.assertEqual(result.returncode, EXIT_MISSING_KEY, result.stderr)
            self.assertIn("OPENAI_API_KEY", result.stderr)
            self.assertFalse((root / "suites").exists())

    def test_blocked_refuses_even_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            original = path.read_text(encoding="utf-8").replace("status: active", "status: blocked")
            original = original.replace("blocked_reason: null", "blocked_reason: parked #12")
            path.write_text(original, encoding="utf-8")
            transport = FakeTransport([EXTRACT, CASES])
            code = run_generate(
                root,
                "inbox/checkout-retry.md",
                force=True,
                environ={"OPENAI_API_KEY": "test-key"},
                urlopen=transport,
                stderr=__import__("io").StringIO(),
            )
            self.assertEqual(code, EXIT_CONTRACT)
            self.assertEqual(transport.bodies, [])
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertIn("status: blocked", original)

    def test_existing_suite_without_force_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            path = root / "suites" / "checkout-retry" / "suite.yaml"
            original = path.read_text(encoding="utf-8")
            transport = FakeTransport([EXTRACT, CASES])
            code = run_generate(
                root,
                "inbox/checkout-retry.md",
                environ={"OPENAI_API_KEY": "test-key"},
                urlopen=transport,
                stderr=__import__("io").StringIO(),
            )
            self.assertEqual(code, EXIT_CONTRACT)
            self.assertEqual(transport.bodies, [])
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_writes_active_suite_from_fake_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            shutil.rmtree(root / "suites")
            transport = FakeTransport([EXTRACT, CASES])
            code = run_generate(
                root,
                "inbox/checkout-retry.md",
                environ={"OPENAI_API_KEY": "test-key"},
                urlopen=transport,
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(len(transport.bodies), 2)
            self.assertEqual(transport.bodies[0]["temperature"], 0)
            self.assertEqual(transport.bodies[1]["temperature"], 0)
            self.assertIn("extract", transport.bodies[0]["messages"][0]["content"].lower())
            self.assertIn("cases", transport.bodies[1]["messages"][0]["content"].lower())
            suite = (root / "suites" / "checkout-retry" / "suite.yaml").read_text(encoding="utf-8")
            cases = (root / "suites" / "checkout-retry" / "cases.md").read_text(encoding="utf-8")
            self.assertIn("schema: overlay-suite/v2", suite)
            self.assertIn("status: active", suite)
            self.assertNotIn("reviewed_by", suite)
            self.assertNotIn("armed", suite)
            self.assertIn("### Functional", cases)
            self.assertIn("### Negative", cases)
            self.assertIn("### Edge", cases)
            self.assertIn("FN-login-retry", cases)

    def test_parse_failure_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            shutil.rmtree(root / "suites")
            transport = FakeTransport(["this is not json"])
            code = run_generate(
                root,
                "inbox/checkout-retry.md",
                environ={"OPENAI_API_KEY": "test-key"},
                urlopen=transport,
                stderr=__import__("io").StringIO(),
            )
            self.assertEqual(code, EXIT_CONTRACT)
            self.assertFalse((root / "suites").exists())

    def test_force_replaces_non_blocked_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = write_generic_root(Path(tmp))
            transport = FakeTransport([EXTRACT, CASES])
            code = run_generate(
                root,
                "inbox/checkout-retry.md",
                force=True,
                environ={"OPENAI_API_KEY": "test-key"},
                urlopen=transport,
            )
            self.assertEqual(code, EXIT_OK, transport.bodies)
            suite = (root / "suites" / "checkout-retry" / "suite.yaml").read_text(encoding="utf-8")
            self.assertIn("status: active", suite)
            self.assertNotIn("reviewed_by", suite)


if __name__ == "__main__":
    unittest.main()
