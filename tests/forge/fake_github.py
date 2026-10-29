"""In-memory GitHub Rulesets API. No sockets, no live hosts."""

from __future__ import annotations

import io
import json
from email.message import Message
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request

from forge.apply import safe_redirect


class FakeResponse:
    def __init__(self, status: int, payload: object, headers: dict[str, str] | None = None) -> None:
        self.status = status
        if isinstance(payload, (bytes, bytearray)):
            raw = bytes(payload)
        else:
            raw = json.dumps(payload).encode("utf-8")
        self._buf = io.BytesIO(raw)
        self.headers = {"Content-Type": "application/json", **(headers or {})}

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
        # tag name -> {"sha": ..., "type": "commit"} or {"sha": tagobj, "type": "tag", "peeled": commit}
        self.tags: dict[str, dict] = {}
        self.main_sha = "abc1234deadbeef"
        self.calls: list[tuple[str, str, dict | None]] = []
        self.next_id = 1
        self.next_pr = 1
        self.next_comment = 1
        self.next_release = 1
        self.fail_status: int | None = None
        self.fail_on: set[str] = set()
        # None = fail every matching call; N = fail the first N, then serve normally.
        self.fail_times: int | None = None
        # Only paths containing this substring fail (None = every path).
        self.fail_path_contains: str | None = None
        self.fail_headers: dict[str, str] = {}
        self.fail_body: bytes = b'{"message":"synthetic"}'
        # path -> absolute URL; served as 302 and followed via Forge's redirect rules.
        self.redirects: dict[str, str] = {}
        # (url, headers as sent) for every request, redirect hops included.
        self.requests: list[tuple[str, dict[str, str]]] = []
        # Ruleset list paging (None = one page) and org-level rulesets that only
        # show up when includes_parents is not false.
        self.ruleset_page_size: int | None = None
        self.parent_rulesets: list[dict] = []

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
        self.requests.append((req.full_url, dict(req.header_items())))

        target = self.redirects.get(path)
        if target is not None and req.full_url != target:
            hop = Request(
                target,
                method=method,
                headers={k: v for k, v in req.header_items() if k.lower() not in ("content-length", "content-type")},
            )
            return self.urlopen(safe_redirect(req, hop), timeout=timeout)

        if (
            self.fail_status
            and (not self.fail_on or method in self.fail_on)
            and (self.fail_path_contains is None or self.fail_path_contains in path)
        ):
            if self.fail_times is None or self.fail_times > 0:
                if self.fail_times is not None:
                    self.fail_times -= 1
                hdrs = Message()
                for key, value in self.fail_headers.items():
                    hdrs[key] = value
                raise HTTPError(req.full_url, self.fail_status, "synthetic", hdrs=hdrs, fp=io.BytesIO(self.fail_body))

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
            if ref.startswith("tags/"):
                found_tag = self.tags.get(ref[len("tags/"):])
                if found_tag is not None:
                    return FakeResponse(
                        200,
                        {
                            "ref": f"refs/{ref}",
                            "object": {"sha": found_tag["sha"], "type": found_tag.get("type", "commit")},
                        },
                    )
            raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))

        if parts[3] == "git" and len(parts) == 6 and parts[4] == "tags":
            if method != "GET":
                raise HTTPError(req.full_url, 405, "method", hdrs=None, fp=io.BytesIO(b"{}"))
            for item in self.tags.values():
                if item.get("type") == "tag" and item["sha"] == parts[5]:
                    return FakeResponse(200, {"sha": parts[5], "object": {"sha": item["peeled"], "type": "commit"}})
            raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))

        if parts[3] != "rulesets":
            raise HTTPError(req.full_url, 404, "not a ruleset route", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))

        owner, repo = parts[1], parts[2]
        ruleset_id = int(parts[4]) if len(parts) > 4 else None

        if method == "GET" and ruleset_id is None:
            return self._list_rulesets(parsed)
        if method == "GET" and ruleset_id is not None:
            found = self._by_id(ruleset_id)
            if found is None:
                raise HTTPError(req.full_url, 404, "not found", hdrs=None, fp=io.BytesIO(b'{"message":"not found"}'))
            return FakeResponse(200, found)
        if method == "POST" and ruleset_id is None:
            # GitHub: a second repo ruleset with the same name is 422 Validation Failed
            # (an org-level ruleset of that name does not block a repo one).
            if any(
                item.get("name") == (body or {}).get("name")
                and item.get("source_type", "Repository") == "Repository"
                for item in self.rulesets
            ):
                raise HTTPError(
                    req.full_url,
                    422,
                    "Unprocessable Entity",
                    hdrs=None,
                    fp=io.BytesIO(b'{"message":"Validation Failed","errors":["Name has already been taken"]}'),
                )
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
            base = (qs.get("base") or [None])[0]
            found = []
            for pull in self.pulls:
                ref = (pull.get("head") or {}).get("ref") if isinstance(pull.get("head"), dict) else None
                pull_base = (pull.get("base") or {}).get("ref") if isinstance(pull.get("base"), dict) else None
                if want is not None and ref != want:
                    continue
                if base is not None and pull_base != base:
                    continue
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

    def _list_rulesets(self, parsed) -> FakeResponse:
        from urllib.parse import parse_qs

        qs = parse_qs(parsed.query)
        items = list(self.rulesets)
        if (qs.get("includes_parents") or ["true"])[0] != "false":
            items = list(self.parent_rulesets) + items
        if not self.ruleset_page_size:
            return FakeResponse(200, items)
        page = int((qs.get("page") or ["1"])[0])
        size = self.ruleset_page_size
        chunk = items[(page - 1) * size : page * size]
        headers = {}
        if page * size < len(items):
            query = "&".join(
                f"{key}={value[0]}" for key, value in qs.items() if key != "page"
            )
            nxt = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query}&page={page + 1}"
            headers["Link"] = f'<{nxt}>; rel="next"'
        return FakeResponse(200, chunk, headers)

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
