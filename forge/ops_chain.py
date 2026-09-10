"""Overlay Ops CI stages that sit around Overlay validate/select/run.

DAG on pull_request (when overlay-check is selected):

    spec (pr-title) → review-bots (CodeRabbit + Copilot comments) → full overlay CI
    → human merge

On red spec/CI or a failed merge report: PR 打回 + write an ops-debug report.
CodeRabbit / Copilot are advisory. This module never merges and never arms.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO
from urllib.parse import urlparse
from urllib.request import Request

from forge import EXIT_CONFIG, EXIT_OK
from forge.apply import REPO_RE

UrlOpen = Callable[..., Any]

BOT_NEEDLES = ("coderabbit", "copilot")
BOUNCE_MARK = "overlay-ops-bounce"


@dataclass
class BotSighting:
    kind: str
    name: str
    source: str


@dataclass
class ReviewReport:
    seen: list[BotSighting] = field(default_factory=list)
    waited_s: int = 0
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "overlay-ops-review/v1",
            "advisory": True,
            "waited_s": self.waited_s,
            "note": self.note,
            "seen": [
                {"kind": item.kind, "name": item.name, "source": item.source}
                for item in self.seen
            ],
        }


def _request(
    urlopen: UrlOpen,
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> Any:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "forge-ops-chain",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=10) as resp:
        raw = resp.read()
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _token(environ: Mapping[str, str]) -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = (environ.get(key) or "").strip()
        if value:
            return value
    return ""


def _is_bot_name(name: str) -> bool:
    lower = name.lower()
    return any(needle in lower for needle in BOT_NEEDLES)


def collect_bot_sightings(
    *,
    repo: str,
    sha: str,
    pr: int,
    urlopen: UrlOpen,
    base_url: str,
    token: str,
) -> list[BotSighting]:
    found: list[BotSighting] = []
    api = base_url.rstrip("/")
    if sha:
        checks = _request(
            urlopen, "GET", f"{api}/repos/{repo}/commits/{sha}/check-runs", token
        )
        runs = checks.get("check_runs") if isinstance(checks, dict) else None
        if isinstance(runs, list):
            for run in runs:
                if not isinstance(run, dict):
                    continue
                name = str(run.get("name") or "")
                if _is_bot_name(name):
                    found.append(BotSighting("check", name, "check-runs"))
    if pr > 0:
        for path, source in (
            (f"{api}/repos/{repo}/issues/{pr}/comments", "issue-comments"),
            (f"{api}/repos/{repo}/pulls/{pr}/comments", "review-comments"),
        ):
            comments = _request(urlopen, "GET", path, token)
            if not isinstance(comments, list):
                continue
            for comment in comments:
                if not isinstance(comment, dict):
                    continue
                user = comment.get("user")
                login = ""
                if isinstance(user, dict):
                    login = str(user.get("login") or "")
                body = str(comment.get("body") or "")
                hay = f"{login} {body}"
                if _is_bot_name(hay):
                    found.append(
                        BotSighting("comment", login or "comment", source)
                    )
    return found


def run_review_bots(
    *,
    repo: str,
    sha: str,
    pr: int,
    write_report: Path,
    urlopen: UrlOpen,
    base_url: str,
    environ: Mapping[str, str],
    stdout: TextIO,
    stderr: TextIO,
    wait_s: int = 0,
    poll_s: int = 5,
    sleeper: Callable[[float], None] | None = None,
) -> int:
    if REPO_RE.match(repo) is None:
        print(f"bad repo: {repo}", file=stderr)
        return EXIT_CONFIG
    token = _token(environ)
    if not token:
        print("ops-review: no GITHUB_TOKEN; writing empty advisory report", file=stderr)
        report = ReviewReport(note="no token; bots not queried")
        _write_yaml(write_report / "review-bots.yaml", report.as_dict())
        print("review-bots advisory (no token)", file=stdout)
        return EXIT_OK

    sleep = sleeper or time.sleep
    deadline = max(0, wait_s)
    waited = 0
    seen: list[BotSighting] = []
    while True:
        try:
            seen = collect_bot_sightings(
                repo=repo,
                sha=sha,
                pr=pr,
                urlopen=urlopen,
                base_url=base_url,
                token=token,
            )
        except Exception as exc:
            host = urlparse(base_url).hostname or ""
            if host in {"api.github.com"} and "test" not in base_url:
                print(f"ops-review query failed: {exc}", file=stderr)
            report = ReviewReport(note=f"query failed: {exc}", waited_s=waited)
            _write_yaml(write_report / "review-bots.yaml", report.as_dict())
            print("review-bots advisory (query failed)", file=stdout)
            return EXIT_OK
        if seen or waited >= deadline:
            break
        step = min(poll_s, deadline - waited) if deadline else 0
        if step <= 0:
            break
        sleep(step)
        waited += step

    note = "bots seen" if seen else "no CodeRabbit/Copilot yet; advisory, continue to full CI"
    report = ReviewReport(seen=seen, waited_s=waited, note=note)
    _write_yaml(write_report / "review-bots.yaml", report.as_dict())
    print(f"review-bots {note}", file=stdout)
    return EXIT_OK


def bounce_body(*, failed: list[str], run_url: str) -> str:
    jobs = ", ".join(failed) if failed else "unknown"
    lines = [
        f"<!-- {BOUNCE_MARK} -->",
        "## 打回",
        "",
        f"Overlay Ops 链失败：`{jobs}`。不要合。",
        "",
        "- PR 侧：按失败点改标题/正文或分支上的 Overlay 全量 CI。",
        "- Ops / CI 侧：本 run 的 artifact（`overlay-ops-debug`、receipts）留存，用来 debug。",
    ]
    if run_url:
        lines.extend(["", f"Run: {run_url}"])
    return "\n".join(lines) + "\n"


def run_bounce(
    *,
    repo: str,
    pr: int,
    failed: list[str],
    write_report: Path,
    urlopen: UrlOpen,
    base_url: str,
    environ: Mapping[str, str],
    stdout: TextIO,
    stderr: TextIO,
    run_url: str = "",
    dry_run: bool = False,
) -> int:
    if REPO_RE.match(repo) is None:
        print(f"bad repo: {repo}", file=stderr)
        return EXIT_CONFIG
    if pr <= 0:
        print("bounce needs --pr", file=stderr)
        return EXIT_CONFIG
    payload = {
        "schema": "overlay-ops-debug/v1",
        "action": "bounce",
        "merge": False,
        "failed": list(failed),
        "pr": pr,
        "repo": repo,
        "run_url": run_url,
        "note": "PR 打回；Ops/CI 留这份报告和 workflow artifacts 做 debug。不合入。",
    }
    _write_yaml(write_report / "ops-debug.yaml", payload)
    body = bounce_body(failed=failed, run_url=run_url)
    if dry_run:
        print("bounce dry-run; wrote ops-debug.yaml; no GitHub write", file=stdout)
        return EXIT_OK
    token = _token(environ)
    if not token:
        print("bounce: no GITHUB_TOKEN; report kept, no PR comment", file=stderr)
        return EXIT_OK
    api = base_url.rstrip("/")
    try:
        _request(
            urlopen,
            "POST",
            f"{api}/repos/{repo}/issues/{pr}/comments",
            token,
            {"body": body},
        )
    except Exception as exc:
        print(f"bounce comment failed: {exc}", file=stderr)
        print("ops-debug.yaml kept for debug", file=stdout)
        return EXIT_OK
    print(f"bounce: 打回 PR #{pr}", file=stdout)
    return EXIT_OK


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except ImportError:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
