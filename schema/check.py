#!/usr/bin/env python3
"""Tiny Overlay schema sanity check. Not a product CLI.

Kernel schemas use the product-agnostic function_id grammar.
Kernel examples use LOGIN-01 / CHK-02 — never Learning Guide routes or REQ-n.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FUNCTION_ID = re.compile(r"^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$")

# Product catalogs and IEEE form names must not be law in kernel schema text.
FORBIDDEN_IN_SCHEMA = (
    r"REQ-\[[0-9]",
    r"\^REQ-",
    r"ML-FR-",
    r"PAY-01",
    r"AUTH-01",
    r"MasterTestPlan",
    r"LevelTestCase",
    r"ilovelearningguide",
    r"LearningGuide",
)

GENERIC_MARKERS = ("LOGIN-01", "CHK-02", "owner/name", "checkout-retry")


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
    if fid.get("type") != "string":
        _fail("function_id must be a string")
    pattern = fid.get("pattern", "")
    if "A-Z]{2,8}" not in pattern or "[0-9]{2,3}" not in pattern:
        _fail("function_id must use the product-agnostic grammar")
    if "REQ-" in pattern:
        _fail("function_id must not be REQ-n")
    if "level" not in props:
        _fail("trace.schema.json must define level")
    if set(props["level"].get("enum", [])) != {"unit", "integration", "smoke", "k6", "e2e"}:
        _fail("level enum must be unit|integration|smoke|k6|e2e")
    required = schema["properties"]["items"]["items"].get("required", [])
    if "function_id" not in required or "level" not in required:
        _fail("function_id and level must be required on trace items")
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
        _fail("trace.example.yaml must use LOGIN-01 / CHK-02 / owner/name style ids")
    for banned in ("ML-FR-", "ilovelearningguide", "/en-GB/", "LearningGuide", "REQ-"):
        if banned in text:
            _fail(f"kernel example {example.name} must not contain {banned!r}")

    suite_ex = (ROOT / "suite.example.yaml").read_text(encoding="utf-8")
    for banned in ("my-learning", "app/[locale]", "ilovelearningguide", "REQ-"):
        if banned in suite_ex:
            _fail(f"suite.example.yaml must stay generic (found {banned!r})")

    inbox_ex = (ROOT / "inbox.example.md").read_text(encoding="utf-8")
    if "owner/name" not in inbox_ex:
        _fail("inbox.example.md source.repo should be owner/name")
    if "LOGIN-01" not in inbox_ex:
        _fail("inbox.example.md In scope should start with LOGIN-01")


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
        if not isinstance(fid, str) or not FUNCTION_ID.match(fid):
            _fail(f"invalid function_id: {fid!r}")
        seen_ids.add(fid)
        if item.get("level") not in {
            "unit",
            "integration",
            "smoke",
            "k6",
            "e2e",
        }:
            _fail(f"invalid or missing level: {item.get('level')!r}")
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
