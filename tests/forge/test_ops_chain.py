"""Overlay Ops review-bots + bounce. Fake GitHub only. Never merges."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_OK
from forge.__main__ import main
from forge.ops_chain import BOUNCE_MARK, bounce_body, run_bounce, run_review_bots
from tests.forge.fake_github import FakeGitHub

API = "https://forge.test"


class ReviewBotsTests(unittest.TestCase):
    def test_no_token_is_green_advisory(self) -> None:
        fake = FakeGitHub()
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_review_bots(
                repo="LibertychaserUS/AIOps",
                sha="abc",
                pr=3,
                write_report=Path(tmp),
                urlopen=fake.urlopen,
                base_url=API,
                environ={},
                stdout=stdout,
                stderr=stderr,
                wait_s=0,
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            self.assertTrue((Path(tmp) / "review-bots.yaml").is_file())
            self.assertEqual(fake.writes(), [])

    def test_sees_coderabbit_check_and_copilot_comment(self) -> None:
        fake = FakeGitHub()
        fake.check_runs.append({"name": "CodeRabbit"})
        fake.issue_comments.append(
            {"user": {"login": "copilot-pull-request-reviewer"}, "body": "note"}
        )
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            code = run_review_bots(
                repo="LibertychaserUS/AIOps",
                sha="deadbeef",
                pr=3,
                write_report=Path(tmp),
                urlopen=fake.urlopen,
                base_url=API,
                environ={"GITHUB_TOKEN": "t"},
                stdout=stdout,
                stderr=io.StringIO(),
                wait_s=0,
            )
            self.assertEqual(code, EXIT_OK)
            text = (Path(tmp) / "review-bots.yaml").read_text(encoding="utf-8")
            self.assertIn("CodeRabbit", text)
            self.assertIn("copilot", text.lower())

    def test_wait_polls_then_continues_without_bots(self) -> None:
        fake = FakeGitHub()
        slept: list[float] = []
        with tempfile.TemporaryDirectory() as tmp:
            code = run_review_bots(
                repo="LibertychaserUS/AIOps",
                sha="x",
                pr=1,
                write_report=Path(tmp),
                urlopen=fake.urlopen,
                base_url=API,
                environ={"GITHUB_TOKEN": "t"},
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                wait_s=10,
                poll_s=5,
                sleeper=slept.append,
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(slept, [5, 5])
            text = (Path(tmp) / "review-bots.yaml").read_text(encoding="utf-8")
            self.assertIn("advisory", text)

    def test_cli_ops_review(self) -> None:
        fake = FakeGitHub()
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "ops-review",
                    "--repo",
                    "LibertychaserUS/AIOps",
                    "--sha",
                    "s",
                    "--pr",
                    "2",
                    "--write-report",
                    tmp,
                ],
                urlopen=fake.urlopen,
                base_url=API,
                environ={"GITHUB_TOKEN": "t"},
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )
            self.assertEqual(code, EXIT_OK)


class BounceTests(unittest.TestCase):
    def test_dry_run_writes_report_no_comment(self) -> None:
        fake = FakeGitHub()
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            code = run_bounce(
                repo="LibertychaserUS/AIOps",
                pr=3,
                failed=["spec"],
                write_report=Path(tmp),
                urlopen=fake.urlopen,
                base_url=API,
                environ={"GITHUB_TOKEN": "t"},
                stdout=stdout,
                stderr=io.StringIO(),
                run_url="https://example.test/run/1",
                dry_run=True,
            )
            self.assertEqual(code, EXIT_OK)
            report = (Path(tmp) / "ops-debug.yaml").read_text(encoding="utf-8")
            self.assertIn("bounce", report)
            self.assertIn("false", report)
            self.assertEqual(fake.writes(), [])

    def test_posts_bounce_comment_never_merge(self) -> None:
        fake = FakeGitHub()
        with tempfile.TemporaryDirectory() as tmp:
            code = run_bounce(
                repo="LibertychaserUS/AIOps",
                pr=9,
                failed=["overlay"],
                write_report=Path(tmp),
                urlopen=fake.urlopen,
                base_url=API,
                environ={"GITHUB_TOKEN": "t"},
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                run_url="https://example.test/run/9",
            )
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(len(fake.issue_comments), 1)
            body = str(fake.issue_comments[0]["body"])
            self.assertIn(BOUNCE_MARK, body)
            self.assertIn("打回", body)
            self.assertNotIn("/merge", "".join(path for _, path, _ in fake.calls))
            self.assertFalse(any(path.endswith("/merge") for _, path, _ in fake.calls))

    def test_cli_bounce_dry_run(self) -> None:
        fake = FakeGitHub()
        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "bounce",
                    "--repo",
                    "LibertychaserUS/AIOps",
                    "--pr",
                    "4",
                    "--failed",
                    "spec,overlay-check",
                    "--write-report",
                    tmp,
                    "--dry-run",
                ],
                urlopen=fake.urlopen,
                base_url=API,
                environ={},
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )
            self.assertEqual(code, EXIT_OK)
            self.assertTrue((Path(tmp) / "ops-debug.yaml").is_file())

    def test_bounce_body_lists_failed_jobs(self) -> None:
        text = bounce_body(failed=["spec", "overlay"], run_url="https://example.test/r")
        self.assertIn("spec, overlay", text)
        self.assertIn("打回", text)


class WorkflowDagTests(unittest.TestCase):
    def test_overlay_ops_order_is_locked(self) -> None:
        root = Path(__file__).resolve().parents[2]
        text = (root / ".github" / "workflows" / "overlay-check.yml").read_text(
            encoding="utf-8"
        )
        spec_at = text.find("name: spec")
        review_at = text.find("name: review-bots")
        bounce_at = text.find("name: bounce")
        self.assertGreater(spec_at, 0)
        self.assertGreater(review_at, spec_at)
        self.assertGreater(bounce_at, review_at)
        self.assertIn("python -m forge pr-title", text)
        self.assertIn("python -m forge ops-review", text)
        self.assertIn("python -m forge bounce", text)
        self.assertIn("needs: [select, spec]", text)
        self.assertIn("needs: [select, spec, review-bots]", text)
        self.assertNotIn("python -m forge submit", text)
        self.assertNotIn("python -m overlay generate", text)
        self.assertNotIn("--wait 60", text)
        self.assertIn("--wait 0", text)

        overlay = (root / ".github" / "workflows" / "overlay.yml").read_text(encoding="utf-8")
        self.assertIn("tool_repository", overlay)
        self.assertIn("${{ inputs.tool_repository }}", overlay)
        self.assertNotIn("repository: LibertychaserUS/AIOps", overlay)


if __name__ == "__main__":
    unittest.main()
