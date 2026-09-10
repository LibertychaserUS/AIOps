"""Program-written overlay receipt. Models must not write this file.

This module must not import an HTTP client. wrote_by is only select or run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

RECEIPT_SCHEMA = "overlay-receipt/v1"
ALLOWED_WROTE_BY = frozenset({"select", "run"})


class ReceiptError(ValueError):
    """Illegal receipt payload (implementation bug, not a model path)."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_receipt(
    *,
    wrote_by: str,
    git_sha: str,
    branch: str,
    events: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    at: str | None = None,
) -> dict[str, Any]:
    if wrote_by not in ALLOWED_WROTE_BY:
        raise ReceiptError(f"wrote_by must be select|run, not {wrote_by!r}")
    return {
        "schema": RECEIPT_SCHEMA,
        "wrote_by": wrote_by,
        "git_sha": git_sha,
        "branch": branch,
        "at": at or utc_now(),
        "events": list(events),
        "evidence": list(evidence),
    }


def receipt_filename(branch: str, git_sha: str, run_id: str | None = None) -> str:
    safe_branch = branch.replace("/", "-") or "unknown"
    if run_id:
        return f"{run_id}.yaml"
    short = git_sha[:12] if git_sha else "unknown"
    return f"{safe_branch}-{short}.yaml"


def write_receipt(directory: Path, receipt: dict[str, Any], filename: str) -> Path:
    wrote_by = receipt.get("wrote_by")
    if wrote_by not in ALLOWED_WROTE_BY:
        raise ReceiptError(f"refusing to write receipt with wrote_by={wrote_by!r}")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    text = yaml.safe_dump(
        receipt,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    path.write_text(text, encoding="utf-8")
    return path
