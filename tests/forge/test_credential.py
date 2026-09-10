"""Host-injected credential probe. Never talks to live GitHub. Never prints secrets."""

from __future__ import annotations

import unittest

from forge.credential import (
    MISSING_IN_ACTIONS,
    WriteCredential,
    probe_write_credential,
    redact_secrets,
)


class ProbeTests(unittest.TestCase):
    def test_actions_is_not_submit_cred(self) -> None:
        leak = "ghs_this_must_not_appear"
        cred = probe_write_credential(
            environ={"GITHUB_ACTIONS": "true", "GITHUB_TOKEN": leak, "GH_TOKEN": leak},
            gh_status=lambda: True,
            git_extraheader=lambda: True,
        )
        self.assertFalse(cred.present)
        self.assertEqual(cred.source, "none")
        self.assertEqual(cred.detail, MISSING_IN_ACTIONS.detail)
        self.assertNotIn(leak, cred.detail)
        self.assertNotIn(leak, repr(cred))

    def test_github_token_alone_is_not_enough(self) -> None:
        leak = "ghs_this_must_not_appear"
        cred = probe_write_credential(
            environ={"GITHUB_TOKEN": leak, "FORGE_GITHUB_TOKEN": leak},
            gh_status=lambda: False,
            git_extraheader=lambda: False,
        )
        self.assertFalse(cred.present)
        self.assertNotIn(leak, cred.detail)
        self.assertNotIn(leak, repr(cred))

    def test_gh_token_presence_does_not_store_value(self) -> None:
        leak = "gho_this_must_not_appear"
        cred = probe_write_credential(
            environ={"GH_TOKEN": leak},
            gh_status=lambda: False,
            git_extraheader=lambda: False,
        )
        self.assertTrue(cred.present)
        self.assertEqual(cred.source, "GH_TOKEN")
        self.assertNotIn(leak, cred.detail)
        self.assertNotIn(leak, repr(cred))

    def test_extraheader_presence(self) -> None:
        cred = probe_write_credential(
            environ={},
            gh_status=lambda: False,
            git_extraheader=lambda: True,
        )
        self.assertTrue(cred.present)
        self.assertEqual(cred.source, "git-extraheader")

    def test_gh_login(self) -> None:
        cred = probe_write_credential(
            environ={},
            gh_status=lambda: True,
            git_extraheader=lambda: False,
        )
        self.assertTrue(cred.present)
        self.assertEqual(cred.source, "gh-login")

    def test_missing(self) -> None:
        cred = probe_write_credential(
            environ={},
            gh_status=lambda: False,
            git_extraheader=lambda: False,
        )
        self.assertFalse(cred.present)
        self.assertEqual(cred.source, "none")

    def test_redact(self) -> None:
        raw = "Authorization: Bearer ghp_abc123TOKEN and github_pat_zzz_yyy"
        cleaned = redact_secrets(raw)
        self.assertNotIn("ghp_abc123TOKEN", cleaned)
        self.assertNotIn("github_pat_zzz_yyy", cleaned)
        self.assertIn("REDACTED", cleaned)

    def test_write_credential_repr_omits_detail(self) -> None:
        cred = WriteCredential(True, "GH_TOKEN", "should-not-need-secret")
        self.assertNotIn("should-not-need-secret", repr(cred))


if __name__ == "__main__":
    unittest.main()
