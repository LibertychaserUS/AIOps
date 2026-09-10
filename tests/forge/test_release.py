"""Forge release against a fake GitHub API. Never talks to a live host."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from forge import EXIT_API, EXIT_AUTH, EXIT_CONFIG, EXIT_OK
from forge.__main__ import main
from forge.release import parse_products, parse_version, product_tag, run_release
from tests.forge.fake_github import FakeGitHub

ROOT = Path(__file__).resolve().parents[2]
FAKE_API = "https://forge.test"
REPO = "acme/widget"


def _release(**kwargs):
    fake = kwargs.pop("fake", FakeGitHub())
    stdout = kwargs.pop("stdout", io.StringIO())
    stderr = kwargs.pop("stderr", io.StringIO())
    env = kwargs.pop("environ", {"FORGE_GITHUB_TOKEN": "test-token"})
    code = run_release(
        repo=kwargs.pop("repo", REPO),
        version=kwargs.pop("version", "1.0.1"),
        urlopen=fake.urlopen,
        base_url=FAKE_API,
        stdout=stdout,
        stderr=stderr,
        environ=env,
        root=kwargs.pop("root", ROOT),
        **kwargs,
    )
    return code, stdout.getvalue(), stderr.getvalue(), fake


class ParseTests(unittest.TestCase):
    def test_version_and_products(self) -> None:
        self.assertEqual(parse_version("1.0.1"), "1.0.1")
        self.assertEqual(parse_version("v1.0.1"), "1.0.1")
        self.assertEqual(parse_products("both"), ("overlay", "forge"))
        self.assertEqual(parse_products("overlay"), ("overlay",))
        self.assertEqual(product_tag("overlay", "1.0.1"), "overlay-v1.0.1")


class ReleaseDryRunTests(unittest.TestCase):
    def test_dry_run_needs_no_token_and_posts_nothing(self) -> None:
        fake = FakeGitHub()
        code, out, err, _ = _release(
            fake=fake,
            dry_run=True,
            environ={},
            sha="unused",
        )
        self.assertEqual(code, EXIT_OK, err)
        self.assertIn("dry-run", out)
        self.assertIn("not production CD", out)
        self.assertIn("overlay-v1.0.1", out)
        self.assertIn("forge-v1.0.1", out)
        self.assertEqual(fake.calls, [])

    def test_cli_dry_run(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            [
                "release",
                "--repo",
                REPO,
                "--version",
                "1.0.1",
                "--dry-run",
                "--root",
                str(ROOT),
            ],
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("overlay-v1.0.1", stdout.getvalue())


class ReleaseWriteTests(unittest.TestCase):
    def test_posts_two_releases_on_main_sha(self) -> None:
        fake = FakeGitHub()
        fake.main_sha = "ddd1111bbbb2222cccc3333aaaa4444eeee5555"
        code, out, err, _ = _release(fake=fake)
        self.assertEqual(code, EXIT_OK, err)
        posts = [call for call in fake.writes() if call[0] == "POST"]
        self.assertEqual(len(posts), 2)
        tags = [body.get("tag_name") for _, _, body in posts]
        self.assertEqual(tags, ["overlay-v1.0.1", "forge-v1.0.1"])
        for _, _, body in posts:
            assert body is not None
            self.assertEqual(body["target_commitish"], fake.main_sha)
            self.assertEqual(body["make_latest"], "false")
            self.assertFalse(body["draft"])
        self.assertIn("published overlay-v1.0.1", out)
        self.assertIn("published forge-v1.0.1", out)

    def test_existing_tag_is_red(self) -> None:
        fake = FakeGitHub()
        fake.releases.append({"tag_name": "overlay-v1.0.1", "id": 9})
        code, _, err, _ = _release(fake=fake, products="overlay", sha="abc1234")
        self.assertEqual(code, EXIT_API, err)
        self.assertIn("already exists", err)
        self.assertEqual(len(fake.writes()), 0)

    def test_missing_token_is_red(self) -> None:
        code, _, err, _ = _release(environ={}, sha="abc1234")
        self.assertEqual(code, EXIT_AUTH, err)
        self.assertIn("FORGE_GITHUB_TOKEN", err)

    def test_learning_guide_is_refused(self) -> None:
        code, _, err, _ = _release(
            repo="First-Light-TechHK/LearningGuidePortal",
            dry_run=True,
            environ={},
        )
        self.assertEqual(code, EXIT_CONFIG, err)
        self.assertIn("refusing", err)

    def test_version_mismatch_is_red(self) -> None:
        code, _, err, _ = _release(version="9.9.9", dry_run=True, environ={})
        self.assertEqual(code, EXIT_CONFIG, err)
        self.assertIn("__version__", err)


class WorkshopReleaseWorkflowTests(unittest.TestCase):
    def test_release_workflow_is_dispatch_only(self) -> None:
        text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", text)
        self.assertNotIn("python -m forge submit", text)
        self.assertNotIn("overlay generate", text)
        self.assertIn("python -m forge release", text)
        data = __import__("yaml").safe_load(text)
        on_field = data.get("on") or data.get(True)
        self.assertIn("workflow_dispatch", on_field)
        self.assertNotIn("push", on_field if isinstance(on_field, dict) else [])


if __name__ == "__main__":
    unittest.main()
