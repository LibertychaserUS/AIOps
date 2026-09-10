"""In-memory GitHub Rulesets API. No sockets, no live hosts."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        if isinstance(payload, (bytes, bytearray)):
            raw = bytes(payload)
        else:
            raw = json.dumps(payload).encode("utf-8")
        self._buf = io.BytesIO(raw)
        self.headers = {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class FakeGitHub:
    """Enough of Rulesets + Pulls APIs for Forge tests. No merge."""

    def __init__(self) -> None:
        self.rulesets: list[dict] = []
        self.pulls: list[dict] = []
        self.issue_comments: list[dict] = []
        self.review_comments: list[dict] = []
        self.check_runs: list[dict] = []
        self.releases: list[dict] = []
        self.main_sha = "abc1234deadbeef"
        self.calls: list[tuple[str, str, dict | None]] = []
        self.next_id = 1
        self.next_pr = 1
        self.next_comment = 1
        self.next_release = 1
        self.fail_status: int | None = None
        self.fail_on: set[str] = set()

    def urlopen(self, req: Request, timeout: int | None = None) -> FakeResponse:
        method = (req.get_method() or "GET").upper()
        parsed = urlparse(req.full_url)
        host = (parsed.hostname or "").lower()
        if host in {"api.github.com", "ilovelearningguide.com"} or host.endswith(
            ".ilovelearningguide.com"
        ):
            raise AssertionError(f"test urlopen must not reach live host {host!r}")
        path = parsed.path
        body = None
        if req.data:
            body = json.loads(req.data.decode("utf-8"))
        self.calls.append((method, path, body))

        if self.fail_status and (not self.fail_on or method in self.fail_on):
            raise HTTPError(req.full_url, self.fail_status, "synthetic", hdrs=None, fp=io.BytesIO(b'{"message":"synthetic"}'))

        parts = [p for p in path.split("/") if p]
        # repos / owner / name / resource [ / id [ / merge ] ]
        if len(parts) < 4 or parts[0] != "repos":
            raise HTTPError(req.full_url, 404, "not a repo route", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))

        if len(parts) >= 6 and parts[3] == "pulls" and parts[5] == "merge":
            raise HTTPError(
                req.full_url,
                405,
                "merge is not implemented",
                hdrs=None,
                fp=io.BytesIO(b'{"message":"forge never merges"}'),
            )

        if parts[3] == "commits" and len(parts) >= 6 and parts[5] == "check-runs":
            if method != "GET":
                raise HTTPError(req.full_url, 405, "method", hdrs=None, fp=io.BytesIO(b"{}"))
            return FakeResponse(200, {"check_runs": list(self.check_runs)})

        if parts[3] == "issues" and len(parts) >= 6 and parts[5] == "comments":
            if method == "GET":
                return FakeResponse(200, list(self.issue_comments))
            if method == "POST":
                created = {
                    "id": self.next_comment,
                    "body": (body or {}).get("body"),
                    "user": {"login": "forge-ops"},
                }
                self.next_comment += 1
                self.issue_comments.append(created)
                return FakeResponse(201, created)
            raise HTTPError(req.full_url, 405, "method", hdrs=None, fp=io.BytesIO(b"{}"))

        if parts[3] == "pulls" and len(parts) >= 6 and parts[5] == "comments":
            if method != "GET":
                raise HTTPError(req.full_url, 405, "method", hdrs=None, fp=io.BytesIO(b"{}"))
            return FakeResponse(200, list(self.review_comments))

        if parts[3] == "pulls":
            return self._handle_pulls(method, parts, parsed.query, body, req)

        if parts[3] == "releases":
            return self._handle_releases(method, parts, body, req)

        if parts[3] == "git" and len(parts) >= 6 and parts[4] == "ref":
            ref = "/".join(parts[5:])
            if method != "GET":
                raise HTTPError(req.full_url, 405, "method", hdrs=None, fp=io.BytesIO(b"{}"))
            if ref == "heads/main":
                return FakeResponse(200, {"ref": "refs/heads/main", "object": {"sha": self.main_sha}})
            raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))

        if parts[3] != "rulesets":
            raise HTTPError(req.full_url, 404, "not a ruleset route", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))

        owner, repo = parts[1], parts[2]
        ruleset_id = int(parts[4]) if len(parts) > 4 else None

        if method == "GET" and ruleset_id is None:
            return FakeResponse(200, list(self.rulesets))
        if method == "GET" and ruleset_id is not None:
            found = self._by_id(ruleset_id)
            if found is None:
                raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))
            return FakeResponse(200, found)
        if method == "POST" and ruleset_id is None:
            created = dict(body or {})
            created["id"] = self.next_id
            created["_owner"] = owner
            created["_repo"] = repo
            self.next_id += 1
            self.rulesets.append(created)
            return FakeResponse(201, created)
        if method == "PUT" and ruleset_id is not None:
            found = self._by_id(ruleset_id)
            if found is None:
                raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))
            found.clear()
            found.update(body or {})
            found["id"] = ruleset_id
            found["_owner"] = owner
            found["_repo"] = repo
            return FakeResponse(200, found)
        raise HTTPError(req.full_url, 405, "method not allowed", hdrs=None, fp=io.BytesIO(b'{"message":"method"}'))

    def _handle_pulls(
        self,
        method: str,
        parts: list[str],
        query: str,
        body: dict | None,
        req: Request,
    ) -> FakeResponse:
        from urllib.parse import parse_qs

        owner = parts[1]
        number = int(parts[4]) if len(parts) > 4 else None
        if method == "GET" and number is None:
            qs = parse_qs(query)
            head = (qs.get("head") or [None])[0]
            want = head.split(":", 1)[-1] if head else None
            found = []
            for pull in self.pulls:
                ref = (pull.get("head") or {}).get("ref") if isinstance(pull.get("head"), dict) else None
                if want is None or ref == want:
                    found.append(pull)
            return FakeResponse(200, found)
        if method == "GET" and number is not None:
            found_one = self._pull_by_number(number)
            if found_one is None:
                raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))
            return FakeResponse(200, found_one)
        if method == "POST" and number is None:
            created = {
                "number": self.next_pr,
                "title": (body or {}).get("title"),
                "body": (body or {}).get("body"),
                "draft": bool((body or {}).get("draft", True)),
                "head": {"ref": (body or {}).get("head"), "repo": {"full_name": f"{owner}/{parts[2]}"}},
                "base": {"ref": (body or {}).get("base")},
                "html_url": f"https://forge.test/{owner}/{parts[2]}/pull/{self.next_pr}",
            }
            self.next_pr += 1
            self.pulls.append(created)
            return FakeResponse(201, created)
        if method == "PATCH" and number is not None:
            found_one = self._pull_by_number(number)
            if found_one is None:
                raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))
            if body:
                if "title" in body:
                    found_one["title"] = body["title"]
                if "body" in body:
                    found_one["body"] = body["body"]
            return FakeResponse(200, found_one)
        raise HTTPError(req.full_url, 405, "method not allowed", hdrs=None, fp=io.BytesIO(b'{"message":"method"}'))

    def _handle_releases(
        self,
        method: str,
        parts: list[str],
        body: dict | None,
        req: Request,
    ) -> FakeResponse:
        if len(parts) >= 6 and parts[4] == "tags":
            tag = parts[5]
            if method != "GET":
                raise HTTPError(req.full_url, 405, "method", hdrs=None, fp=io.BytesIO(b"{}"))
            found = next((item for item in self.releases if item.get("tag_name") == tag), None)
            if found is None:
                raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))
            return FakeResponse(200, found)
        if method == "POST" and len(parts) == 4:
            created = dict(body or {})
            created["id"] = self.next_release
            created["html_url"] = (
                f"https://forge.test/{parts[1]}/{parts[2]}/releases/tag/{created.get('tag_name')}"
            )
            self.next_release += 1
            self.releases.append(created)
            return FakeResponse(201, created)
        raise HTTPError(req.full_url, 405, "method not allowed", hdrs=None, fp=io.BytesIO(b'{"message":"method"}'))

    def _pull_by_number(self, number: int) -> dict | None:
        for item in self.pulls:
            if item.get("number") == number:
                return item
        return None

    def _by_id(self, ruleset_id: int) -> dict | None:
        for item in self.rulesets:
            if item.get("id") == ruleset_id:
                return item
        return None

    def methods(self) -> list[str]:
        return [method for method, _, _ in self.calls]

    def writes(self) -> list[tuple[str, str, dict | None]]:
        return [call for call in self.calls if call[0] in {"POST", "PUT", "PATCH", "DELETE"}]
