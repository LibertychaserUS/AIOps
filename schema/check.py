#!/usr/bin/env python3
"""Tiny Overlay schema sanity check. Not a product CLI.

function_id is a free string. Kernel examples use FN-* / owner/name.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FORBIDDEN_IN_SCHEMA = (
    r"REQ-\[[0-9]",
    r"\^REQ-",
    r"ML-FR-",
    r"PAY-01",
    r"AUTH-01",
    r"A-Z\]\{2,8\}",
    r"MasterTestPlan",
    r"LevelTestCase",
    r"ilovelearningguide",
    r"LearningGuide",
)

GENERIC_MARKERS = ("FN-login-retry", "FN-checkout-idempotent", "owner/name", "checkout-retry")


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _fail(msg: str) -> None:
    print(f"schema/check.py: {msg}", file=sys.stderr)
    raise SystemExit(2)


def check_schemas() -> None:
    for name in ("inbox.schema.json", "suite.schema.json", "trace.schema.json"):
        path = ROOT / name
        if not path.is_file():
            _fail(f"missing {path.name}")
        try:
            _load_json(path)
        except json.JSONDecodeError as exc:
            _fail(f"{path.name} is not JSON: {exc}")
        text = path.read_text(encoding="utf-8")
        for pat in FORBIDDEN_IN_SCHEMA:
            if re.search(pat, text):
                _fail(f"{path.name} bakes catalog law matching /{pat}/")


def check_trace_contract() -> None:
    schema = _load_json(ROOT / "trace.schema.json")
    props = schema["properties"]["items"]["items"]["properties"]
    fid = props.get("function_id")
    if not isinstance(fid, dict):
        _fail("trace.schema.json must define items.function_id")
    if fid.get("type") != "string" or fid.get("minLength", 0) < 1:
        _fail("function_id must be a string with minLength >= 1")
    pattern = fid.get("pattern", "")
    if "REQ-" in pattern or "A-Z]{2,8}" in pattern:
        _fail("function_id pattern must not require a product numbering series")
    if "level" not in props:
        _fail("trace.schema.json must allow optional level")
    if set(props["level"].get("enum", [])) != {"unit", "integration", "smoke", "k6", "e2e"}:
        _fail("level enum must be unit|integration|smoke|k6|e2e")
    required = schema["properties"]["items"]["items"].get("required", [])
    if "function_id" not in required:
        _fail("function_id must be required on trace items")
    if "level" in required:
        _fail("level must be optional")
    if "requirement_id" in required or "requirement_id" in props:
        _fail("requirement_id is not a contract field; use function_id")


def check_kernel_examples() -> None:
    example = ROOT / "trace.example.yaml"
    text = example.read_text(encoding="utf-8")
    if "requirement_id:" in text:
        _fail("trace.example.yaml must use function_id, not requirement_id")
    if "function_id:" not in text:
        _fail("trace.example.yaml must show function_id")
    if not any(m in text for m in GENERIC_MARKERS):
        _fail("trace.example.yaml must use a generic FN-* / owner/name style id")
    for banned in ("ML-FR-", "ilovelearningguide", "/en-GB/", "LearningGuide", "LOGIN-01"):
        if banned in text:
            _fail(f"kernel example {example.name} must not contain {banned!r}")

    suite_ex = (ROOT / "suite.example.yaml").read_text(encoding="utf-8")
    for banned in ("my-learning", "app/[locale]", "ilovelearningguide", "REQ-", "LOGIN-01"):
        if banned in suite_ex:
            _fail(f"suite.example.yaml must stay generic (found {banned!r})")

    inbox_ex = (ROOT / "inbox.example.md").read_text(encoding="utf-8")
    if "owner/name" not in inbox_ex:
        _fail("inbox.example.md source.repo should be owner/name")
    if "FN-first-path" not in inbox_ex:
        _fail("inbox.example.md In scope should carry an adopter-minted id")


def check_trace_example_ids() -> None:
    try:
        import yaml
    except ImportError:
        print("schema/check.py: PyYAML missing; skip instance parse")
        return
    data = yaml.safe_load((ROOT / "trace.example.yaml").read_text(encoding="utf-8"))
    seen_ids: set[str] = set()
    for item in data.get("items") or []:
        fid = item.get("function_id")
        if not isinstance(fid, str) or not fid or re.search(r"\s", fid):
            _fail(f"invalid function_id: {fid!r}")
        seen_ids.add(fid)
        if "level" in item and item["level"] not in {
            "unit",
            "integration",
            "smoke",
            "k6",
            "e2e",
        }:
            _fail(f"invalid level: {item['level']!r}")
    if len(seen_ids) < 1:
        _fail("trace.example.yaml has no function_id values")


def main() -> None:
    check_schemas()
    check_trace_contract()
    check_kernel_examples()
    check_trace_example_ids()
    print("schema/check.py: ok")


if __name__ == "__main__":
    main()
