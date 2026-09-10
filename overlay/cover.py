"""Coverage ledger: local triad, cited invariants, optional interaction hints.

No model. Not line coverage. Not a second PRD tree.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from overlay import EXIT_CONTRACT, EXIT_OK
from overlay.validate import (
    H2_RE,
    REQUIRED_TECHNIQUES,
    InboxDoc,
    InvariantDoc,
    SuiteDoc,
    load_invariants,
    load_json_schema,
    parse_function_id,
    token_in_text,
    validate_root,
)


def function_sections(cases_text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buf)

    for line in cases_text.splitlines():
        heading = H2_RE.match(line)
        if heading is not None:
            flush()
            buf = []
            current = parse_function_id(heading.group(1))
            continue
        if current is not None:
            buf.append(line)
    flush()
    return sections


def sibling_hints(inboxes: list[InboxDoc], suites: list[SuiteDoc]) -> list[str]:
    suite_by_id = {suite.suite_id: suite for suite in suites}
    hints: list[str] = []
    for inbox in inboxes:
        suite = suite_by_id.get(inbox.inbox_id)
        if suite is None or len(suite.function_ids) < 2:
            continue
        related: set[str] = set()
        for item in suite.trace_items:
            for other in item.get("relates") or []:
                if isinstance(other, str):
                    related.add(other)
        leaves = suite.function_ids
        sections = function_sections(suite.cases_text)
        coupled = any(
            token_in_text(sections.get(fid, ""), other) or other in related
            for fid in leaves
            for other in leaves
            if other != fid
        )
        if not coupled and suite.status == "armed":
            hints.append(
                f"{suite.suite_id}: armed leaves {leaves} share one inbox; "
                f"add an interaction case or trace.relates (span=interaction)"
            )
    return hints


def format_cover_report(
    suites: list[SuiteDoc],
    invariants: list[InvariantDoc],
    hints: list[str],
) -> str:
    lines = ["# overlay cover", ""]
    lines.append("## function_id")
    for suite in sorted(suites, key=lambda item: item.suite_id):
        for fid in suite.function_ids:
            have = suite.techniques.get(fid, frozenset())
            marks = " ".join(
                f"{name}={'yes' if name in have else 'NO'}"
                for name in ("functional", "negative", "edge")
            )
            lines.append(f"- {fid} suite={suite.suite_id} status={suite.status} {marks}")
            missing = sorted(REQUIRED_TECHNIQUES - have)
            if missing and suite.status != "armed":
                lines.append(f"  hint: missing {', '.join(missing)} (not gated while {suite.status})")
    if not any(suite.function_ids for suite in suites):
        lines.append("- (none)")
    lines.append("")
    lines.append("## invariants")
    corpus = "\n".join(suite.cases_text for suite in suites)
    if not invariants:
        lines.append("- (no invariants.yaml; global corners are undeclared)")
    for inv in invariants:
        cited = "yes" if token_in_text(corpus, inv.inv_id) else "NO"
        lines.append(
            f"- {inv.inv_id} cited={cited} span={inv.span} "
            f"function_ids={','.join(inv.function_ids)}"
        )
    if hints:
        lines.append("")
        lines.append("## interaction hints")
        for hint in hints:
            lines.append(f"- {hint}")
    lines.append("")
    return "\n".join(lines)


def run_cover(root: Path, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    issues, _config, inboxes, suites = validate_root(root)
    try:
        schema = load_json_schema("invariants.schema.json")
    except (OSError, ValueError):
        schema = {"type": "object"}
    # Re-read invariants even when validate already flagged them, for the matrix.
    extra: list = []
    invariants = load_invariants(root, schema, extra)
    hints = sibling_hints(inboxes, suites)
    print(format_cover_report(suites, invariants, hints), file=out, end="")
    if issues:
        for issue in issues:
            print(issue, file=err)
        print(f"overlay cover: {len(issues)} contract issue(s)", file=err)
        return EXIT_CONTRACT
    print(
        f"overlay cover: ok ({sum(len(s.function_ids) for s in suites)} function_id, "
        f"{len(invariants)} invariant)",
        file=out,
    )
    return EXIT_OK
