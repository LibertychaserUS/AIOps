"""SOP lock: temp fixtures + this workshop. No GitHub write."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from forge.__main__ import main
from forge.sop_lock import (
    EXIT_SOP,
    check_codeowners,
    codeowners_covers,
    collect_issues,
    run_sop_lock,
)

from forge import EXIT_OK

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

    def test_ci_yml_unittest_job_on_push_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "ci.yml",
                "name: ci\non:\n  push:\njobs:\n  unittest:\n"
                "    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: python3 -m unittest discover -s tests -t . -q\n",
            )
            issues = collect_issues(root)
            self.assertFalse(any("unittest" in item.message for item in issues), issues)

    def test_ci_yml_non_unittest_job_discover_is_red(self) -> None:
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


class HardenedLockTests(unittest.TestCase):
    def _ci_issues(self, mutate) -> list[str]:
        from forge.sop_lock import _check_workshop_ci

        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / ".github" / "workflows" / "ci.yml", mutate(text))
            return [item.message for item in _check_workshop_ci(root)]

    def test_workshop_ci_is_green(self) -> None:
        self.assertEqual(self._ci_issues(lambda text: text), [])

    def test_fail_open_ci_jobs_are_red(self) -> None:
        cases = {
            "job continue-on-error": lambda t: t.replace(
                "  sop-lock:\n    name: sop-lock\n",
                "  sop-lock:\n    name: sop-lock\n    continue-on-error: true\n",
            ),
            "step continue-on-error": lambda t: t.replace(
                "      - name: sop-lock\n",
                "      - name: sop-lock\n        continue-on-error: true\n",
            ),
            "|| true": lambda t: t.replace(
                "python -m forge sop-lock --root .", "python -m forge sop-lock --root . || true"
            ),
            "; exit 0": lambda t: t.replace(
                "python3 -m unittest discover -s tests -t . -q",
                "python3 -m unittest discover -s tests -t . -q; exit 0",
            ),
            "set +e": lambda t: t.replace(
                "run: python -m forge pr-title --root .",
                "run: |\n          set +e\n          python -m forge pr-title --root .",
            ),
            "pr-title if": lambda t: t.replace(
                "if: github.event_name == 'pull_request'",
                "if: github.event_name == 'pull_request' || always()",
            ),
            "sop-lock if": lambda t: t.replace(
                "  sop-lock:\n    name: sop-lock\n",
                "  sop-lock:\n    name: sop-lock\n    if: false\n",
            ),
            "renamed check": lambda t: t.replace("    name: unittest\n", "    name: unit\n"),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                issues = self._ci_issues(mutate)
                self.assertTrue(issues, label)

    def test_pr_title_if_quoting_variants_are_green(self) -> None:
        for variant in (
            'if: "github.event_name == \'pull_request\'"',
            "if: ${{ github.event_name=='pull_request' }}",
            'if: github.event_name == "pull_request"',
        ):
            with self.subTest(variant):
                issues = self._ci_issues(
                    lambda t, v=variant: t.replace("if: github.event_name == 'pull_request'", v)
                )
                self.assertEqual(issues, [])

    def _rule_issues(self, yaml_text: str) -> list[str]:
        from forge.sop_lock import _check_workshop_branch_rules

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.yaml"
            path.write_text(yaml_text, encoding="utf-8")
            return [item.message for item in _check_workshop_branch_rules(path)]

    def test_workshop_forge_yaml_branch_rules_are_green(self) -> None:
        self.assertEqual(self._rule_issues((ROOT / "forge.yaml").read_text(encoding="utf-8")), [])

    def test_check_names_only_in_comments_or_other_branch_are_red(self) -> None:
        checks = "      - overlay-check\n      - pr-title\n      - forge-check\n      - sop-lock\n      - unittest\n"
        text = (
            "schema: forge-config/v1\n"
            "# overlay-check pr-title forge-check sop-lock unittest\n"
            "protect:\n  - dev\n  - main\nbranches:\n"
            "  dev:\n    required_checks:\n      - unittest\n    approvals: 0\n"
            "  main:\n    required_checks:\n" + checks + "    approvals: 1\n    code_owners: true\n"
        )
        issues = self._rule_issues(text)
        self.assertTrue(any("branches.dev.required_checks" in m for m in issues), issues)

    def test_main_review_weakened_is_red(self) -> None:
        base = (ROOT / "forge.yaml").read_text(encoding="utf-8")
        for label, old, new in (
            ("approvals", "    approvals: 1\n    code_owners: true\n", "    approvals: 0\n    code_owners: true\n"),
            ("code_owners", "    approvals: 1\n    code_owners: true\n", "    approvals: 1\n    code_owners: false\n"),
        ):
            with self.subTest(label):
                self.assertIn(old, base)
                issues = self._rule_issues(base.replace(old, new))
                self.assertTrue(any(f"branches.main.{label}" in m for m in issues), issues)

    def test_floating_uses_refs_are_red(self) -> None:
        from forge.sop_lock import floating_uses_ref

        for ref in (
            "actions/checkout@main",
            "actions/checkout@master",
            "acme/x/.github/workflows/w.yml@refs/heads/main",
            "acme/x/.github/workflows/w.yml@dev",
            "actions/checkout@HEAD",
            "actions/checkout",
        ):
            with self.subTest(ref):
                self.assertIsNotNone(floating_uses_ref(ref))
        for ref in (
            "actions/checkout@v4",
            "actions/setup-python@v5.1.0",
            "LibertychaserUS/AIOps/.github/workflows/overlay.yml@overlay-v2.0.0",
            "actions/checkout@" + "a" * 40,
            "./.github/workflows/overlay.yml",
            "docker://alpine:3.20",
        ):
            with self.subTest(ref):
                self.assertIsNone(floating_uses_ref(ref))

    def test_floating_action_in_workflow_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / ".github" / "workflows" / "bad.yml",
                "name: bad\non:\n  pull_request:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: actions/checkout@main\n",
            )
            issues = collect_issues(root)
            self.assertTrue(any("pin" in item.message for item in issues), issues)


class CodeownersLockTests(unittest.TestCase):
    """Workshop only: CODEOWNERS must own suites/**, forge.yaml, overlay.yaml."""

    def _workshop(self, root: Path) -> None:
        for rel in ("overlay/__init__.py", "forge/__init__.py", "skills/use-overlay/SKILL.md", "docs/sop.md"):
            _write(root / rel, "")

    def test_workshop_codeowners_is_green(self) -> None:
        self.assertEqual(check_codeowners(ROOT), [])
        self.assertIn("forge.yaml @", (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8"))

    def test_missing_codeowners_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workshop(root)
            messages = [str(issue) for issue in check_codeowners(root)]
            self.assertEqual(len(messages), 1)
            self.assertIn(".github/CODEOWNERS: missing", messages[0])

    def test_uncovered_paths_are_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workshop(root)
            _write(root / ".github" / "CODEOWNERS", "docs/** @team\nsuites/** @team\nforge.yaml\n")
            messages = [str(issue) for issue in check_codeowners(root)]
            self.assertEqual(
                messages,
                [
                    ".github/CODEOWNERS: must assign an owner to forge.yaml",
                    ".github/CODEOWNERS: must assign an owner to overlay.yaml",
                ],
            )

    def test_suite_yaml_glob_and_star_owner_are_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workshop(root)
            _write(
                root / ".github" / "CODEOWNERS",
                "# comment\nsuites/**/suite.yaml @a\n/forge.yaml @b\noverlay.yaml @c @d\n",
            )
            self.assertEqual(check_codeowners(root), [])
            _write(root / ".github" / "CODEOWNERS", "* @everyone\n")
            self.assertEqual(check_codeowners(root), [])

    def test_consumer_root_is_not_checked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(check_codeowners(Path(tmp)), [])

    def test_codeowners_pattern_matching(self) -> None:
        self.assertTrue(codeowners_covers("suites/**", "suites/x/suite.yaml"))
        self.assertTrue(codeowners_covers("suites/", "suites/x/suite.yaml"))
        self.assertTrue(codeowners_covers("suites", "suites/x/suite.yaml"))
        self.assertTrue(codeowners_covers("suites/**/suite.yaml", "suites/x/suite.yaml"))
        self.assertTrue(codeowners_covers("*.yaml", "forge.yaml"))
        self.assertTrue(codeowners_covers("*", "overlay.yaml"))
        self.assertFalse(codeowners_covers("suites/*", "suites/x/suite.yaml"))
        self.assertFalse(codeowners_covers("forge/", "forge.yaml"))
        self.assertFalse(codeowners_covers("docs/**", "suites/x/suite.yaml"))
        self.assertFalse(codeowners_covers("/overlay/overlay.yaml", "overlay.yaml"))

    def test_sop_lock_cli_reports_missing_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._workshop(root)
            _write(root / ".github" / "CODEOWNERS", "suites/** @team\noverlay.yaml @team\n")
            stderr = io.StringIO()
            code = run_sop_lock(root, stdout=io.StringIO(), stderr=stderr)
            self.assertEqual(code, EXIT_SOP)
            self.assertIn("must assign an owner to forge.yaml", stderr.getvalue())
