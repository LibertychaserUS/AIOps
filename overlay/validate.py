"""Validate inbox + suite + optional trace. No model. Exit 2 on contract red."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, TextIO

import yaml

from overlay import EXIT_CONTRACT, EXIT_OK
from overlay.schemautil import validate as schema_validate

INBOX_FORBIDDEN_FIELDS = frozenset(
    {"status", "reviewed_by", "armed", "blocked", "product_command"}
)
FLOATING_REFS = frozenset({"main", "master", "HEAD", "latest"})
SUITE_STATUSES = frozenset({"draft", "blocked", "armed"})
SUITE_KINDS = frozenset({"functional", "regression"})
NEVER_RED_ALLOWED = frozenset({"draft", "blocked"})
KIND_LATER = "later"
INBOX_MAX_BYTES = 32 * 1024
INBOX_MAX_CHARS = 8000
INBOX_MIN_BODY_CHARS = 40
FUNCTION_ID_RE = re.compile(r"^\S+$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TOKEN_RE = re.compile(r"\S+")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
URL_IN_TEXT_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)


@dataclass
class Issue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class OverlayConfig:
    path: Path
    product_repo: str
    default_ref: str
    branches: dict[str, frozenset[str]]
    kinds: dict[str, str]
    never_red_statuses: frozenset[str]
    forbid_hosts: tuple[str, ...]


@dataclass
class InboxDoc:
    path: Path
    inbox_id: str
    kind: str
    body: str
    front: dict[str, Any]
    in_scope: str
    out_of_scope: str
    user_cases: str


@dataclass
class SuiteDoc:
    path: Path
    suite_id: str
    title: str
    status: str
    kind: str
    subject: str
    source: str
    reviewed_by: str | None
    reviewed_at: str | None
    blocked_reason: str | None
    armed_reason: str | None
    cases_path: Path
    cases_text: str
    function_ids: list[str]
    trace_items: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def schema_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "schema"


def load_json_schema(name: str) -> dict[str, Any]:
    path = schema_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"missing contract schema {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_yaml(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat() + "Z"
        return value.astimezone().isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): normalize_yaml(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_yaml(item) for item in value]
    return value


def load_yaml_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        raise ValueError("UTF-8 BOM is not allowed")
    loaded = yaml.safe_load(text)
    return normalize_yaml(loaded)


def split_front_matter(text: str, path: str, issues: list[Issue]) -> tuple[dict[str, Any] | None, str]:
    if text.startswith("\ufeff"):
        issues.append(Issue(path, "UTF-8 BOM is not allowed"))
        text = text.lstrip("\ufeff")
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", text, re.DOTALL)
    if match is None:
        issues.append(Issue(path, "expected a single YAML front-matter block"))
        return None, ""
    try:
        front = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        issues.append(Issue(path, f"front matter is not YAML: {exc}"))
        return None, match.group(2)
    front = normalize_yaml(front)
    if not isinstance(front, dict):
        issues.append(Issue(path, "front matter must be a mapping"))
        return None, match.group(2)
    return front, match.group(2)


def heading_sections(body: str) -> dict[str, str]:
    matches = list(HEADING_RE.finditer(body))
    found: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(2).strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        found[title] = body[start:end]
    return found


def compact_len(text: str) -> int:
    return len("".join(text.split()))


def token_in_text(text: str, token: str) -> bool:
    return re.search(rf"(?<!\S){re.escape(token)}(?!\S)", text) is not None


def parse_function_id(heading: str) -> str | None:
    parts = heading.split()
    if not parts:
        return None
    token = parts[0]
    if FUNCTION_ID_RE.fullmatch(token) is None:
        return None
    return token


def cases_function_ids(cases_text: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for match in H2_RE.finditer(cases_text):
        token = parse_function_id(match.group(1))
        if token is None:
            continue
        if token not in seen:
            ids.append(token)
            seen.add(token)
    return ids


def look_like_url(text: str) -> list[str]:
    return URL_IN_TEXT_RE.findall(text)


def forbid_host_url_hits(text: str, hosts: Iterable[str]) -> list[str]:
    lower = text.lower()
    hits: list[str] = []
    for host in hosts:
        host_l = host.lower().strip()
        if not host_l:
            continue
        needles = (
            f"https://{host_l}",
            f"http://{host_l}",
            f"https://www.{host_l}",
            f"http://www.{host_l}",
        )
        if any(needle in lower for needle in needles):
            hits.append(host)
    return hits


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def parse_iso8601(value: str) -> bool:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return False
    return True


def load_overlay_config(root: Path, issues: list[Issue]) -> OverlayConfig | None:
    path = root / "overlay.yaml"
    rel = _rel(root, path)
    if not path.is_file():
        issues.append(Issue(rel, "missing overlay.yaml"))
        return None
    try:
        data = load_yaml_file(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        issues.append(Issue(rel, f"cannot read overlay.yaml: {exc}"))
        return None
    if not isinstance(data, dict):
        issues.append(Issue(rel, "overlay.yaml must be a mapping"))
        return None
    if data.get("schema") != "overlay-config/v1":
        issues.append(Issue(rel, "schema must be overlay-config/v1"))

    product = data.get("product")
    repo = ""
    default_ref = ""
    if not isinstance(product, dict):
        issues.append(Issue(rel, "product must be a mapping"))
    else:
        repo = str(product.get("repo") or "").strip()
        default_ref = str(product.get("default_ref") or "").strip()
        if not repo or REPO_RE.fullmatch(repo) is None:
            issues.append(Issue(rel, "product.repo must be owner/name"))
        if not default_ref:
            issues.append(Issue(rel, "product.default_ref is required"))
        elif default_ref in FLOATING_REFS:
            issues.append(Issue(rel, "product.default_ref must be pinned (not main/master/HEAD/latest)"))

    branches: dict[str, frozenset[str]] = {}
    raw_branches = data.get("branches")
    if not isinstance(raw_branches, dict) or not raw_branches:
        issues.append(Issue(rel, "branches must be a non-empty mapping"))
    else:
        for name, spec in raw_branches.items():
            if not isinstance(spec, dict):
                issues.append(Issue(f"{rel}:branches.{name}", "must be a mapping with run:"))
                continue
            run = spec.get("run")
            if not isinstance(run, list) or not run:
                issues.append(Issue(f"{rel}:branches.{name}", "run must be a non-empty list"))
                continue
            bad = [item for item in run if item not in SUITE_KINDS]
            if bad:
                issues.append(Issue(f"{rel}:branches.{name}", f"illegal run kinds: {bad}"))
                continue
            branches[str(name)] = frozenset(str(item) for item in run)

    kinds: dict[str, str] = {}
    raw_kinds = data.get("kinds") or {}
    if raw_kinds is None:
        raw_kinds = {}
    if not isinstance(raw_kinds, dict):
        issues.append(Issue(rel, "kinds must be a mapping"))
    else:
        for name, value in raw_kinds.items():
            if value != KIND_LATER:
                issues.append(Issue(f"{rel}:kinds.{name}", "value must be later"))
                continue
            kinds[str(name)] = KIND_LATER

    never_red = data.get("never_red_statuses", ["draft", "blocked"])
    if never_red is None:
        never_red = ["draft", "blocked"]
    if not isinstance(never_red, list) or not all(isinstance(item, str) for item in never_red):
        issues.append(Issue(rel, "never_red_statuses must be a list of strings"))
        never_set: frozenset[str] = frozenset({"draft", "blocked"})
    else:
        never_set = frozenset(never_red)
        extra = never_set - NEVER_RED_ALLOWED
        if extra:
            issues.append(Issue(rel, f"never_red_statuses cannot include {sorted(extra)}"))

    hosts_raw = data.get("forbid_hosts") or []
    if hosts_raw is None:
        hosts_raw = []
    if not isinstance(hosts_raw, list) or not all(isinstance(item, str) for item in hosts_raw):
        issues.append(Issue(rel, "forbid_hosts must be a list of hosts"))
        hosts: tuple[str, ...] = ()
    else:
        hosts = tuple(item.strip() for item in hosts_raw if str(item).strip())

    if not branches or not repo or not default_ref or default_ref in FLOATING_REFS:
        return None
    never_ok = never_set & NEVER_RED_ALLOWED
    return OverlayConfig(
        path=path,
        product_repo=repo,
        default_ref=default_ref,
        branches=branches,
        kinds=kinds,
        never_red_statuses=never_ok or frozenset({"draft", "blocked"}),
        forbid_hosts=hosts,
    )


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def iter_inbox_paths(root: Path) -> list[Path]:
    folder = root / "inbox"
    if not folder.is_dir():
        return []
    found: list[Path] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix != ".md":
            continue
        if path.name.startswith(("_", ".")):
            continue
        found.append(path)
    return found


def iter_suite_paths(root: Path) -> list[Path]:
    folder = root / "suites"
    if not folder.is_dir():
        return []
    found: list[Path] = []
    for path in sorted(folder.iterdir()):
        if not path.is_dir() or path.name.startswith(("_", ".")):
            continue
        suite = path / "suite.yaml"
        if suite.is_file():
            found.append(suite)
    return found


def validate_inbox_file(
    root: Path,
    path: Path,
    config: OverlayConfig | None,
    inbox_schema: dict[str, Any],
    issues: list[Issue],
) -> InboxDoc | None:
    rel = _rel(root, path)
    raw = path.read_bytes()
    if len(raw) > INBOX_MAX_BYTES:
        issues.append(Issue(rel, f"larger than {INBOX_MAX_BYTES} bytes"))
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(Issue(rel, f"not UTF-8: {exc}"))
        return None
    front, body = split_front_matter(text, rel, issues)
    if front is None:
        return None
    for key in INBOX_FORBIDDEN_FIELDS:
        if key in front:
            issues.append(Issue(rel, f"inbox must not declare {key!r}"))
    for err in schema_validate(front, inbox_schema, "$"):
        issues.append(Issue(rel, err))
    inbox_id = str(front.get("id") or "")
    stem = path.stem
    if inbox_id and inbox_id != stem:
        issues.append(Issue(rel, f"id {inbox_id!r} must equal filename stem {stem!r}"))
    if len(body) > INBOX_MAX_CHARS:
        issues.append(Issue(rel, f"body longer than {INBOX_MAX_CHARS} characters"))
    if compact_len(body) < INBOX_MIN_BODY_CHARS:
        issues.append(Issue(rel, f"body must have at least {INBOX_MIN_BODY_CHARS} non-whitespace characters"))
    kind = str(front.get("kind") or "")
    if kind == "figma-ref":
        for url in look_like_url(body):
            if not url.lower().startswith("https://"):
                issues.append(Issue(rel, f"figma-ref links must be https:// ({url})"))
        for token in TOKEN_RE.findall(body):
            if token.startswith("http://"):
                issues.append(Issue(rel, f"figma-ref links must be https:// ({token})"))
    if config is not None:
        hits = forbid_host_url_hits(body, config.forbid_hosts)
        if hits:
            issues.append(Issue(rel, f"body contains a forbidden production URL for {hits}"))
    sections = heading_sections(body)
    doc = InboxDoc(
        path=path,
        inbox_id=inbox_id or stem,
        kind=kind,
        body=body,
        front=front,
        in_scope=sections.get("in scope", ""),
        out_of_scope=sections.get("out of scope", ""),
        user_cases=sections.get("user cases", ""),
    )
    return doc


def validate_suite_file(
    root: Path,
    path: Path,
    suite_schema: dict[str, Any],
    trace_schema: dict[str, Any],
    issues: list[Issue],
) -> SuiteDoc | None:
    rel = _rel(root, path)
    try:
        data = load_yaml_file(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        issues.append(Issue(rel, f"cannot read suite.yaml: {exc}"))
        return None
    if not isinstance(data, dict):
        issues.append(Issue(rel, "suite.yaml must be a mapping"))
        return None
    for err in schema_validate(data, suite_schema, "$"):
        issues.append(Issue(rel, err))

    suite_id = str(data.get("id") or "")
    dirname = path.parent.name
    if suite_id and suite_id != dirname:
        issues.append(Issue(rel, f"id {suite_id!r} must equal directory name {dirname!r}"))
    status = data.get("status")
    if status is not None and status not in SUITE_STATUSES:
        issues.append(Issue(rel, f"illegal status {status!r}"))
    source = str(data.get("source") or "")
    expected_source = f"inbox/{dirname}.md"
    if source and source != expected_source:
        issues.append(Issue(rel, f"source must be {expected_source}"))
    inbox_path = root / expected_source
    if source == expected_source and not inbox_path.is_file():
        issues.append(Issue(rel, f"source {expected_source} does not exist"))

    reviewed_by = data.get("reviewed_by")
    reviewed_at = data.get("reviewed_at")
    blocked_reason = data.get("blocked_reason")
    armed_reason = data.get("armed_reason")
    if isinstance(reviewed_by, str):
        reviewed_by = reviewed_by.strip() or None
    if isinstance(reviewed_at, str):
        reviewed_at = reviewed_at.strip() or None
    if isinstance(blocked_reason, str):
        blocked_reason = blocked_reason.strip() or None
    if isinstance(armed_reason, str):
        armed_reason = armed_reason.strip() or None

    if status in {"blocked", "armed"} and is_blank(reviewed_by):
        issues.append(Issue(rel, f"{status} requires non-empty reviewed_by"))
    if not is_blank(reviewed_by):
        if is_blank(reviewed_at):
            issues.append(Issue(rel, "reviewed_at is required when reviewed_by is set"))
        elif not parse_iso8601(str(reviewed_at)):
            issues.append(Issue(rel, "reviewed_at must be ISO-8601"))
    if status == "blocked" and is_blank(blocked_reason):
        issues.append(Issue(rel, "blocked requires blocked_reason"))
    if status == "armed" and is_blank(armed_reason):
        issues.append(Issue(rel, "armed requires armed_reason"))

    cases_path = path.parent / "cases.md"
    cases_rel = _rel(root, cases_path)
    if not cases_path.is_file():
        issues.append(Issue(cases_rel, "missing cases.md"))
        cases_text = ""
    else:
        cases_text = cases_path.read_text(encoding="utf-8")
        if cases_path.read_bytes().startswith(b"\xef\xbb\xbf"):
            issues.append(Issue(cases_rel, "UTF-8 BOM is not allowed"))
        if compact_len(cases_text) == 0:
            issues.append(Issue(cases_rel, "cases.md must be non-empty"))
        if "status: armed" in cases_text:
            issues.append(Issue(cases_rel, "must not put status: armed in the case body"))

    function_ids = cases_function_ids(cases_text)
    for heading in H2_RE.finditer(cases_text):
        token = parse_function_id(heading.group(1))
        if token is None:
            issues.append(Issue(cases_rel, f"## heading needs a non-empty function_id without whitespace: {heading.group(1)!r}"))
    if status == "armed" and not function_ids:
        issues.append(Issue(cases_rel, "armed suite needs at least one ## <function_id> heading"))

    trace_items: list[dict[str, Any]] = []
    trace_path = path.parent / "trace.yaml"
    if trace_path.is_file():
        trace_rel = _rel(root, trace_path)
        try:
            trace = load_yaml_file(trace_path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            issues.append(Issue(trace_rel, f"cannot read trace.yaml: {exc}"))
        else:
            if not isinstance(trace, dict):
                issues.append(Issue(trace_rel, "trace.yaml must be a mapping"))
            else:
                for err in schema_validate(trace, trace_schema, "$"):
                    issues.append(Issue(trace_rel, err))
                if trace.get("suite") and trace.get("suite") != dirname:
                    issues.append(Issue(trace_rel, f"suite must equal directory name {dirname!r}"))
                items = trace.get("items") or []
                if isinstance(items, list):
                    for index, item in enumerate(items):
                        if not isinstance(item, dict):
                            continue
                        fid = item.get("function_id")
                        if isinstance(fid, str) and fid and fid not in function_ids:
                            issues.append(
                                Issue(trace_rel, f"items[{index}].function_id {fid!r} is not a ## heading in cases.md")
                            )
                        trace_items.append(item)

    return SuiteDoc(
        path=path,
        suite_id=suite_id or dirname,
        title=str(data.get("title") or ""),
        status=str(status or ""),
        kind=str(data.get("kind") or ""),
        subject=str(data.get("subject") or ""),
        source=source,
        reviewed_by=reviewed_by if isinstance(reviewed_by, str) else None,
        reviewed_at=reviewed_at if isinstance(reviewed_at, str) else None,
        blocked_reason=blocked_reason if isinstance(blocked_reason, str) else None,
        armed_reason=armed_reason if isinstance(armed_reason, str) else None,
        cases_path=cases_path,
        cases_text=cases_text,
        function_ids=function_ids,
        trace_items=trace_items,
        raw=data,
    )


def _align_suite_inbox(root: Path, inbox: InboxDoc, suite: SuiteDoc, issues: list[Issue]) -> None:
    expected = f"inbox/{inbox.inbox_id}.md"
    if suite.source != expected:
        issues.append(Issue(_rel(root, suite.path), f"source must be {expected}"))
    allowed = inbox.in_scope + "\n" + inbox.user_cases
    for fid in suite.function_ids:
        if not token_in_text(allowed, fid):
            issues.append(
                Issue(
                    _rel(root, suite.cases_path),
                    f"function_id {fid!r} must appear in inbox In scope or User cases",
                )
            )
        if token_in_text(inbox.out_of_scope, fid) and not token_in_text(allowed, fid):
            issues.append(
                Issue(
                    _rel(root, suite.cases_path),
                    f"function_id {fid!r} is Out of scope and cannot be a cases.md heading",
                )
            )


def validate_root(root: Path) -> tuple[list[Issue], OverlayConfig | None, list[InboxDoc], list[SuiteDoc]]:
    root = root.resolve()
    issues: list[Issue] = []
    try:
        inbox_schema = load_json_schema("inbox.schema.json")
        suite_schema = load_json_schema("suite.schema.json")
        trace_schema = load_json_schema("trace.schema.json")
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(Issue("schema/", str(exc)))
        return issues, None, [], []

    config = load_overlay_config(root, issues)
    inboxes: list[InboxDoc] = []
    for path in iter_inbox_paths(root):
        doc = validate_inbox_file(root, path, config, inbox_schema, issues)
        if doc is not None:
            inboxes.append(doc)
    if not (root / "inbox").is_dir():
        issues.append(Issue("inbox/", "missing inbox directory"))

    suites: list[SuiteDoc] = []
    for path in iter_suite_paths(root):
        doc = validate_suite_file(root, path, suite_schema, trace_schema, issues)
        if doc is not None:
            suites.append(doc)

    inbox_by_id = {doc.inbox_id: doc for doc in inboxes}
    suite_by_id = {doc.suite_id: doc for doc in suites}
    for inbox in inboxes:
        suite = suite_by_id.get(inbox.inbox_id)
        if suite is not None:
            _align_suite_inbox(root, inbox, suite, issues)
    for suite in suites:
        inbox = inbox_by_id.get(suite.suite_id)
        if inbox is None and suite.source:
            # source existence already flagged; skip heading alignment
            continue

    seen_leaf: dict[str, str] = {}
    for suite in suites:
        for fid in suite.function_ids:
            owner = seen_leaf.get(fid)
            if owner is not None and owner != suite.suite_id:
                issues.append(
                    Issue(
                        _rel(root, suite.cases_path),
                        f"function_id {fid!r} is already used by suite {owner!r}",
                    )
                )
            else:
                seen_leaf[fid] = suite.suite_id

    issues.sort(key=lambda item: (item.path, item.message))
    return issues, config, inboxes, suites


def validate_or_issues(root: Path) -> list[Issue]:
    issues, _config, _inboxes, _suites = validate_root(root)
    return issues


def run_validate(root: Path, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    issues, _config, inboxes, suites = validate_root(root)
    if issues:
        for issue in issues:
            print(issue, file=err)
        print(f"overlay validate: {len(issues)} contract issue(s)", file=err)
        return EXIT_CONTRACT
    print(
        f"overlay validate: ok ({len(inboxes)} inbox, {len(suites)} suite)",
        file=out,
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    raise SystemExit("use python -m overlay validate")
