"""Install or update the default Forge ruleset. Does not write repo files."""

from __future__ import annotations

import difflib
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

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
from forge.title import SCOPE_RE, SCOPE_SHAPE

UrlOpen = Callable[..., Any]

REPO_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
BRANCH_RE = re.compile(r"^(?:refs/heads/)?([A-Za-z0-9._][A-Za-z0-9._/-]*)$")
DEFAULT_API = "https://api.github.com"
DEFAULT_PROTECT = ("main",)
DEFAULT_PREFIXES = ("cursor/", "copilot/")
DEFAULT_DENY = (".github/workflows/ci.yml",)
DEFAULT_TAG_PATTERNS = ("overlay-v*", "forge-v*")
# GitHub Actions app id: a required check must come from Actions, not from a
# commit status anyone with write access can POST under the same name.
DEFAULT_CHECKS_APP_ID = 15368
DEFAULT_MERGE_METHODS = ("squash",)
ALLOWED_MERGE_METHODS = ("merge", "squash", "rebase")
# Repository admin role: the only bypass actor forge ever writes (tag creation).
ADMIN_BYPASS_ACTOR = {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
CODEOWNERS_LOCATIONS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
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
    "checks_app_id",
    "tag_rules",
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
    merge_methods: list[str] = field(default_factory=lambda: list(DEFAULT_MERGE_METHODS))
    # None = follow approvals (True when approvals >= 1); see last_push_required().
    last_push_approval: bool | None = None
    resolve_threads: bool = False

    def last_push_required(self) -> bool:
        if self.last_push_approval is None:
            return self.approvals >= 1
        return self.last_push_approval


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
    checks_app_id: int | None = DEFAULT_CHECKS_APP_ID
    tag_creation: bool = False

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


class _YamlError(ValueError):
    pass


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader for forge.yaml: duplicate keys are refused at every level.

    Plain scalars keep forge-config/v1 typing: ints and ``true`` / ``false``
    resolve, everything else stays a string. ``1.0``, ``2026-01-01``, ``yes``,
    ``on`` are branch / check / tag names here, not floats, dates or booleans.
    """

    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict[Any, Any]:
        if isinstance(node, yaml.MappingNode):
            seen: set[Any] = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=deep)
                try:
                    duplicate = key in seen
                except TypeError:
                    continue  # unhashable key: SafeLoader reports it below
                if duplicate:
                    raise _YamlError(f"line {key_node.start_mark.line + 1}: duplicate key {key}")
                seen.add(key)
        return super().construct_mapping(node, deep=deep)


_StrictLoader.yaml_implicit_resolvers = {
    first: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag
        not in {
            "tag:yaml.org,2002:bool",
            "tag:yaml.org,2002:float",
            "tag:yaml.org,2002:timestamp",
        }
    ]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_StrictLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse forge.yaml with PyYAML (safe loader, strict keys). Top level must be a mapping."""
    try:
        value = yaml.load(text, Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise _YamlError(" ".join(str(exc).split())) from exc
    if value is None:
        raise _YamlError("empty document")
    if not isinstance(value, dict):
        raise _YamlError("document must be a mapping")
    return value


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


KNOWN_BRANCH_KEYS = (
    "required_checks",
    "approvals",
    "code_owners",
    "promote_from",
    "merge_methods",
    "last_push_approval",
    "resolve_threads",
)
KNOWN_TAG_RULES_KEYS = ("creation",)
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
    entries = _string_list(scopes, "title.scopes", allow_empty=False)
    for entry in entries:
        # Adopter products / actors are allowed; the shape is not negotiable.
        if not SCOPE_RE.fullmatch(entry):
            raise ForgeError(
                EXIT_CONFIG, f"illegal title.scopes item: {entry!r} (use {SCOPE_SHAPE})"
            )
    return entries


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
    if "merge_methods" in raw:
        methods = _string_list(raw["merge_methods"], f"branches.{name}.merge_methods", allow_empty=False)
        for method in methods:
            if method not in ALLOWED_MERGE_METHODS:
                raise ForgeError(
                    EXIT_CONFIG,
                    f"illegal branches.{name}.merge_methods item: {method!r} "
                    f"({' | '.join(ALLOWED_MERGE_METHODS)})",
                )
    else:
        methods = list(DEFAULT_MERGE_METHODS)
    last_push = raw.get("last_push_approval")
    if last_push is not None and not isinstance(last_push, bool):
        raise ForgeError(EXIT_CONFIG, f"illegal branches.{name}.last_push_approval: {last_push!r}")
    resolve_threads = raw.get("resolve_threads", False)
    if not isinstance(resolve_threads, bool):
        raise ForgeError(EXIT_CONFIG, f"illegal branches.{name}.resolve_threads: {resolve_threads!r}")
    return BranchRule(
        name=name,
        required_checks=checks,
        approvals=approvals,
        code_owners=code_owners,
        promote_from=promote,
        merge_methods=methods,
        last_push_approval=last_push,
        resolve_threads=resolve_threads,
    )


def _parse_checks_app_id(raw: dict[str, Any]) -> int | None:
    """`checks_app_id: null` / `none` unbinds required checks from the Actions app."""
    if "checks_app_id" not in raw:
        return DEFAULT_CHECKS_APP_ID
    value = raw["checks_app_id"]
    if value is None or (isinstance(value, str) and value.strip().lower() in {"none", "null"}):
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ForgeError(EXIT_CONFIG, f"illegal checks_app_id: {value!r} (positive int | null)")
    return value


def _parse_tag_rules(raw: Any) -> bool:
    """tag_rules.creation (default false). Opt-in: ADR 0008 is a proposal."""
    if raw is None:
        return False
    if not isinstance(raw, dict):
        raise ForgeError(EXIT_CONFIG, "illegal tag_rules: expected a mapping")
    _reject_unknown_keys(raw, KNOWN_TAG_RULES_KEYS, "tag_rules.")
    creation = raw.get("creation", False)
    if not isinstance(creation, bool):
        raise ForgeError(EXIT_CONFIG, f"illegal tag_rules.creation: {creation!r}")
    return creation


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
        checks_app_id=_parse_checks_app_id(raw),
        tag_creation=_parse_tag_rules(raw.get("tag_rules")),
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


def codeowners_exists(root: Path) -> bool:
    return any((root / rel).is_file() for rel in CODEOWNERS_LOCATIONS)


def config_warnings(config: ForgeConfig, root: Path | None) -> list[str]:
    """Non-fatal: rules that install fine but cannot bite as written."""
    out: list[str] = []
    for branch in config.protect:
        rule = config.rule_for(branch)
        if not rule.required_checks:
            out.append(
                f"warning: branches.{branch}.required_checks is empty; "
                "no required_status_checks rule written"
            )
    if root is not None and any(config.rule_for(b).code_owners for b in config.protect):
        if not codeowners_exists(root):
            out.append(
                "warning: code_owners: true but no CODEOWNERS file "
                f"({', '.join(CODEOWNERS_LOCATIONS)}) under {root.as_posix()}"
            )
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
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.urlopen(req, timeout=30) as resp:
                raw = resp.read() or b""
                status = int(getattr(resp, "status", 200) or 200)
                headers = getattr(resp, "headers", None)
        except ForgeError:
            raise
        except urllib.error.HTTPError as exc:
            if not_found_ok and exc.code == 404:
                return None, None
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
            return None, headers
        try:
            return json.loads(raw.decode("utf-8")), headers
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
                result = client.create_ruleset(owner, name, payload)
                action = "created"
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
