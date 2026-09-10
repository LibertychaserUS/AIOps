"""Install or update the default Forge ruleset. Does not write repo files."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from forge import (
    COPY_FILES_NOTE,
    EXIT_API,
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_OK,
    FORBIDDEN_REPOS,
    RULESET_JSON,
    RULESET_NAME,
    SCHEMA_ID,
)

UrlOpen = Callable[..., Any]

REPO_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
BRANCH_RE = re.compile(r"^(?:refs/heads/)?([A-Za-z0-9._][A-Za-z0-9._/-]*)$")
DEFAULT_API = "https://api.github.com"
DEFAULT_PROTECT = ("main",)
DEFAULT_PREFIXES = ("cursor/", "copilot/")
DEFAULT_DENY = (".github/workflows/ci.yml",)


class ForgeError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ForgeConfig:
    schema: str = SCHEMA_ID
    protect: list[str] = field(default_factory=lambda: list(DEFAULT_PROTECT))
    agent_branch_prefixes: list[str] = field(default_factory=lambda: list(DEFAULT_PREFIXES))
    deny_paths: list[str] = field(default_factory=lambda: list(DEFAULT_DENY))
    required_checks: list[str] = field(default_factory=list)
    min_approvals: int = 1
    code_owners: bool = False


def default_urlopen(req: urllib.request.Request, timeout: int = 30) -> Any:
    url = req.full_url if hasattr(req, "full_url") else str(req)
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("ilovelearningguide.com") or host == "ilovelearningguide.com":
        raise ForgeError(EXIT_API, "refusing production host")
    return urllib.request.urlopen(req, timeout=timeout)


def resolve_token(environ: dict[str, str] | os._Environ[str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    for key in ("FORGE_GITHUB_TOKEN", "GITHUB_TOKEN"):
        value = str(env.get(key, "")).strip()
        if value:
            return value
    return None


def parse_repo(repo: str) -> tuple[str, str]:
    text = (repo or "").strip()
    match = REPO_RE.fullmatch(text)
    if not match:
        raise ForgeError(EXIT_CONFIG, f"illegal repo: {repo!r} (use OWNER/NAME)")
    return match.group(1), match.group(2)


def assert_apply_allowed(owner: str, name: str) -> None:
    key = f"{owner}/{name}".lower()
    if key in FORBIDDEN_REPOS:
        raise ForgeError(EXIT_CONFIG, f"refusing to apply to {owner}/{name}")
    if "ilovelearningguide" in key:
        raise ForgeError(EXIT_CONFIG, f"refusing to apply to {owner}/{name}")


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    out: list[str] = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(text: str) -> Any:
    if text in {"true", "True"}:
        return True
    if text in {"false", "False"}:
        return False
    if text in {"null", "Null", "~"}:
        return None
    if len(text) >= 2 and (
        (text[0] == text[-1] == '"') or (text[0] == text[-1] == "'")
    ):
        return text[1:-1]
    if re.fullmatch(r"-?[0-9]+", text):
        return int(text)
    return text


class _YamlError(ValueError):
    pass


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the indent-based YAML subset used by forge-config/v1."""
    rows: list[tuple[int, int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw:
            raise _YamlError(f"line {lineno}: tabs are not allowed")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        rows.append((lineno, indent, stripped.strip()))
    if not rows:
        raise _YamlError("empty document")
    value, next_i = _parse_block(rows, 0, rows[0][1])
    if next_i != len(rows):
        raise _YamlError(f"line {rows[next_i][0]}: trailing content")
    if not isinstance(value, dict):
        raise _YamlError("document must be a mapping")
    return value


def _parse_block(rows: list[tuple[int, int, str]], i: int, indent: int) -> tuple[Any, int]:
    _, _, content = rows[i]
    if content.startswith("- ") or content == "-":
        return _parse_list(rows, i, indent)
    return _parse_map(rows, i, indent)


def _parse_map(
    rows: list[tuple[int, int, str]], i: int, indent: int
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while i < len(rows):
        lineno, ind, content = rows[i]
        if ind < indent:
            break
        if ind > indent:
            raise _YamlError(f"line {lineno}: unexpected indent")
        if content.startswith("- ") or content == "-":
            raise _YamlError(f"line {lineno}: expected a mapping entry")
        if ":" not in content:
            raise _YamlError(f"line {lineno}: expected key:")
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not key:
            raise _YamlError(f"line {lineno}: empty key")
        if rest:
            result[key] = _parse_scalar(rest)
            i += 1
            continue
        if i + 1 >= len(rows) or rows[i + 1][1] <= indent:
            result[key] = None
            i += 1
            continue
        child, i = _parse_block(rows, i + 1, rows[i + 1][1])
        result[key] = child
    return result, i


def _parse_list(rows: list[tuple[int, int, str]], i: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while i < len(rows):
        lineno, ind, content = rows[i]
        if ind < indent:
            break
        if ind > indent:
            raise _YamlError(f"line {lineno}: unexpected indent")
        if not content.startswith("- ") and content != "-":
            raise _YamlError(f"line {lineno}: expected a list item")
        rest = content[1:].strip()
        if rest:
            result.append(_parse_scalar(rest))
            i += 1
            continue
        if i + 1 >= len(rows) or rows[i + 1][1] <= indent:
            result.append(None)
            i += 1
            continue
        child, i = _parse_block(rows, i + 1, rows[i + 1][1])
        result.append(child)
    return result, i


def _string_list(value: Any, field: str, *, allow_empty: bool) -> list[str]:
    if value is None:
        if allow_empty:
            return []
        raise ForgeError(EXIT_CONFIG, f"illegal {field}: empty")
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ForgeError(EXIT_CONFIG, f"illegal {field}: expected a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ForgeError(EXIT_CONFIG, f"illegal {field} item: {item!r}")
        if ".." in item:
            raise ForgeError(EXIT_CONFIG, f"illegal {field} item: {item!r}")
        out.append(item)
    return out


def normalize_branch(name: str) -> str:
    match = BRANCH_RE.fullmatch(name.strip())
    if not match or ".." in name:
        raise ForgeError(EXIT_CONFIG, f"illegal branch: {name!r}")
    return match.group(1)


def validate_config(raw: dict[str, Any]) -> ForgeConfig:
    schema = raw.get("schema", SCHEMA_ID)
    if schema != SCHEMA_ID:
        raise ForgeError(EXIT_CONFIG, f"illegal schema: {schema!r}")

    if "protect" in raw:
        protect = [normalize_branch(item) for item in _string_list(raw["protect"], "protect", allow_empty=False)]
    else:
        protect = list(DEFAULT_PROTECT)

    if "agent_branch_prefixes" in raw:
        prefixes = _string_list(
            raw["agent_branch_prefixes"], "agent_branch_prefixes", allow_empty=False
        )
    else:
        prefixes = list(DEFAULT_PREFIXES)

    if "deny_paths" in raw:
        deny_paths = _string_list(raw["deny_paths"], "deny_paths", allow_empty=False)
    else:
        deny_paths = list(DEFAULT_DENY)

    if "required_checks" in raw:
        required_checks = _string_list(raw["required_checks"], "required_checks", allow_empty=True)
    else:
        required_checks = []

    review = raw.get("review")
    if review is None:
        review = {}
    if not isinstance(review, dict):
        raise ForgeError(EXIT_CONFIG, "illegal review: expected a mapping")

    min_approvals = review.get("min_approvals", 1)
    if isinstance(min_approvals, bool) or not isinstance(min_approvals, int) or min_approvals < 0:
        raise ForgeError(EXIT_CONFIG, f"illegal review.min_approvals: {min_approvals!r}")

    code_owners = review.get("code_owners", False)
    if not isinstance(code_owners, bool):
        raise ForgeError(EXIT_CONFIG, f"illegal review.code_owners: {code_owners!r}")

    return ForgeConfig(
        schema=SCHEMA_ID,
        protect=protect,
        agent_branch_prefixes=prefixes,
        deny_paths=deny_paths,
        required_checks=required_checks,
        min_approvals=min_approvals,
        code_owners=code_owners,
    )


def load_config(path: Path | None) -> ForgeConfig:
    if path is None:
        default = Path("forge.yaml")
        if not default.is_file():
            return ForgeConfig()
        path = default
    if not path.is_file():
        raise ForgeError(EXIT_CONFIG, f"forge.yaml not found: {path}")
    try:
        raw = parse_simple_yaml(path.read_text(encoding="utf-8"))
    except _YamlError as exc:
        raise ForgeError(EXIT_CONFIG, f"illegal forge.yaml: {exc}") from exc
    return validate_config(raw)


def load_ruleset_template() -> dict[str, Any]:
    if not RULESET_JSON.is_file():
        raise ForgeError(EXIT_CONFIG, f"missing ruleset template: {RULESET_JSON}")
    try:
        data = json.loads(RULESET_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ForgeError(EXIT_CONFIG, f"illegal ruleset template: {exc}") from exc
    if not isinstance(data, dict):
        raise ForgeError(EXIT_CONFIG, "illegal ruleset template: expected an object")
    return data


def build_payload(config: ForgeConfig, template: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.loads(json.dumps(template if template is not None else load_ruleset_template()))
    payload["name"] = RULESET_NAME
    payload["target"] = payload.get("target") or "branch"
    payload["enforcement"] = payload.get("enforcement") or "active"
    payload["bypass_actors"] = []
    payload["conditions"] = {
        "ref_name": {
            "include": [f"refs/heads/{branch}" for branch in config.protect],
            "exclude": [],
        }
    }
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ForgeError(EXIT_CONFIG, "illegal ruleset template: rules must be a list")
    found_pr = False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("type") == "pull_request":
            found_pr = True
            params = rule.setdefault("parameters", {})
            if not isinstance(params, dict):
                raise ForgeError(EXIT_CONFIG, "illegal pull_request parameters")
            params["required_approving_review_count"] = config.min_approvals
            params["require_code_owner_review"] = config.code_owners
            params.setdefault("dismiss_stale_reviews_on_push", True)
            params.setdefault("require_last_push_approval", False)
    if not found_pr:
        raise ForgeError(EXIT_CONFIG, "ruleset template is missing pull_request")
    types = {rule.get("type") for rule in rules if isinstance(rule, dict)}
    if "deletion" not in types or "non_fast_forward" not in types:
        raise ForgeError(EXIT_CONFIG, "ruleset template is missing deletion/non_fast_forward")
    return payload


def _as_ruleset_list(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("rulesets", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ForgeError(EXIT_API, "unexpected ruleset list shape")


def find_named_ruleset(items: list[dict[str, Any]], name: str = RULESET_NAME) -> dict[str, Any] | None:
    for item in items:
        if item.get("name") == name:
            return item
    return None


def protect_from_ruleset(item: dict[str, Any]) -> list[str]:
    conditions = item.get("conditions") or {}
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else {}
    include = ref_name.get("include") if isinstance(ref_name, dict) else None
    if not isinstance(include, list):
        return []
    out: list[str] = []
    for raw in include:
        if not isinstance(raw, str):
            continue
        if raw.startswith("refs/heads/"):
            out.append(raw[len("refs/heads/") :])
        else:
            out.append(raw)
    return out


class GitHubClient:
    def __init__(
        self,
        token: str,
        *,
        urlopen: UrlOpen | None = None,
        base_url: str = DEFAULT_API,
    ) -> None:
        self.token = token
        self.urlopen = urlopen or default_urlopen
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "forge",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.urlopen(req, timeout=30) as resp:
                raw = resp.read() or b""
                status = int(getattr(resp, "status", 200) or 200)
        except ForgeError:
            raise
        except urllib.error.HTTPError as exc:
            raw = exc.read() or b""
            message = _api_message(raw, fallback=str(exc.reason or exc))
            if exc.code in (401, 403):
                raise ForgeError(EXIT_AUTH, f"GitHub auth failed ({exc.code}): {message}") from exc
            raise ForgeError(EXIT_API, f"GitHub API {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ForgeError(EXIT_API, f"GitHub API network error: {exc.reason}") from exc
        if status >= 400:
            raise ForgeError(EXIT_API, f"GitHub API {status}: {_api_message(raw)}")
        if not raw.strip():
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ForgeError(EXIT_API, f"GitHub API returned non-JSON: {exc}") from exc

    def list_rulesets(self, owner: str, repo: str) -> list[dict[str, Any]]:
        payload = self.request("GET", f"/repos/{owner}/{repo}/rulesets?per_page=100")
        return _as_ruleset_list(payload)

    def get_ruleset(self, owner: str, repo: str, ruleset_id: int) -> dict[str, Any]:
        payload = self.request("GET", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}")
        if not isinstance(payload, dict):
            raise ForgeError(EXIT_API, "GitHub API returned a non-object ruleset")
        return payload

    def create_ruleset(self, owner: str, repo: str, payload: dict[str, Any]) -> dict[str, Any]:
        created = self.request("POST", f"/repos/{owner}/{repo}/rulesets", payload)
        if not isinstance(created, dict):
            raise ForgeError(EXIT_API, "GitHub API returned a non-object create result")
        return created

    def update_ruleset(
        self, owner: str, repo: str, ruleset_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        updated = self.request("PUT", f"/repos/{owner}/{repo}/rulesets/{ruleset_id}", payload)
        if not isinstance(updated, dict):
            raise ForgeError(EXIT_API, "GitHub API returned a non-object update result")
        return updated


def _api_message(raw: bytes, fallback: str = "") -> str:
    if not raw:
        return fallback or "empty error body"
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        text = raw.decode("utf-8", errors="replace").strip()
        return text or fallback or "unknown error"
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return fallback or "unknown error"


def _print_copy_note(stdout: Any) -> None:
    print(COPY_FILES_NOTE, file=stdout)


def run_apply(
    *,
    repo: str,
    path: Path | str | None = None,
    dry_run: bool = False,
    token: str | None = None,
    urlopen: UrlOpen | None = None,
    base_url: str = DEFAULT_API,
    stdout: Any = None,
    stderr: Any = None,
    environ: dict[str, str] | os._Environ[str] | None = None,
) -> int:
    import sys

    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        owner, name = parse_repo(repo)
        assert_apply_allowed(owner, name)
        config_path = None if path is None else Path(path)
        config = load_config(config_path)
        payload = build_payload(config)
        if dry_run:
            print("dry-run", file=out)
            print(json.dumps(payload, indent=2), file=out)
            print(f"protect: {', '.join(config.protect)}", file=out)
            _print_copy_note(out)
            return EXIT_OK
        resolved = token if token is not None else resolve_token(environ)
        if not resolved:
            print("missing FORGE_GITHUB_TOKEN or GITHUB_TOKEN", file=err)
            return EXIT_AUTH
        client = GitHubClient(resolved, urlopen=urlopen, base_url=base_url)
        existing = find_named_ruleset(client.list_rulesets(owner, name))
        if existing and existing.get("id") is not None:
            result = client.update_ruleset(owner, name, int(existing["id"]), payload)
            action = "updated"
        else:
            result = client.create_ruleset(owner, name, payload)
            action = "created"
        ruleset_id = result.get("id", existing.get("id") if existing else "?")
        print(f"{action} ruleset id={ruleset_id} name={RULESET_NAME}", file=out)
        print(f"protect: {', '.join(config.protect)}", file=out)
        _print_copy_note(out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
