"""Install or update the default Forge ruleset. Does not write repo files."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from forge import (
    COPY_FILES_NOTE,
    EXIT_API,
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_OK,
    FORBIDDEN_REPOS,
    RULESET_JSON,
    TAG_RULESET_NAME,
    branch_ruleset_name,
)

# forge.yaml model and loader live in forge/config.py (ADR 0009). Re-exported
# under their old names so `from forge.apply import ...` keeps working.
from forge.config import ALLOWED_MERGE_METHODS as ALLOWED_MERGE_METHODS
from forge.config import BRANCH_RE as BRANCH_RE
from forge.config import CI_KEYS as CI_KEYS
from forge.config import CODEOWNERS_LOCATIONS as CODEOWNERS_LOCATIONS
from forge.config import DEFAULT_CHECKS_APP_ID as DEFAULT_CHECKS_APP_ID
from forge.config import DEFAULT_DENY as DEFAULT_DENY
from forge.config import DEFAULT_MERGE_METHODS as DEFAULT_MERGE_METHODS
from forge.config import DEFAULT_PREFIXES as DEFAULT_PREFIXES
from forge.config import DEFAULT_PROTECT as DEFAULT_PROTECT
from forge.config import DEFAULT_TAG_PATTERNS as DEFAULT_TAG_PATTERNS
from forge.config import KNOWN_BRANCH_KEYS as KNOWN_BRANCH_KEYS
from forge.config import KNOWN_REVIEW_KEYS as KNOWN_REVIEW_KEYS
from forge.config import KNOWN_TAG_RULES_KEYS as KNOWN_TAG_RULES_KEYS
from forge.config import KNOWN_TOP_LEVEL_KEYS as KNOWN_TOP_LEVEL_KEYS
from forge.config import REPO_RE as REPO_RE
from forge.config import BranchRule as BranchRule
from forge.config import DocsSyncRule as DocsSyncRule
from forge.config import ForgeConfig as ForgeConfig
from forge.config import ForgeError as ForgeError
from forge.config import _check_ci_keys as _check_ci_keys
from forge.config import _StrictLoader as _StrictLoader
from forge.config import _YamlError as _YamlError
from forge.config import codeowners_exists as codeowners_exists
from forge.config import config_warnings as config_warnings
from forge.config import load_config as load_config
from forge.config import normalize_branch as normalize_branch
from forge.config import normalize_repo_entry as normalize_repo_entry
from forge.config import parse_simple_yaml as parse_simple_yaml
from forge.config import validate_config as validate_config

UrlOpen = Callable[..., Any]

DEFAULT_API = "https://api.github.com"
# Repository admin role: the only bypass actor forge ever writes (tag creation).
ADMIN_BYPASS_ACTOR = {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}


def assert_not_production_host(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("ilovelearningguide.com") or host == "ilovelearningguide.com":
        raise ForgeError(EXIT_API, "refusing production host")


def safe_redirect(req: urllib.request.Request, new: urllib.request.Request) -> urllib.request.Request:
    """The request urllib would follow, after Forge's redirect rules.

    https never downgrades to http (the token would travel in clear), the
    production-host guard applies to the target as it did to the first URL,
    and the bearer token stays on the host it was issued for.
    """
    old_url = urlparse(req.full_url)
    new_url = urlparse(new.full_url)
    if old_url.scheme == "https" and new_url.scheme != "https":
        raise ForgeError(EXIT_API, f"refusing redirect from https to {new_url.scheme or '?'}: {new.full_url}")
    assert_not_production_host(new.full_url)
    if (old_url.hostname or "").lower() != (new_url.hostname or "").lower():
        new.remove_header("Authorization")
    return new


class ForgeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        return safe_redirect(req, new)


def default_urlopen(req: urllib.request.Request, timeout: int = 30) -> Any:
    url = req.full_url if hasattr(req, "full_url") else str(req)
    assert_not_production_host(url)
    return urllib.request.build_opener(ForgeRedirectHandler).open(req, timeout=timeout)


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


def assert_live_repo_allowed(
    owner: str,
    name: str,
    forbidden: Sequence[str] | None = None,
    *,
    action: str = "apply",
) -> None:
    """Refuse forge.yaml.forbidden_live_repos, the built-in FORBIDDEN_REPOS, and the LG hostname.

    The built-in list applies whatever config was loaded (target's own forge.yaml, or none).
    """
    key = f"{owner}/{name}".lower()
    listed = {normalize_repo_entry(item) for item in (forbidden or ()) if isinstance(item, str)}
    listed.update(item.lower() for item in FORBIDDEN_REPOS)
    if key in listed:
        raise ForgeError(EXIT_CONFIG, f"refusing to {action} to {owner}/{name}")
    if "ilovelearningguide" in key:
        raise ForgeError(EXIT_CONFIG, f"refusing to {action} to {owner}/{name}")


def assert_apply_allowed(
    owner: str,
    name: str,
    forbidden: Sequence[str] | None = None,
) -> None:
    """Live Ruleset apply: refuses forge.yaml.forbidden_live_repos."""
    assert_live_repo_allowed(owner, name, forbidden, action="apply")


def assert_submit_allowed(owner: str, name: str) -> None:
    """Dev submit: refuses upstream only; developers do open draft PRs on the fork."""
    key = f"{owner}/{name}".lower()
    if key in FORBIDDEN_REPOS:
        raise ForgeError(EXIT_CONFIG, f"refusing to submit to {owner}/{name}")
    if "ilovelearningguide" in key:
        raise ForgeError(EXIT_CONFIG, f"refusing to submit to {owner}/{name}")


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


def build_branch_payload(config: ForgeConfig, branch: str) -> dict[str, Any]:
    rule = config.rule_for(branch)
    payload = json.loads(json.dumps(load_ruleset_template()))
    payload["name"] = branch_ruleset_name(branch)
    payload["target"] = "branch"
    payload["enforcement"] = payload.get("enforcement") or "active"
    payload["bypass_actors"] = []
    payload["conditions"] = {
        "ref_name": {
            "include": [f"refs/heads/{branch}"],
            "exclude": [],
        }
    }
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise ForgeError(EXIT_CONFIG, "illegal ruleset template: rules must be a list")
    found_pr = False
    for item in rules:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "pull_request":
            found_pr = True
            params = item.setdefault("parameters", {})
            if not isinstance(params, dict):
                raise ForgeError(EXIT_CONFIG, "illegal pull_request parameters")
            params["required_approving_review_count"] = rule.approvals
            params["require_code_owner_review"] = rule.code_owners
            params["dismiss_stale_reviews_on_push"] = True
            params["require_last_push_approval"] = rule.last_push_required()
            params["allowed_merge_methods"] = list(rule.merge_methods)
            params["required_review_thread_resolution"] = rule.resolve_threads
    if not found_pr:
        raise ForgeError(EXIT_CONFIG, "ruleset template is missing pull_request")
    # No checks: omit the rule (an empty contexts list is a no-op GitHub may reject).
    rules[:] = [
        item
        for item in rules
        if not (isinstance(item, dict) and item.get("type") == "required_status_checks")
    ]
    if rule.required_checks:
        checks: list[dict[str, Any]] = []
        for name in rule.required_checks:
            check: dict[str, Any] = {"context": name}
            if config.checks_app_id is not None:
                check["integration_id"] = config.checks_app_id
            checks.append(check)
        rules.append(
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "required_status_checks": checks,
                },
            }
        )
    types = {item.get("type") for item in payload["rules"] if isinstance(item, dict)}
    if "deletion" not in types or "non_fast_forward" not in types:
        raise ForgeError(EXIT_CONFIG, "ruleset template is missing deletion/non_fast_forward")
    return payload


def build_tag_payload(config: ForgeConfig) -> dict[str, Any]:
    includes = [f"refs/tags/{pattern}" for pattern in config.tag_patterns]
    rules: list[dict[str, Any]] = [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "update"},
    ]
    bypass: list[dict[str, Any]] = []
    if config.tag_creation:
        # Opt-in (ADR 0008, proposal): only repository admins may create release tags,
        # so `forge release` keeps working for them.
        rules.append({"type": "creation"})
        bypass.append(dict(ADMIN_BYPASS_ACTOR))
    return {
        "name": TAG_RULESET_NAME,
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": bypass,
        "conditions": {"ref_name": {"include": includes, "exclude": []}},
        "rules": rules,
    }


def build_payloads(config: ForgeConfig) -> list[dict[str, Any]]:
    return [build_branch_payload(config, branch) for branch in config.protect] + [
        build_tag_payload(config)
    ]


def build_payload(config: ForgeConfig, template: dict[str, Any] | None = None) -> dict[str, Any]:
    """First protected-branch payload. Prefer build_payloads()."""
    del template
    branch = config.protect[0] if config.protect else DEFAULT_PROTECT[0]
    return build_branch_payload(config, branch)


def expected_ruleset_names(config: ForgeConfig) -> list[str]:
    return [branch_ruleset_name(branch) for branch in config.protect] + [TAG_RULESET_NAME]


def stale_ruleset_names(config: ForgeConfig, installed: Sequence[dict[str, Any]]) -> list[str]:
    """`forge-protected-*` rulesets on GitHub that no current protect branch owns.

    Reported only; neither apply nor status deletes them.
    """
    prefix = branch_ruleset_name("")
    expected = set(expected_ruleset_names(config))
    out: list[str] = []
    for item in installed:
        name = item.get("name")
        if isinstance(name, str) and name.startswith(prefix) and name not in expected:
            if name not in out:
                out.append(name)
    return out


RULESET_VOLATILE_KEYS = frozenset(
    {
        "id",
        "source",
        "source_type",
        "node_id",
        "created_at",
        "updated_at",
        "_links",
        "current_user_can_bypass",
    }
)


def _normalise_checks(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for check in raw if isinstance(raw, list) else []:
        if isinstance(check, dict):
            out.append({"context": check.get("context"), "integration_id": check.get("integration_id")})
        else:
            out.append({"context": check, "integration_id": None})
    out.sort(key=lambda row: (str(row["context"]), str(row["integration_id"])))
    return out


def _normalise_bypass(raw: Any) -> list[Any]:
    items = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    return sorted(items, key=lambda row: json.dumps(row, sort_keys=True, default=str))


def _normalise_conditions(raw: Any) -> dict[str, Any]:
    conditions = dict(raw) if isinstance(raw, dict) else {}
    ref_name = conditions.get("ref_name")
    ref = dict(ref_name) if isinstance(ref_name, dict) else {}
    for key in ("include", "exclude"):
        value = ref.get(key)
        ref[key] = sorted(str(item) for item in value) if isinstance(value, list) else []
    conditions["ref_name"] = ref
    return conditions


def ruleset_fingerprint(item: dict[str, Any]) -> dict[str, Any]:
    """Normalised ruleset for drift checks: GitHub ids/timestamps dropped, lists sorted.

    Enforcement, bypass actors, both ref_name lists and every rule parameter are kept.
    """
    out = {key: value for key, value in item.items() if key not in RULESET_VOLATILE_KEYS}
    out["target"] = item.get("target") or "branch"
    out["enforcement"] = item.get("enforcement")
    out["bypass_actors"] = _normalise_bypass(item.get("bypass_actors"))
    out["conditions"] = _normalise_conditions(item.get("conditions"))
    rules_out: list[dict[str, Any]] = []
    for rule in item.get("rules") or []:
        if not isinstance(rule, dict):
            rules_out.append({"type": None, "parameters": {"raw": rule}})
            continue
        params = dict(rule.get("parameters")) if isinstance(rule.get("parameters"), dict) else {}
        if rule.get("type") == "required_status_checks":
            params["required_status_checks"] = _normalise_checks(params.get("required_status_checks"))
        rules_out.append({"type": rule.get("type"), "parameters": params})
    rules_out.sort(key=lambda row: str(row.get("type")))
    out["rules"] = rules_out
    return out


def _params_match(expected: dict[str, Any], live: dict[str, Any]) -> bool:
    # GitHub echoes defaults for parameters Forge never sends; every parameter Forge
    # sends (allowed_merge_methods, require_last_push_approval, integration_id, ...)
    # must match exactly.
    return all(live.get(key) == value for key, value in expected.items())


def ruleset_matches(expected: dict[str, Any], installed: dict[str, Any]) -> bool:
    want = ruleset_fingerprint(expected)
    have = ruleset_fingerprint(installed)
    for key, value in want.items():
        if key == "rules":
            continue
        if have.get(key) != value:
            return False
    want_rules = want["rules"]
    have_rules = have["rules"]
    if [row["type"] for row in want_rules] != [row["type"] for row in have_rules]:
        return False
    return all(
        _params_match(left["parameters"], right["parameters"])
        for left, right in zip(want_rules, have_rules, strict=True)
    )


def classify_ruleset(
    expected: dict[str, Any], installed: dict[str, Any] | None
) -> str:
    if installed is None:
        return "missing"
    if not ruleset_matches(expected, installed):
        return "drifted"
    return "installed"


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


def find_named_ruleset(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
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


RETRY_TRIES = 3
RETRY_BACKOFF_S = (1.0, 2.0, 4.0)
RETRY_AFTER_CAP_S = 30.0
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD"})


class GitHubApiError(ForgeError):
    """A ForgeError that keeps the HTTP status, so callers can branch on 422 etc."""

    def __init__(self, code: int, message: str, *, status: int | None = None) -> None:
        super().__init__(code, message)
        self.status = status


def _header(headers: Any, name: str) -> str | None:
    if headers is None:
        return None
    try:
        value = headers.get(name)
        if value is None and hasattr(headers, "items"):
            wanted = name.lower()
            value = next((v for k, v in headers.items() if str(k).lower() == wanted), None)
    except (AttributeError, TypeError):
        return None
    return str(value) if value is not None else None


def _retry_after_seconds(headers: Any) -> float | None:
    raw = _header(headers, "Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    return max(0.0, min(seconds, RETRY_AFTER_CAP_S))


def retry_delay(method: str, status: int, headers: Any, attempt: int) -> float | None:
    """Seconds to wait before retrying, or None: never for writes, only 5xx / 429, bounded tries."""
    if method.upper() not in IDEMPOTENT_METHODS:
        return None
    if status != 429 and status < 500:
        return None
    if attempt >= RETRY_TRIES:
        return None
    retry_after = _retry_after_seconds(headers)
    if retry_after is not None:
        return retry_after
    return RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S)) - 1]


def is_rate_limited(status: int, headers: Any, raw: bytes) -> bool:
    if status == 429:
        return True
    if status != 403:
        return False
    if (_header(headers, "X-RateLimit-Remaining") or "").strip() == "0":
        return True
    text = raw.decode("utf-8", errors="replace").lower()
    return "rate limit" in text


def rate_limit_reset(headers: Any) -> str:
    raw = _header(headers, "X-RateLimit-Reset")
    try:
        when = datetime.fromtimestamp(int(str(raw).strip()), UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        retry_after = _header(headers, "Retry-After")
        return f"in {retry_after.strip()}s" if retry_after else "unknown"
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def http_error_to_forge(exc: urllib.error.HTTPError) -> GitHubApiError:
    raw = exc.read() or b""
    message = _api_message(raw, fallback=str(exc.reason or exc))
    headers = getattr(exc, "headers", None)
    if is_rate_limited(exc.code, headers, raw):
        return GitHubApiError(
            EXIT_API,
            f"GitHub rate limit hit ({exc.code}): {message}; resets at {rate_limit_reset(headers)}",
            status=exc.code,
        )
    if exc.code in (401, 403):
        return GitHubApiError(EXIT_AUTH, f"GitHub auth failed ({exc.code}): {message}", status=exc.code)
    return GitHubApiError(EXIT_API, f"GitHub API {exc.code}: {message}", status=exc.code)


class GitHubClient:
    def __init__(
        self,
        token: str,
        *,
        urlopen: UrlOpen | None = None,
        base_url: str = DEFAULT_API,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.token = token
        self.urlopen = urlopen or default_urlopen
        self.base_url = base_url.rstrip("/")
        # Injected by tests; the backoff waits are real in production.
        self.sleep = sleep or time.sleep

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        not_found_ok: bool = False,
    ) -> Any:
        payload, _ = self._send(method, path, body, not_found_ok=not_found_ok)
        return payload

    def _send(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        not_found_ok: bool = False,
    ) -> tuple[Any, Any]:
        if path.startswith(self.base_url + "/"):
            url = path
        elif path.startswith("/"):
            url = f"{self.base_url}{path}"
        else:
            raise ForgeError(EXIT_API, f"refusing to follow off-API URL: {path}")
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "forge",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        attempt = 0
        while True:
            attempt += 1
            # A fresh Request per try: urllib may mutate one it has sent.
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with self.urlopen(req, timeout=30) as resp:
                    raw = resp.read() or b""
                    status = int(getattr(resp, "status", 200) or 200)
                    resp_headers = getattr(resp, "headers", None)
                break
            except ForgeError:
                raise
            except urllib.error.HTTPError as exc:
                if not_found_ok and exc.code == 404:
                    return None, None
                delay = retry_delay(method, exc.code, getattr(exc, "headers", None), attempt)
                if delay is not None:
                    self.sleep(delay)
                    continue
                raise http_error_to_forge(exc) from exc
            except urllib.error.URLError as exc:
                raise GitHubApiError(EXIT_API, f"GitHub API network error: {exc.reason}") from exc
        if status >= 400:
            raise GitHubApiError(EXIT_API, f"GitHub API {status}: {_api_message(raw)}", status=status)
        if not raw.strip():
            return None, resp_headers
        try:
            return json.loads(raw.decode("utf-8")), resp_headers
        except json.JSONDecodeError as exc:
            raise ForgeError(EXIT_API, f"GitHub API returned non-JSON: {exc}") from exc

    def list_rulesets(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """This repo's own rulesets, every page. Org / parent rulesets are not ours to match."""
        out: list[dict[str, Any]] = []
        path: str | None = f"/repos/{owner}/{repo}/rulesets?per_page=100&includes_parents=false"
        seen: set[str] = set()
        while path is not None:
            if path in seen or len(seen) >= MAX_RULESET_PAGES:
                raise ForgeError(EXIT_API, "ruleset pagination did not terminate")
            seen.add(path)
            payload, headers = self._send("GET", path)
            out.extend(
                item
                for item in _as_ruleset_list(payload)
                if item.get("source_type", "Repository") == "Repository"
            )
            path = _next_link(headers)
        return out

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


MAX_RULESET_PAGES = 50
LINK_NEXT_RE = re.compile(r'<([^>]+)>\s*;\s*rel="?next"?')


def _next_link(headers: Any) -> str | None:
    if headers is None:
        return None
    try:
        value = headers.get("Link") or headers.get("link")
    except AttributeError:
        return None
    if not isinstance(value, str):
        return None
    for part in value.split(","):
        match = LINK_NEXT_RE.search(part)
        if match:
            return match.group(1).strip()
    return None


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
        config_path = None if path is None else Path(path)
        config = load_config(config_path)
        assert_apply_allowed(owner, name, config.forbidden_live_repos)
        payloads = build_payloads(config)
        # The target repo root is where its forge.yaml lives (cwd without --path).
        root = Path(".") if config_path is None else config_path.resolve().parent
        for line in config_warnings(config, root):
            print(line, file=err)
        if dry_run:
            print("dry-run", file=out)
            print(json.dumps(payloads, indent=2), file=out)
            print(f"protect: {', '.join(config.protect)}", file=out)
            _print_copy_note(out)
            return EXIT_OK
        resolved = token if token is not None else resolve_token(environ)
        if not resolved:
            print("missing FORGE_GITHUB_TOKEN or GITHUB_TOKEN", file=err)
            return EXIT_AUTH
        client = GitHubClient(resolved, urlopen=urlopen, base_url=base_url)
        existing_list = client.list_rulesets(owner, name)
        for payload in payloads:
            existing = find_named_ruleset(existing_list, str(payload["name"]))
            if existing and existing.get("id") is not None:
                result = client.update_ruleset(owner, name, int(existing["id"]), payload)
                action = "updated"
            else:
                try:
                    result = client.create_ruleset(owner, name, payload)
                    action = "created"
                except GitHubApiError as exc:
                    # 422 on POST: a ruleset with this name already exists (created by
                    # someone else since we listed). Look it up again and PUT by id.
                    if exc.status != 422:
                        raise
                    again = find_named_ruleset(client.list_rulesets(owner, name), str(payload["name"]))
                    if again is None or again.get("id") is None:
                        raise
                    existing = again
                    result = client.update_ruleset(owner, name, int(again["id"]), payload)
                    action = "updated"
                else:
                    existing_list.append(result)
            ruleset_id = result.get("id", existing.get("id") if existing else "?")
            print(f"{action} ruleset id={ruleset_id} name={payload['name']}", file=out)
        for stale in stale_ruleset_names(config, existing_list):
            print(f"stale ruleset name={stale} (not in protect; not deleted)", file=out)
        print(f"protect: {', '.join(config.protect)}", file=out)
        _print_copy_note(out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
