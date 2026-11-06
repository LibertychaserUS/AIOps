"""forge.yaml model and loader: ForgeConfig, strict PyYAML parse, key whitelists.

Moved out of forge/apply.py unchanged (ADR 0009). apply.py re-exports every
name here so existing ``from forge.apply import ...`` sites keep working.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from forge import EXIT_CONFIG, SCHEMA_ID
from forge.title import SCOPE_RE, SCOPE_SHAPE

REPO_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
BRANCH_RE = re.compile(r"^(?:refs/heads/)?([A-Za-z0-9._][A-Za-z0-9._/-]*)$")
DEFAULT_PROTECT = ("main",)
DEFAULT_PREFIXES = ("cursor/", "copilot/")
DEFAULT_DENY = (".github/workflows/ci.yml",)
DEFAULT_TAG_PATTERNS = ("overlay-v*", "forge-v*")
# GitHub Actions app id: a required check must come from Actions, not from a
# commit status anyone with write access can POST under the same name.
DEFAULT_CHECKS_APP_ID = 15368
DEFAULT_MERGE_METHODS = ("squash",)
ALLOWED_MERGE_METHODS = ("merge", "squash", "rebase")
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
