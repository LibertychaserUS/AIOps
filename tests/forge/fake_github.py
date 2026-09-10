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
    """Enough of GET/POST/PUT /repos/{owner}/{repo}/rulesets for Forge tests."""

    def __init__(self) -> None:
        self.rulesets: list[dict] = []
        self.calls: list[tuple[str, str, dict | None]] = []
        self.next_id = 1
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
        # repos / owner / name / rulesets [ / id ]
        if len(parts) < 4 or parts[0] != "repos" or parts[3] != "rulesets":
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

    def _by_id(self, ruleset_id: int) -> dict | None:
        for item in self.rulesets:
            if item.get("id") == ruleset_id:
                return item
        return None

    def methods(self) -> list[str]:
        return [method for method, _, _ in self.calls]

    def writes(self) -> list[tuple[str, str, dict | None]]:
        return [call for call in self.calls if call[0] in {"POST", "PUT", "PATCH", "DELETE"}]
