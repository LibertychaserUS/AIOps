"""Forge release against a fake GitHub API. Never talks to a live host."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_API, EXIT_AUTH, EXIT_CONFIG, EXIT_OK
from forge.__main__ import main
from forge.release import parse_products, parse_version, product_tag, run_release
from tests.forge.fake_github import FakeGitHub

ROOT = Path(__file__).resolve().parents[2]
FAKE_API = "https://forge.test"
REPO = "acme/widget"

CHANGELOG = """# Changelog

## [overlay-2.0.0]

- Overlay v2

## [forge-1.1.0]

- Forge v1.1
"""


def _workshop_copy(tmp: str) -> Path:
    root = Path(tmp)
    (root / "overlay").mkdir()
    (root / "forge").mkdir()
    (root / "overlay" / "__init__.py").write_text('__version__ = "2.0.0"\n', encoding="utf-8")
    (root / "forge" / "__init__.py").write_text('__version__ = "1.1.0"\n', encoding="utf-8")
    (root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    (root / "forge.yaml").write_text(
        "schema: forge-config/v1\nprotect:\n  - main\nforbidden_live_repos:\n"
        "  - first-light-techhk/learningguideportal\n",
        encoding="utf-8",
    )
    return root


def _release(**kwargs):
    fake = kwargs.pop("fake", FakeGitHub())
    stdout = kwargs.pop("stdout", io.StringIO())
    stderr = kwargs.pop("stderr", io.StringIO())
    env = kwargs.pop("environ", {"FORGE_GITHUB_TOKEN": "test-token"})
    code = run_release(
        repo=kwargs.pop("repo", REPO),
        version=kwargs.pop("version", "1.1.0"),
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
        self.assertEqual(parse_version("1.1.0"), "1.1.0")
        self.assertEqual(parse_version("v1.1.0"), "1.1.0")
        self.assertEqual(parse_products("both"), ("overlay", "forge"))
        self.assertEqual(parse_products("overlay"), ("overlay",))
        self.assertEqual(product_tag("overlay", "2.0.0"), "overlay-v2.0.0")


class ReleaseDryRunTests(unittest.TestCase):
    def test_dry_run_needs_no_token_and_posts_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            fake = FakeGitHub()
            code, out, err, _ = _release(
                fake=fake,
                dry_run=True,
                environ={},
                sha="unused",
                products="forge",
                version="1.1.0",
                root=root,
            )
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn("dry-run", out)
            self.assertIn("not production CD", out)
            self.assertIn("forge-v1.1.0", out)
            self.assertIn("Forge v1.1", out)
            self.assertEqual(fake.calls, [])

    def test_cli_dry_run_single_product(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = main(
                [
                    "release",
                    "--repo",
                    REPO,
                    "--version",
                    "1.1.0",
                    "--products",
                    "forge",
                    "--dry-run",
                    "--root",
                    str(root),
                ],
                stdout=stdout,
                stderr=stderr,
                environ={},
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            self.assertIn("forge-v1.1.0", stdout.getvalue())

    def test_both_requires_equal_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            code, _, err, _ = _release(
                version="1.1.0",
                products="both",
                dry_run=True,
                environ={},
                root=root,
            )
            self.assertEqual(code, EXIT_CONFIG, err)
            self.assertIn("run twice", err)

    def test_missing_changelog_heading_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
            code, _, err, _ = _release(
                products="forge",
                version="1.1.0",
                dry_run=True,
                environ={},
                root=root,
            )
            self.assertEqual(code, EXIT_CONFIG, err)
            self.assertIn("## [forge-1.1.0]", err)


class ReleaseWriteTests(unittest.TestCase):
    def test_posts_one_release_on_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            fake = FakeGitHub()
            target = "ddd1111bbbb2222cccc3333aaaa4444eeee5555"
            code, out, err, _ = _release(
                fake=fake,
                products="forge",
                version="1.1.0",
                sha=target,
                root=root,
            )
            self.assertEqual(code, EXIT_OK, err)
            posts = [call for call in fake.writes() if call[0] == "POST"]
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0][2]["tag_name"], "forge-v1.1.0")
            self.assertEqual(posts[0][2]["target_commitish"], target)
            self.assertEqual(posts[0][2]["make_latest"], "false")
            self.assertIn("Forge v1.1", posts[0][2]["body"])
            self.assertIn("published forge-v1.1.0", out)

    def test_existing_tag_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            fake = FakeGitHub()
            fake.releases.append({"tag_name": "overlay-v2.0.0", "id": 9})
            code, _, err, _ = _release(
                fake=fake,
                products="overlay",
                version="2.0.0",
                sha="abc1234",
                root=root,
            )
            self.assertEqual(code, EXIT_API, err)
            self.assertIn("already exists", err)
            self.assertEqual(len(fake.writes()), 0)

    def test_existing_tag_at_another_sha_is_red_and_never_force_moves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            fake = FakeGitHub()
            fake.tags["overlay-v2.0.0"] = {
                "sha": "0000000aaaaaaaa1111111bbbbbbbb2222222ccc",
                "type": "commit",
            }
            code, _, err, _ = _release(
                fake=fake,
                products="overlay",
                version="2.0.0",
                sha="ddd1111bbbb2222cccc3333aaaa4444eeee5555",
                root=root,
            )
            self.assertEqual(code, EXIT_CONFIG, err)
            self.assertIn("overlay-v2.0.0", err)
            self.assertIn("force-move", err)
            self.assertEqual(len(fake.writes()), 0)

    def test_existing_tag_at_target_sha_only_attaches_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            target = "ddd1111bbbb2222cccc3333aaaa4444eeee5555"
            fake = FakeGitHub()
            fake.tags["forge-v1.1.0"] = {"sha": target, "type": "commit"}
            code, out, err, _ = _release(
                fake=fake,
                products="forge",
                version="1.1.0",
                sha=target,
                root=root,
            )
            self.assertEqual(code, EXIT_OK, err)
            posts = [call for call in fake.writes() if call[0] == "POST"]
            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0][2]["tag_name"], "forge-v1.1.0")
            self.assertIn("tag forge-v1.1.0 exists at", out)
            self.assertIn("published forge-v1.1.0", out)

    def test_annotated_tag_is_peeled_before_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            target = "ddd1111bbbb2222cccc3333aaaa4444eeee5555"
            fake = FakeGitHub()
            fake.tags["overlay-v2.0.0"] = {
                "sha": "9999999tagobject9999999tagobject99999999",
                "type": "tag",
                "peeled": target,
            }
            code, _, err, _ = _release(
                fake=fake,
                products="overlay",
                version="2.0.0",
                sha=target[:12],
                root=root,
            )
            self.assertEqual(code, EXIT_OK, err)
            self.assertEqual(len(fake.writes()), 1)

    def test_missing_token_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            code, _, err, _ = _release(
                environ={},
                sha="abc1234",
                products="forge",
                version="1.1.0",
                root=root,
            )
            self.assertEqual(code, EXIT_AUTH, err)
            self.assertIn("FORGE_GITHUB_TOKEN", err)

    def test_listed_live_repo_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            code, _, err, _ = _release(
                repo="First-Light-TechHK/LearningGuidePortal",
                dry_run=True,
                environ={},
                products="forge",
                version="1.1.0",
                root=root,
            )
            self.assertEqual(code, EXIT_CONFIG, err)
            self.assertIn("refusing", err)

    def test_unlisted_fork_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            code, _, err, _ = _release(
                repo="LibertychaserUS/LearningGuidePortal",
                dry_run=True,
                environ={},
                products="forge",
                version="1.1.0",
                root=root,
            )
            self.assertEqual(code, EXIT_OK, err)

    def test_version_mismatch_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _workshop_copy(tmp)
            code, _, err, _ = _release(
                version="9.9.9",
                products="forge",
                dry_run=True,
                environ={},
                root=root,
            )
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
