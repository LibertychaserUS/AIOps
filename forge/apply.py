"""Install or update the default Forge ruleset. Does not write repo files."""

from __future__ import annotations

import difflib
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
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
    SCHEMA_ID,
    TAG_RULESET_NAME,
    branch_ruleset_name,
)

UrlOpen = Callable[..., Any]

REPO_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
BRANCH_RE = re.compile(r"^(?:refs/heads/)?([A-Za-z0-9._][A-Za-z0-9._/-]*)$")
DEFAULT_API = "https://api.github.com"
DEFAULT_PROTECT = ("main",)
DEFAULT_PREFIXES = ("cursor/", "copilot/")
DEFAULT_DENY = (".github/workflows/ci.yml",)
DEFAULT_TAG_PATTERNS = ("overlay-v*", "forge-v*")
KNOWN_TOP_LEVEL_KEYS = (
    "schema",
    "protect",
    "agent_branch_prefixes",
    "deny_paths",
    "required_checks",
    "review",
    "ci",
    "branches",
    "title",
    "docs_sync",
    "forbidden_live_repos",
    "tag_patterns",
)


class ForgeError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class BranchRule:
    name: str
    required_checks: list[str] = field(default_factory=list)
    approvals: int = 1
    code_owners: bool = False
    promote_from: str | None = None


@dataclass(frozen=True)
class DocsSyncRule:
    paths: list[str]
    require: list[str]


@dataclass
class ForgeConfig:
    schema: str = SCHEMA_ID
    protect: list[str] = field(default_factory=lambda: list(DEFAULT_PROTECT))
    agent_branch_prefixes: list[str] = field(default_factory=lambda: list(DEFAULT_PREFIXES))
    deny_paths: list[str] = field(default_factory=lambda: list(DEFAULT_DENY))
    required_checks: list[str] = field(default_factory=list)
    min_approvals: int = 1
    code_owners: bool = False
    branches: dict[str, BranchRule] = field(default_factory=dict)
    title_scopes: str | list[str] | None = None
    docs_sync: list[DocsSyncRule] = field(default_factory=list)
    forbidden_live_repos: list[str] = field(default_factory=list)
    tag_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_TAG_PATTERNS))

    def rule_for(self, branch: str) -> BranchRule:
        found = self.branches.get(branch)
        if found is not None:
            return found
        return BranchRule(
            name=branch,
            required_checks=list(self.required_checks),
            approvals=self.min_approvals,
            code_owners=self.code_owners,
        )


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


def normalize_repo_entry(entry: str) -> str:
    """`https://github.com/O/N.git` / `github.com/O/N/` / `O/N` -> `o/n` (no validation)."""
    text = entry.strip()
    lowered = text.lower()
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.rstrip("/")
    if text.lower().endswith(".git"):
        text = text[: -len(".git")]
    return text.rstrip("/").lower()


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
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",") if part.strip()]
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
        if key in result:
            raise _YamlError(f"line {lineno}: duplicate key {key}")
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
            if ":" in rest and not rest.startswith("[") and not rest.startswith("'") and not rest.startswith('"'):
                mapping, i = _parse_list_mapping_item(rows, i, indent, rest)
                result.append(mapping)
                continue
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


def _parse_list_mapping_item(
    rows: list[tuple[int, int, str]], i: int, indent: int, rest: str
) -> tuple[dict[str, Any], int]:
    """Parse `- key: value` plus sibling keys indented further than the dash."""
    key, _, value = rest.partition(":")
    key = key.strip()
    value = value.strip()
    mapping: dict[str, Any] = {}
    _, ind, _ = rows[i]
    if value:
        mapping[key] = _parse_scalar(value)
        i += 1
    elif i + 1 < len(rows) and rows[i + 1][1] > ind:
        child, i = _parse_block(rows, i + 1, rows[i + 1][1])
        mapping[key] = child
    else:
        mapping[key] = None
        i += 1
    while i < len(rows):
        lineno2, ind2, content2 = rows[i]
        if ind2 <= indent:
            break
        if content2.startswith("- ") or content2 == "-":
            break
        if ":" not in content2:
            raise _YamlError(f"line {lineno2}: expected key:")
        k, _, r = content2.partition(":")
        k, r = k.strip(), r.strip()
        if not k:
            raise _YamlError(f"line {lineno2}: empty key")
        if k in mapping:
            raise _YamlError(f"line {lineno2}: duplicate key {k}")
        if r:
            mapping[k] = _parse_scalar(r)
            i += 1
            continue
        if i + 1 >= len(rows) or rows[i + 1][1] <= ind2:
            mapping[k] = None
            i += 1
            continue
        child, i = _parse_block(rows, i + 1, rows[i + 1][1])
        mapping[k] = child
    return mapping, i


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
        if ".." in item.replace("\\", "/").split("/"):
            raise ForgeError(EXIT_CONFIG, f"illegal {field} item: {item!r}")
        out.append(item)
    return out


