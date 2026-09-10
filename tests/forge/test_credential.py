"""Named FORGE_SUBMIT_TOKEN only. Never talks to live GitHub. Never prints secrets."""

from __future__ import annotations

import unittest

from forge import SUBMIT_TOKEN_ENV
from forge.credential import (
    WriteCredential,
    probe_write_credential,
    redact_secrets,
)


class ProbeTests(unittest.TestCase):
    def test_named_secret_is_enough(self) -> None:
        leak = "gho_this_must_not_appear"
        cred = probe_write_credential(
            environ={SUBMIT_TOKEN_ENV: leak},
            gh_status=lambda: False,
            git_extraheader=lambda: False,
        )
        self.assertTrue(cred.present)
        self.assertEqual(cred.source, SUBMIT_TOKEN_ENV)
        self.assertNotIn(leak, cred.detail)
        self.assertNotIn(leak, repr(cred))

    def test_github_token_alone_is_not_enough(self) -> None:
        leak = "ghs_this_must_not_appear"
        cred = probe_write_credential(
            environ={"GITHUB_TOKEN": leak, "FORGE_GITHUB_TOKEN": leak},
            gh_status=lambda: True,
            git_extraheader=lambda: True,
        )
        self.assertFalse(cred.present)
        self.assertNotIn(leak, cred.detail)
        self.assertNotIn(leak, repr(cred))

    def test_gh_token_is_not_enough(self) -> None:
        leak = "gho_this_must_not_appear"
        cred = probe_write_credential(
            environ={"GH_TOKEN": leak},
            gh_status=lambda: False,
            git_extraheader=lambda: False,
        )
        self.assertFalse(cred.present)
        self.assertNotIn(leak, cred.detail)

    def test_extraheader_is_not_enough(self) -> None:
        cred = probe_write_credential(
            environ={},
            gh_status=lambda: False,
            git_extraheader=lambda: True,
        )
        self.assertFalse(cred.present)
        self.assertEqual(cred.source, "none")

    def test_gh_login_is_not_enough(self) -> None:
        cred = probe_write_credential(
            environ={},
            gh_status=lambda: True,
            git_extraheader=lambda: False,
        )
        self.assertFalse(cred.present)
        self.assertEqual(cred.source, "none")

    def test_empty_named_secret_is_not_enough(self) -> None:
        cred = probe_write_credential(
            environ={SUBMIT_TOKEN_ENV: "   "},
            gh_status=lambda: True,
            git_extraheader=lambda: True,
        )
        self.assertFalse(cred.present)

    def test_actions_github_token_is_not_submit(self) -> None:
        leak = "ghs_this_must_not_appear"
        cred = probe_write_credential(
            environ={"GITHUB_ACTIONS": "true", "GITHUB_TOKEN": leak, "GH_TOKEN": leak},
            gh_status=lambda: True,
            git_extraheader=lambda: True,
        )
        self.assertFalse(cred.present)
        self.assertNotIn(leak, cred.detail)

    def test_redact(self) -> None:
        raw = "Authorization: Bearer ghp_abc123TOKEN and github_pat_zzz_yyy"
        cleaned = redact_secrets(raw)
        self.assertNotIn("ghp_abc123TOKEN", cleaned)
        self.assertNotIn("github_pat_zzz_yyy", cleaned)
        self.assertIn("REDACTED", cleaned)

    def test_write_credential_repr_omits_detail(self) -> None:
        cred = WriteCredential(True, SUBMIT_TOKEN_ENV, "should-not-need-secret")
        self.assertNotIn("should-not-need-secret", repr(cred))


if __name__ == "__main__":
    unittest.main()
