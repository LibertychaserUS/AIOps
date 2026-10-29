"""GitHubClient: bounded retries, rate-limit 403, safe redirects, 422-on-create. Fake API only."""

from __future__ import annotations

import io
import tempfile
import unittest
import urllib.request
from pathlib import Path

from forge.apply import (
    RETRY_AFTER_CAP_S,
    ForgeError,
    ForgeRedirectHandler,
    GitHubApiError,
    GitHubClient,
    default_urlopen,
    retry_delay,
    run_apply,
    safe_redirect,
)

from forge import EXIT_API, EXIT_AUTH, EXIT_OK
from tests.forge.fake_github import FakeGitHub

FAKE_API = "https://forge.test"
REPO = "acme/widget"
SIMPLE_YAML = (
    "schema: forge-config/v1\n"
    "protect:\n"
    "  - main\n"
    "required_checks:\n"
    "  - unit\n"
)


def _client(fake: FakeGitHub, sleeps: list[float]) -> GitHubClient:
    return GitHubClient("t", urlopen=fake.urlopen, base_url=FAKE_API, sleep=sleeps.append)


class RetryTests(unittest.TestCase):
    def test_get_retries_5xx_with_backoff_then_succeeds(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 502
        fake.fail_times = 2
        sleeps: list[float] = []
        payload = _client(fake, sleeps).list_rulesets("acme", "widget")
        self.assertEqual(payload, [])
        self.assertEqual(sleeps, [1.0, 2.0])
        self.assertEqual(fake.methods(), ["GET", "GET", "GET"])

    def test_get_gives_up_after_three_tries(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 503
        sleeps: list[float] = []
        with self.assertRaises(ForgeError) as ctx:
            _client(fake, sleeps).list_rulesets("acme", "widget")
        self.assertEqual(ctx.exception.code, EXIT_API)
        self.assertIn("503", ctx.exception.message)
        self.assertEqual(sleeps, [1.0, 2.0])
        self.assertEqual(len(fake.calls), 3)

    def test_429_honours_retry_after_capped(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 429
        fake.fail_times = 1
        fake.fail_headers = {"Retry-After": "7"}
        sleeps: list[float] = []
        _client(fake, sleeps).list_rulesets("acme", "widget")
        self.assertEqual(sleeps, [7.0])

        fake = FakeGitHub()
        fake.fail_status = 429
        fake.fail_times = 1
        fake.fail_headers = {"Retry-After": "3600"}
        sleeps = []
        _client(fake, sleeps).list_rulesets("acme", "widget")
        self.assertEqual(sleeps, [RETRY_AFTER_CAP_S])

    def test_429_exhausted_says_when_it_resets(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 429
        fake.fail_headers = {"X-RateLimit-Reset": "1700000000"}
        sleeps: list[float] = []
        with self.assertRaises(ForgeError) as ctx:
            _client(fake, sleeps).list_rulesets("acme", "widget")
        self.assertEqual(ctx.exception.code, EXIT_API)
        self.assertIn("rate limit", ctx.exception.message)
        self.assertIn("2023-11-14T22:13:20Z", ctx.exception.message)

    def test_writes_are_never_retried(self) -> None:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            fake = FakeGitHub()
            fake.fail_status = 500
            fake.fail_times = 1
            sleeps: list[float] = []
            with self.assertRaises(ForgeError) as ctx:
                _client(fake, sleeps).request(method, "/repos/acme/widget/rulesets", {"name": "x"})
            self.assertEqual(ctx.exception.code, EXIT_API, method)
            self.assertEqual(sleeps, [], method)
            self.assertEqual(len(fake.calls), 1, method)

    def test_4xx_get_is_not_retried(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 404
        sleeps: list[float] = []
        with self.assertRaises(ForgeError):
            _client(fake, sleeps).get_ruleset("acme", "widget", 9)
        self.assertEqual(sleeps, [])
        self.assertEqual(len(fake.calls), 1)

    def test_retry_delay_table(self) -> None:
        self.assertEqual(retry_delay("GET", 500, None, 1), 1.0)
        self.assertEqual(retry_delay("GET", 500, None, 2), 2.0)
        self.assertIsNone(retry_delay("GET", 500, None, 3))
        self.assertIsNone(retry_delay("POST", 500, None, 1))
        self.assertIsNone(retry_delay("GET", 403, None, 1))
        self.assertEqual(retry_delay("GET", 429, {"Retry-After": "2"}, 1), 2.0)


class RateLimit403Tests(unittest.TestCase):
    def test_remaining_zero_is_rate_limit_not_auth(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 403
        fake.fail_headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"}
        fake.fail_body = b'{"message":"API rate limit exceeded for user ID 1."}'
        with self.assertRaises(ForgeError) as ctx:
            _client(fake, []).list_rulesets("acme", "widget")
        self.assertEqual(ctx.exception.code, EXIT_API)
        self.assertNotIn("auth failed", ctx.exception.message)
        self.assertIn("resets at 2023-11-14T22:13:20Z", ctx.exception.message)

    def test_secondary_rate_limit_body_without_headers(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 403
        fake.fail_body = b'{"message":"You have exceeded a secondary rate limit. Please wait."}'
        with self.assertRaises(ForgeError) as ctx:
            _client(fake, []).list_rulesets("acme", "widget")
        self.assertEqual(ctx.exception.code, EXIT_API)
        self.assertIn("rate limit", ctx.exception.message)
        self.assertIn("resets at unknown", ctx.exception.message)

    def test_real_403_is_still_auth(self) -> None:
        fake = FakeGitHub()
        fake.fail_status = 403
        fake.fail_headers = {"X-RateLimit-Remaining": "4999"}
        fake.fail_body = b'{"message":"Resource not accessible by integration"}'
        with self.assertRaises(ForgeError) as ctx:
            _client(fake, []).list_rulesets("acme", "widget")
        self.assertEqual(ctx.exception.code, EXIT_AUTH)
        self.assertIn("auth failed (403)", ctx.exception.message)


class RedirectTests(unittest.TestCase):
    def _req(self, url: str) -> urllib.request.Request:
        return urllib.request.Request(url, headers={"Authorization": "Bearer t", "Accept": "x"})

    def test_cross_host_redirect_drops_the_token(self) -> None:
        fake = FakeGitHub()
        fake.redirects["/repos/acme/widget/rulesets"] = "https://mirror.test/repos/acme/widget/rulesets"
        _client(fake, []).list_rulesets("acme", "widget")
        first, second = fake.requests[:2]
        self.assertTrue(first[0].startswith(FAKE_API))
        self.assertIn("Authorization", first[1])
        self.assertTrue(second[0].startswith("https://mirror.test/"))
        self.assertNotIn("Authorization", second[1])

    def test_same_host_redirect_keeps_the_token(self) -> None:
        fake = FakeGitHub()
        fake.redirects["/repos/acme/widget/rulesets"] = f"{FAKE_API}/repos/acme/widget/rulesets/"
        # Trailing slash: the fake routes by path parts, so it still serves the list.
        _client(fake, []).list_rulesets("acme", "widget")
        self.assertEqual(len(fake.requests), 2)
        self.assertIn("Authorization", fake.requests[1][1])

    def test_https_to_http_redirect_is_refused(self) -> None:
        fake = FakeGitHub()
        fake.redirects["/repos/acme/widget/rulesets"] = "http://forge.test/repos/acme/widget/rulesets"
        with self.assertRaises(ForgeError) as ctx:
            _client(fake, []).list_rulesets("acme", "widget")
        self.assertEqual(ctx.exception.code, EXIT_API)
        self.assertIn("https to http", ctx.exception.message)
        self.assertEqual(len(fake.requests), 1)

    def test_redirect_to_production_host_is_refused(self) -> None:
        fake = FakeGitHub()
        fake.redirects["/repos/acme/widget/rulesets"] = "https://api.ilovelearningguide.com/x"
        with self.assertRaises(ForgeError) as ctx:
            _client(fake, []).list_rulesets("acme", "widget")
        self.assertIn("production host", ctx.exception.message)
        self.assertEqual(len(fake.requests), 1)

    def test_handler_applies_the_same_rules(self) -> None:
        handler = ForgeRedirectHandler()
        req = self._req("https://api.example/a")
        new = handler.redirect_request(req, None, 302, "Found", {}, "https://other.example/b")
        self.assertIsNotNone(new)
        self.assertFalse(new.has_header("Authorization"))
        self.assertEqual(new.get_method(), "GET")
        same = handler.redirect_request(req, None, 302, "Found", {}, "https://api.example/b")
        self.assertTrue(same.has_header("Authorization"))
        with self.assertRaises(ForgeError):
            handler.redirect_request(req, None, 301, "Moved", {}, "http://api.example/a")

    def test_safe_redirect_unit(self) -> None:
        req = self._req("https://api.example/a")
        hop = safe_redirect(req, self._req("https://api.example/b"))
        self.assertTrue(hop.has_header("Authorization"))
        hop = safe_redirect(req, self._req("https://cdn.example/b"))
        self.assertFalse(hop.has_header("Authorization"))

    def test_default_urlopen_still_refuses_production_first_url(self) -> None:
        with self.assertRaises(ForgeError):
            default_urlopen(urllib.request.Request("https://ilovelearningguide.com/api"))


class CreateConflictTests(unittest.TestCase):
    def test_422_on_create_falls_back_to_put_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "forge.yaml"
            path.write_text(SIMPLE_YAML, encoding="utf-8")
            fake = FakeGitHub()
            # The listing is empty at list time, then a same-name ruleset appears before the POST.
            original = fake.urlopen

            def racy(req, timeout=None):
                if req.get_method() == "POST" and not fake.rulesets:
                    fake.rulesets.append(
                        {"id": 41, "name": "forge-protected-main", "source_type": "Repository"}
                    )
                return original(req, timeout=timeout)

            stdout = io.StringIO()
            stderr = io.StringIO()
            code = run_apply(
                repo=REPO,
                path=path,
                token="t",
                urlopen=racy,
                base_url=FAKE_API,
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            self.assertIn("updated ruleset id=41 name=forge-protected-main", stdout.getvalue())
            methods = fake.methods()
            self.assertEqual(methods.count("POST"), 2)  # main (422) + tags (201)
            self.assertEqual(methods.count("PUT"), 1)
            self.assertEqual(len(fake.rulesets), 2)

    def test_fake_returns_422_for_duplicate_name(self) -> None:
        fake = FakeGitHub()
        client = GitHubClient("t", urlopen=fake.urlopen, base_url=FAKE_API)
        client.create_ruleset("acme", "widget", {"name": "dup"})
        with self.assertRaises(GitHubApiError) as ctx:
            client.create_ruleset("acme", "widget", {"name": "dup"})
        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.code, EXIT_API)


if __name__ == "__main__":
    unittest.main()
