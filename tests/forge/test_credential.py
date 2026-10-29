"""One redactor for every Forge error path. Never prints secrets."""

from __future__ import annotations

import unittest

from forge.credential import REDACTED, redact_secrets


class RedactTests(unittest.TestCase):
    def test_bare_tokens(self) -> None:
        tokens = (
            "ghp_abc123TOKEN",
            "github_pat_11AAA_bbbCCC",
            "gho_oauthTOKEN",
            "ghu_userTOKEN",
            "ghs_serverTOKEN",
            "ghr_refreshTOKEN",
        )
        for token in tokens:
            with self.subTest(token=token):
                cleaned = redact_secrets(f"error: {token} rejected")
                self.assertNotIn(token, cleaned)
                self.assertIn(REDACTED, cleaned)

    def test_authorization_headers(self) -> None:
        for raw in (
            "AUTHORIZATION: bearer opaque.value",
            "Authorization: Bearer opaque.value",
            "AUTHORIZATION: basic b3BhcXVlLnZhbHVl",
        ):
            with self.subTest(raw=raw):
                cleaned = redact_secrets(f"http.extraheader={raw}")
                self.assertNotIn("opaque", cleaned)
                self.assertNotIn("b3BhcXVl", cleaned)
                self.assertRegex(cleaned, r"(?i)authorization:\s*\S+ REDACTED")

    def test_url_userinfo(self) -> None:
        raw = (
            "fatal: unable to access "
            "'https://x-access-token:opaque-secret@github.com/acme/app.git/': 403"
        )
        cleaned = redact_secrets(raw)
        self.assertNotIn("opaque-secret", cleaned)
        self.assertIn("https://x-access-token:REDACTED@github.com/acme/app.git/", cleaned)

    def test_plain_text_untouched(self) -> None:
        text = "git push origin abc:refs/heads/dev failed: rejected (non-fast-forward)"
        self.assertEqual(redact_secrets(text), text)
        self.assertEqual(redact_secrets("https://github.com/acme/app.git"), "https://github.com/acme/app.git")


if __name__ == "__main__":
    unittest.main()
