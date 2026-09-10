"""Forge status is read-only against the fake API."""

from __future__ import annotations

import io
import unittest

from forge import EXIT_AUTH, EXIT_OK, RULESET_NAME
from forge.status import run_status

from tests.forge.fake_github import FakeGitHub

FAKE_API = "https://forge.test"
REPO = "acme/widget"


class StatusTests(unittest.TestCase):
    def test_not_installed(self) -> None:
        fake = FakeGitHub()
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_status(
            repo=REPO,
            urlopen=fake.urlopen,
            base_url=FAKE_API,
            stdout=stdout,
            stderr=stderr,
            environ={"FORGE_GITHUB_TOKEN": "t"},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        self.assertIn("installed: no", stdout.getvalue())
        self.assertIn(RULESET_NAME, stdout.getvalue())
        self.assertEqual(fake.writes(), [])
        self.assertTrue(all(method == "GET" for method in fake.methods()))

    def test_installed_lists_protect_branches(self) -> None:
        fake = FakeGitHub()
        fake.rulesets.append(
            {
                "id": 4,
                "name": RULESET_NAME,
                "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            }
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_status(
            repo=REPO,
            urlopen=fake.urlopen,
            base_url=FAKE_API,
            stdout=stdout,
            stderr=stderr,
            environ={"GITHUB_TOKEN": "t"},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())
        text = stdout.getvalue()
        self.assertIn("installed: yes", text)
        self.assertIn("id: 4", text)
        self.assertIn("protect: main", text)
        self.assertEqual(fake.writes(), [])

    def test_missing_token(self) -> None:
        fake = FakeGitHub()
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = run_status(
            repo=REPO,
            urlopen=fake.urlopen,
            base_url=FAKE_API,
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_AUTH)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