def normalize_branch(name: str) -> str:
    match = BRANCH_RE.fullmatch(name.strip())
    if not match or ".." in name:
        raise ForgeError(EXIT_CONFIG, f"illegal branch: {name!r}")
    return match.group(1)


KNOWN_BRANCH_KEYS = ("required_checks", "approvals", "code_owners", "promote_from")
KNOWN_REVIEW_KEYS = ("min_approvals", "code_owners")


def _unknown_key_message(
    key: str, known: Sequence[str] = KNOWN_TOP_LEVEL_KEYS, prefix: str = ""
) -> str:
    suggestions = difflib.get_close_matches(key, known, n=1, cutoff=0.5)
    if suggestions:
        return f"unknown key {prefix}{key}; did you mean {prefix}{suggestions[0]}"
    return f"unknown key {prefix}{key}"


def _reject_unknown_keys(raw: dict[str, Any], known: Sequence[str], prefix: str) -> None:
    for key in raw:
        if key not in known:
            raise ForgeError(EXIT_CONFIG, _unknown_key_message(str(key), known, prefix))


CI_KEYS: dict[str, tuple[str, ...]] = {
    "ci": ("common", "products", "select"),
    "ci.products.*": ("check", "paths"),
    "ci.select": ("title",),
}


def _check_ci_keys(raw: Any) -> None:
    """Unknown keys under ci would silently drop a gate; refuse them (exit 3)."""

    def _refuse(where: str, data: Any, known: tuple[str, ...]) -> None:
        if not isinstance(data, dict):
            return
        for key in data:
            if key in known:
                continue
            hint = difflib.get_close_matches(str(key), known, n=1, cutoff=0.5)
            tail = f"; did you mean {hint[0]}" if hint else ""
            raise ForgeError(EXIT_CONFIG, f"unknown key {where}.{key}{tail}")

    _refuse("ci", raw, CI_KEYS["ci"])
    if not isinstance(raw, dict):
        return
    products = raw.get("products")
    if isinstance(products, dict):
        for name, spec in products.items():
            _refuse(f"ci.products.{name}", spec, CI_KEYS["ci.products.*"])
    _refuse("ci.select", raw.get("select"), CI_KEYS["ci.select"])


def _parse_title_scopes(raw: Any) -> str | list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ForgeError(EXIT_CONFIG, "illegal title: expected a mapping")
    if "scopes" not in raw:
        return None
    scopes = raw["scopes"]
    if isinstance(scopes, str):
        if scopes != "any":
            raise ForgeError(EXIT_CONFIG, f"illegal title.scopes: {scopes!r} (any | list)")
        return "any"
    return _string_list(scopes, "title.scopes", allow_empty=False)


def _parse_docs_sync(raw: Any) -> list[DocsSyncRule]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ForgeError(EXIT_CONFIG, "illegal docs_sync: expected a list")
    out: list[DocsSyncRule] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ForgeError(EXIT_CONFIG, "illegal docs_sync item: expected a mapping")
        paths = _string_list(item.get("paths"), "docs_sync.paths", allow_empty=False)
        require = _string_list(item.get("require"), "docs_sync.require", allow_empty=False)
        out.append(DocsSyncRule(paths=paths, require=require))
    return out


def _parse_branch_rule(
    name: str,
    raw: Any,
    *,
    fallback_checks: list[str],
    fallback_approvals: int,
    fallback_owners: bool,
) -> BranchRule:
    if not isinstance(raw, dict):
        raise ForgeError(EXIT_CONFIG, f"illegal branches.{name}: expected a mapping")
    _reject_unknown_keys(raw, KNOWN_BRANCH_KEYS, f"branches.{name}.")
    if "required_checks" in raw:
        checks = _string_list(raw["required_checks"], f"branches.{name}.required_checks", allow_empty=True)
    else:
        checks = list(fallback_checks)
    approvals = raw.get("approvals", fallback_approvals)
    if isinstance(approvals, bool) or not isinstance(approvals, int) or approvals < 0:
        raise ForgeError(EXIT_CONFIG, f"illegal branches.{name}.approvals: {approvals!r}")
    code_owners = raw.get("code_owners", fallback_owners)
    if not isinstance(code_owners, bool):
        raise ForgeError(EXIT_CONFIG, f"illegal branches.{name}.code_owners: {code_owners!r}")
    promote_from = raw.get("promote_from")
    if promote_from is None:
        promote = None
    elif isinstance(promote_from, str) and promote_from.strip():
        promote = normalize_branch(promote_from)
    else:
        raise ForgeError(EXIT_CONFIG, f"illegal branches.{name}.promote_from: {promote_from!r}")
    return BranchRule(
        name=name,
        required_checks=checks,
        approvals=approvals,
        code_owners=code_owners,
        promote_from=promote,
    )


