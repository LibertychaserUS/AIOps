"""Contract tests for the closed forge check registry (ADR 0009).

Every registered check: unique name, in the documented order, has a test that
names it, has a docs row, and survives a minimal non-git root without raising.
The registry file itself has no runtime discovery.
"""

from __future__ import annotations

import io
import re
import tempfile
import unittest
from pathlib import Path

from forge.check import build_context, run_one
from forge.checks import CHECKS, HIDDEN, KNOWN_NEEDS, CheckContext, Step

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "forge" / "checks" / "__init__.py"

# The checklist order `forge check` prints today. Changing it is a design change.
EXPECTED_ORDER = (
    "overlay validate",
    "overlay cover",
    "pr-title",
    "pr-body",
    "deny_paths",
    "suite_guard",
    "docs_sync",
    "sop-lock",
    "schema/check.py",
    "unittest",
)

_MINIMAL_FORGE = "schema: forge-config/v1\nprotect:\n  - main\n"


def _minimal_context(root: Path) -> CheckContext:
    (root / "forge.yaml").write_text(_MINIMAL_FORGE, encoding="utf-8")
    return build_context(root, {}, out=io.StringIO(), err=io.StringIO())


class RegistryShapeTests(unittest.TestCase):
    def test_checks_is_an_immutable_tuple(self) -> None:
        self.assertIsInstance(CHECKS, tuple)
        with self.assertRaises(TypeError):
            CHECKS[0] = CHECKS[1]  # type: ignore[index]

    def test_names_are_unique_and_non_empty(self) -> None:
        names = [check.name for check in CHECKS]
        self.assertTrue(all(isinstance(name, str) and name.strip() for name in names), names)
        self.assertEqual(len(names), len(set(names)), names)

    def test_order_matches_the_documented_checklist(self) -> None:
        self.assertEqual(tuple(check.name for check in CHECKS), EXPECTED_ORDER)

    def test_every_check_declares_known_needs(self) -> None:
        for check in CHECKS:
            with self.subTest(check=check.name):
                self.assertIsInstance(check.needs, frozenset)
                self.assertTrue(check.needs <= KNOWN_NEEDS, check.needs)
                self.assertTrue(callable(check.applies))
                self.assertTrue(callable(check.run))

    def test_registry_source_has_no_runtime_discovery(self) -> None:
        text = REGISTRY.read_text(encoding="utf-8")
        for banned in ("importlib", "pkgutil", "entry_points", "__import__", "iter_modules", "walk_packages"):
            self.assertNotIn(banned, text, banned)
        self.assertRegex(text, re.compile(r"^CHECKS: tuple\[Check, \.\.\.\] = \($", re.MULTILINE))


class RegistryCoverageTests(unittest.TestCase):
    def test_every_check_has_a_test_module_naming_it(self) -> None:
        test_files = [path for path in (ROOT / "tests" / "forge").glob("test_*.py") if path.name != Path(__file__).name]
        corpus = {path.name: path.read_text(encoding="utf-8") for path in test_files}
        for check in CHECKS:
            with self.subTest(check=check.name):
                hits = [name for name, text in corpus.items() if check.name in text]
                self.assertTrue(hits, f"no tests/forge/test_*.py mentions {check.name!r}")

    def test_every_check_has_a_docs_row(self) -> None:
        docs = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8") + (
            ROOT / "docs" / "forge-config.md"
        ).read_text(encoding="utf-8")
        for check in CHECKS:
            with self.subTest(check=check.name):
                self.assertIn(check.name, docs)


class RegistryRuntimeTests(unittest.TestCase):
    def test_every_check_returns_a_step_on_a_minimal_non_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _minimal_context(Path(tmp))
            self.assertIsNotNone(ctx.config)
            self.assertIsNone(ctx.changed)
            for check in CHECKS:
                with self.subTest(check=check.name):
                    reason = check.applies(ctx)
                    step = run_one(check, ctx)
                    if reason == HIDDEN:
                        self.assertIsNone(step)
                        continue
                    self.assertIsInstance(step, Step)
                    assert step is not None
                    self.assertEqual(step.name, check.name)
                    self.assertIn(step.status, {"ok", "skip", "fail"})

    def test_runner_disciplines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No forge.yaml: forge.yaml-based checks skip with the fixed reason.
            ctx = build_context(root, {}, out=io.StringIO(), err=io.StringIO())
            self.assertIsNone(ctx.config)
            for check in CHECKS:
                if "forge.yaml" in check.needs:
                    step = run_one(check, ctx)
                    assert step is not None
                    self.assertEqual((step.status, step.detail), ("skip", "no forge.yaml"), check.name)
            # Unloadable forge.yaml: those checks fail with the config message.
            (root / "forge.yaml").write_text("schema: forge-config/v1\nprotekt: [x]\n", encoding="utf-8")
            ctx = build_context(root, {}, out=io.StringIO(), err=io.StringIO())
            self.assertIsNotNone(ctx.config_error)
            for check in CHECKS:
                if "forge.yaml" in check.needs:
                    step = run_one(check, ctx)
                    assert step is not None
                    self.assertEqual(step.status, "fail", check.name)
                    self.assertIn("protekt", step.detail)


if __name__ == "__main__":
    unittest.main()
