"""SOP lock: temp fixtures + this workshop. No GitHub write."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_OK
from forge.__main__ import main
from forge.sop_lock import EXIT_SOP, collect_issues, run_sop_lock

ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class WorkshopSopLockTests(unittest.TestCase):
    def test_skill_discovery_dirs_point_at_skills(self) -> None:
        from forge.sop_lock import check_skill_discovery

        issues = check_skill_discovery(ROOT)
        self.assertEqual(issues, [])
        for rel in (".agents/skills", ".cursor/skills", ".claude/skills"):
            self.assertTrue((ROOT / rel / "use-forge" / "SKILL.md").is_file())
            self.assertTrue((ROOT / rel / "use-overlay" / "SKILL.md").is_file())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("--agent codex", readme)
        self.assertIn("--agent cursor", readme)
        self.assertIn("--agent claude-code", readme)
        self.assertNotIn("--agent copilot", readme)

    def test_workshop_is_green(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_sop_lock(ROOT, stdout=stdout, stderr=stderr)
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("ok", stdout.getvalue())

    def test_cli_sop_lock(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["sop-lock", "--root", str(ROOT)],
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())


class WorkflowLockTests(unittest.TestCase):
    def test_generate_on_push_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "bad.yml",
                "name: bad\non:\n  push:\njobs:\n  gen:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m overlay generate --inbox inbox/x.md\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("generate" in item.message for item in issues), issues)

    def test_openai_key_on_push_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "bad.yml",
                "name: bad\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                "    env:\n      OPENAI_API_KEY: secret\n    steps:\n      - run: echo hi\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("OPENAI_API_KEY" in item.message for item in issues), issues)

    def test_workflow_call_ci_yml_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "bad.yml",
                "name: bad\non:\n  pull_request:\njobs:\n  x:\n"
                "    uses: First-Light-TechHK/LearningGuidePortal/.github/workflows/ci.yml@main\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any(issues), issues)

    def test_unittest_bypass_on_push_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "self-test.yml",
                "name: self-test\non:\n  push:\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m unittest discover -s tests -t .\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("unittest" in item.message for item in issues), issues)

    def test_forge_check_unit_layer_on_push_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "forge-check.yml",
                "name: forge-check\non:\n  push:\njobs:\n  forge-check:\n"
                "    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: python3 -m unittest discover -s tests/forge -t .\n",
            )
            issues = collect_issues(root)
            self.assertFalse(any("unittest" in item.message for item in issues), issues)

    def test_ci_yml_unittest_on_push_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "ci.yml",
                "name: ci\non:\n  push:\njobs:\n  sop-lock:\n"
                "    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: python3 -m unittest discover -s tests/forge -t .\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("unittest" in item.message for item in issues), issues)

    def test_checkout_learningguideportal_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "bad.yml",
                "name: bad\non:\n  pull_request:\njobs:\n  x:\n"
                "    runs-on: ubuntu-latest\n    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "        with:\n          repository: First-Light-TechHK/LearningGuidePortal\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("LearningGuidePortal" in item.message for item in issues), issues)

    def test_floating_uses_main_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "bad.yml",
                "name: bad\non:\n  pull_request:\njobs:\n  x:\n"
                "    uses: LibertychaserUS/AIOps/.github/workflows/overlay.yml@main\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("pin" in item.message or "main" in item.message for item in issues), issues)

    def test_path_filtered_common_ci_yml_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "overlay" / "__init__.py", "")
            _write(root / "forge" / "__init__.py", "")
            _write(root / "docs" / "sop.md", "# sop\n")
            _write(root / "skills" / "use-overlay" / "SKILL.md", "## Lock\n不绿不能合 overlay-check\n")
            _write(
                root / ".github" / "workflows" / "ci.yml",
                "name: ci\non:\n  pull_request:\n    paths:\n      - docs/**\n"
                "jobs:\n  pr-title:\n    if: github.event_name == 'pull_request'\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m forge pr-title --root .\n"
                "  sop-lock:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m forge sop-lock --root .\n",
            )
            issues = collect_issues(root)
            self.assertTrue(
                any("path-filter" in item.message for item in issues),
                issues,
            )

    def test_path_filtered_product_workflow_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "overlay" / "__init__.py", "")
            _write(root / "forge" / "__init__.py", "")
            _write(root / "docs" / "sop.md", "# sop\n")
            _write(root / "skills" / "use-overlay" / "SKILL.md", "## Lock\n不绿不能合 overlay-check\n")
            _write(
                root / ".github" / "workflows" / "overlay-check.yml",
                "name: overlay-check\non:\n  pull_request:\n    paths:\n      - overlay/**\n"
                "jobs:\n  overlay-check:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m forge ci-select --check overlay-check\n",
            )
            issues = collect_issues(root)
            self.assertTrue(
                any("path-filter" in item.message for item in issues),
                issues,
            )

    def test_leftover_common_workflow_files_are_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "overlay" / "__init__.py", "")
            _write(root / "forge" / "__init__.py", "")
            _write(root / "docs" / "sop.md", "# sop\n")
            _write(root / "skills" / "use-overlay" / "SKILL.md", "## Lock\n不绿不能合 overlay-check\n")
            _write(
                root / ".github" / "workflows" / "ci.yml",
                "name: ci\non:\n  pull_request:\njobs:\n  pr-title:\n"
                "    if: github.event_name == 'pull_request'\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m forge pr-title --root .\n"
                "  sop-lock:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m forge sop-lock --root .\n",
            )
            _write(
                root / ".github" / "workflows" / "pr-title.yml",
                "name: pr-title\non:\n  pull_request:\njobs:\n  pr-title:\n"
                "    runs-on: ubuntu-latest\n    steps:\n      - run: echo leftover\n",
            )
            _write(
                root / ".github" / "workflows" / "sop-lock.yml",
                "name: sop-lock\non:\n  push:\njobs:\n  sop-lock:\n"
                "    runs-on: ubuntu-latest\n    steps:\n      - run: echo leftover\n",
            )
            issues = collect_issues(root)
            leftovers = [item for item in issues if "leftover" in item.message]
            self.assertTrue(any("pr-title.yml" in item.path for item in leftovers), issues)
            self.assertTrue(any("sop-lock.yml" in item.path for item in leftovers), issues)
            self.assertFalse(
                any("forge-check.yml" in item.message for item in leftovers),
                leftovers,
            )
            self.assertFalse(
                any("overlay-check.yml" in item.message for item in leftovers),
                leftovers,
            )

    def test_comment_no_generate_on_push_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "ok.yml",
                "# No generate.\nname: ok\non:\n  push:\njobs:\n  x:\n"
                "    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n",
            )
            issues = collect_issues(root)
            self.assertFalse(any("generate" in item.message for item in issues), issues)


class SkillAndHuskyTests(unittest.TestCase):
    def test_skill_without_lock_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "skills" / "use-x" / "SKILL.md",
                "---\nname: use-x\ndescription: x\n---\n\n# X\n\n## Instructions\n\nDo x.\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("## Lock" in item.message for item in issues), issues)

    def test_husky_dir_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".husky").mkdir()
            issues = collect_issues(root)
            self.assertTrue(any(".husky" in item.path for item in issues), issues)


class SubmitSecretLockTests(unittest.TestCase):
    def test_submit_without_named_secret_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "forge" / "submit.py", "def run_submit():\n    return 0\n")
            issues = collect_issues(root)
            self.assertTrue(
                any("FORGE_SUBMIT_TOKEN" in item.message for item in issues),
                issues,
            )

    def test_workshop_submit_requires_named_secret(self) -> None:
        text = (ROOT / "forge" / "submit.py").read_text(encoding="utf-8")
        self.assertIn("FORGE_SUBMIT_TOKEN", text)
        self.assertNotIn('get("GITHUB_TOKEN"', text)
        self.assertNotIn("resolve_token(", text)
        cred = (ROOT / "forge" / "credential.py").read_text(encoding="utf-8")
        self.assertIn("FORGE_SUBMIT_TOKEN", cred)
        self.assertNotIn('source="gh-login"', cred)


class KernelLockTests(unittest.TestCase):
    def test_overlay_kernel_with_product_host_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "overlay" / "x.py", "HOST = 'ilovelearningguide.com'\n")
            issues = collect_issues(root)
            self.assertTrue(any("ilovelearningguide" in item.message for item in issues), issues)


class ExitCodeTests(unittest.TestCase):
    def test_red_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".husky").mkdir()
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_sop_lock(root, stdout=stdout, stderr=stderr)
            self.assertEqual(code, EXIT_SOP)
            self.assertTrue(stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