def validate_config(raw: dict[str, Any]) -> ForgeConfig:
    schema = raw.get("schema", SCHEMA_ID)
    if schema != SCHEMA_ID:
        raise ForgeError(EXIT_CONFIG, f"illegal schema: {schema!r}")

    for key in raw:
        if key not in KNOWN_TOP_LEVEL_KEYS:
            raise ForgeError(EXIT_CONFIG, _unknown_key_message(str(key)))
    _check_ci_keys(raw.get("ci"))

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
    _reject_unknown_keys(review, KNOWN_REVIEW_KEYS, "review.")

    min_approvals = review.get("min_approvals", 1)
    if isinstance(min_approvals, bool) or not isinstance(min_approvals, int) or min_approvals < 0:
        raise ForgeError(EXIT_CONFIG, f"illegal review.min_approvals: {min_approvals!r}")

    code_owners = review.get("code_owners", False)
    if not isinstance(code_owners, bool):
        raise ForgeError(EXIT_CONFIG, f"illegal review.code_owners: {code_owners!r}")

    branches_raw = raw.get("branches")
    branches: dict[str, BranchRule] = {}
    if branches_raw is not None:
        if not isinstance(branches_raw, dict):
            raise ForgeError(EXIT_CONFIG, "illegal branches: expected a mapping")
        for name, item in branches_raw.items():
            branch = normalize_branch(str(name))
            if branch not in protect:
                raise ForgeError(
                    EXIT_CONFIG,
                    f"illegal branches.{branch}: not in protect ({', '.join(protect)})",
                )
            branches[branch] = _parse_branch_rule(
                branch,
                item,
                fallback_checks=required_checks,
                fallback_approvals=min_approvals,
                fallback_owners=code_owners,
            )
        for branch, rule in branches.items():
            if rule.promote_from is not None and rule.promote_from not in protect:
                raise ForgeError(
                    EXIT_CONFIG,
                    f"illegal branches.{branch}.promote_from: {rule.promote_from} is not in protect",
                )
            if rule.promote_from == branch:
                raise ForgeError(
                    EXIT_CONFIG, f"illegal branches.{branch}.promote_from: cannot promote from itself"
                )

    if "tag_patterns" in raw:
        tag_patterns = _string_list(raw["tag_patterns"], "tag_patterns", allow_empty=False)
    else:
        tag_patterns = list(DEFAULT_TAG_PATTERNS)

    if "forbidden_live_repos" in raw:
        forbidden = []
        for item in _string_list(
            raw["forbidden_live_repos"], "forbidden_live_repos", allow_empty=True
        ):
            entry = normalize_repo_entry(item)
            if not REPO_RE.fullmatch(entry):
                raise ForgeError(
                    EXIT_CONFIG, f"illegal forbidden_live_repos item: {item!r} (use OWNER/NAME)"
                )
            forbidden.append(entry)
    else:
        forbidden = []

    return ForgeConfig(
        schema=SCHEMA_ID,
        protect=protect,
        agent_branch_prefixes=prefixes,
        deny_paths=deny_paths,
        required_checks=required_checks,
        min_approvals=min_approvals,
        code_owners=code_owners,
        branches=branches,
        title_scopes=_parse_title_scopes(raw.get("title")),
        docs_sync=_parse_docs_sync(raw.get("docs_sync")),
        forbidden_live_repos=forbidden,
        tag_patterns=tag_patterns,
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
            params.setdefault("require_last_push_approval", False)
    if not found_pr:
        raise ForgeError(EXIT_CONFIG, "ruleset template is missing pull_request")
    check_rule = {
        "type": "required_status_checks",
        "parameters": {
            "strict_required_status_checks_policy": True,
            "required_status_checks": [{"context": name} for name in rule.required_checks],
        },
    }
    replaced = False
    for index, item in enumerate(rules):
        if isinstance(item, dict) and item.get("type") == "required_status_checks":
            rules[index] = check_rule
            replaced = True
            break
    if not replaced:
        rules.append(check_rule)
    types = {item.get("type") for item in payload["rules"] if isinstance(item, dict)}
    if "deletion" not in types or "non_fast_forward" not in types:
        raise ForgeError(EXIT_CONFIG, "ruleset template is missing deletion/non_fast_forward")
    return payload


def build_tag_payload(config: ForgeConfig) -> dict[str, Any]:
    includes = [f"refs/tags/{pattern}" for pattern in config.tag_patterns]
    return {
        "name": TAG_RULESET_NAME,
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": includes, "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "update"},
        ],
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
    # GitHub echoes defaults for parameters Forge never sends (e.g. allowed_merge_methods);
    # every parameter Forge sends must match exactly.
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
        print(f"protect: {', '.join(config.protect)}", file=out)
        _print_copy_note(out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
