"""Compile one inbox into suites/<id> via a chat completion. Not on push.

Uses urllib (stdlib). Tests inject urlopen. Missing API key exits 3.
Parse failure writes nothing. Never clears blocked.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TextIO

import yaml

from overlay import EXIT_CONTRACT, EXIT_MISSING_KEY, EXIT_OK
from overlay.validate import Issue, load_json_schema, load_overlay_config, validate_inbox_file

UrlOpen = Callable[..., Any]
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE = "https://api.openai.com/v1"
FUNCTION_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def prompts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts"


def resolve_api_key(environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        value = (env.get(name) or "").strip()
        if value:
            return value
    return None


def chat_url(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    base = (env.get("OPENAI_BASE_URL") or DEFAULT_BASE).strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def load_prompt(path: Path) -> tuple[float, str]:
    text = path.read_text(encoding="utf-8")
    temperature = 0.0
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            front = yaml.safe_load(text[4:end]) or {}
            body = text[end + 5 :]
            if isinstance(front, dict) and front.get("temperature") is not None:
                temperature = float(front["temperature"])
    return temperature, body.strip()


def parse_model_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    text = FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _post_chat(
    *,
    url: str,
    api_key: str,
    model: str,
    temperature: float,
    system: str,
    user: str,
    urlopen: UrlOpen,
    timeout: float = 60,
) -> dict[str, Any] | None:
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except (OSError, urllib.error.URLError, TimeoutError):
        return None
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict):
        return None
    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return parse_model_json(content)


def _functions_from_extract(data: dict[str, Any]) -> list[dict[str, str]] | None:
    raw = data.get("functions")
    if not isinstance(raw, list) or not raw:
        return None
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            return None
        fid = str(item.get("id") or "").strip()
        intent = str(item.get("intent") or "").strip()
        if FUNCTION_ID_RE.fullmatch(fid) is None or not intent or fid in seen:
            return None
        seen.add(fid)
        out.append({"id": fid, "intent": intent})
    return out


def _cases_from_model(
    data: dict[str, Any], expected_ids: list[str]
) -> tuple[str, list[dict[str, str]]] | None:
    title = str(data.get("title") or "").strip().replace("\n", " ")
    raw = data.get("functions")
    if not title or not isinstance(raw, list):
        return None
    by_id: dict[str, dict[str, str]] = {}
    for item in raw:
        if not isinstance(item, dict):
            return None
        fid = str(item.get("id") or "").strip()
        heading = str(item.get("heading") or "").strip().replace("\n", " ")
        functional = str(item.get("functional") or "").strip()
        negative = str(item.get("negative") or "").strip()
        edge = str(item.get("edge") or "").strip()
        if FUNCTION_ID_RE.fullmatch(fid) is None or not heading:
            return None
        if not functional or not negative or not edge:
            return None
        by_id[fid] = {
            "id": fid,
            "heading": heading,
            "functional": functional,
            "negative": negative,
            "edge": edge,
        }
    if set(by_id) != set(expected_ids):
        return None
    ordered = [by_id[fid] for fid in expected_ids if fid in by_id]
    if len(ordered) != len(expected_ids):
        return None
    return title, ordered


def render_cases(title: str, readiness: str, functions: list[dict[str, str]]) -> str:
    parts = [f"<!-- inbox-readiness: {readiness} -->", f"# {title}", ""]
    for item in functions:
        parts.append(f"## {item['id']} {item['heading']}")
        parts.append("")
        parts.append("### Functional")
        parts.append(item["functional"])
        parts.append("")
        parts.append("### Negative")
        parts.append(item["negative"])
        parts.append("")
        parts.append("### Edge")
        parts.append(item["edge"])
        parts.append("")
    return "\n".join(parts)


def render_suite(
    *,
    suite_id: str,
    title: str,
    packages: list[str],
) -> str:
    if packages:
        package_block = "packages:\n" + "\n".join(f"  - {item}" for item in packages)
    else:
        package_block = "packages: []"
    safe_title = json.dumps(title, ensure_ascii=False)
    return (
        "schema: overlay-suite/v2\n"
        f"id: {suite_id}\n"
        f"title: {safe_title}\n"
        "status: active\n"
        "kind: functional\n"
        "subject: product\n"
        f"source: inbox/{suite_id}.md\n"
        f"{package_block}\n"
        "blocked_reason: null\n"
        "product_command: null\n"
    )


def _existing_status(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return ""
    if not isinstance(data, dict):
        return ""
    status = str(data.get("status") or "").strip()
    return status or "active"


def _inbox_path(root: Path, inbox: str) -> Path | None:
    raw = Path(inbox)
    if not raw.is_absolute():
        raw = root / raw
    try:
        rel = raw.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    if rel.parent.as_posix() != "inbox" or raw.suffix != ".md":
        return None
    return raw


def run_generate(
    root: Path,
    inbox: str,
    *,
    force: bool = False,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    urlopen: UrlOpen | None = None,
) -> int:
    import sys

    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    env = os.environ if environ is None else environ
    root = root.resolve()
    config_issues: list[Issue] = []
    config = load_overlay_config(root, config_issues)
    if config is None or config_issues:
        for issue in config_issues:
            print(issue, file=err)
        print("overlay generate: overlay.yaml is not valid", file=err)
        return EXIT_CONTRACT
    inbox_file = _inbox_path(root, inbox)
    if inbox_file is None or not inbox_file.is_file():
        print("overlay generate: --inbox must be inbox/<id>.md under --root", file=err)
        return EXIT_CONTRACT
    inbox_issues: list[Issue] = []
    doc = validate_inbox_file(
        root,
        inbox_file,
        config,
        load_json_schema("inbox.schema.json"),
        inbox_issues,
    )
    if doc is None or inbox_issues:
        for issue in inbox_issues:
            print(issue, file=err)
        print("overlay generate: inbox failed validate", file=err)
        return EXIT_CONTRACT

    suite_yaml = root / "suites" / doc.inbox_id / "suite.yaml"
    existing = _existing_status(suite_yaml)
    if existing == "blocked":
        print(
            "overlay generate: refusing to write "
            f"{doc.inbox_id}: status is blocked; --force does not clear blocked",
            file=err,
        )
        return EXIT_CONTRACT
    if existing is not None and not force:
        print(
            "overlay generate: suite exists; pass --force to replace a non-blocked suite",
            file=err,
        )
        return EXIT_CONTRACT

    api_key = resolve_api_key(env)
    if not api_key:
        print("overlay generate: missing OPENAI_API_KEY", file=err)
        return EXIT_MISSING_KEY

    extract_path = prompts_dir() / "extract.md"
    cases_path = prompts_dir() / "generate-cases.md"
    if not extract_path.is_file() or not cases_path.is_file():
        print("overlay generate: missing prompts/extract.md or prompts/generate-cases.md", file=err)
        return EXIT_CONTRACT
    extract_temp, extract_prompt = load_prompt(extract_path)
    cases_temp, cases_prompt = load_prompt(cases_path)
    opener = urllib.request.urlopen if urlopen is None else urlopen
    model = (env.get("OPENAI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    url = chat_url(env)
    inbox_text = inbox_file.read_text(encoding="utf-8")
    extracted = _post_chat(
        url=url,
        api_key=api_key,
        model=model,
        temperature=extract_temp,
        system=extract_prompt,
        user=inbox_text,
        urlopen=opener,
    )
    if extracted is None:
        print("overlay generate: extract response was not JSON; wrote nothing", file=err)
        return EXIT_CONTRACT
    functions = _functions_from_extract(extracted)
    if functions is None:
        print("overlay generate: extract JSON failed the contract; wrote nothing", file=err)
        return EXIT_CONTRACT
    cases_user = json.dumps({"inbox": inbox_text, "functions": functions}, ensure_ascii=False)
    generated = _post_chat(
        url=url,
        api_key=api_key,
        model=model,
        temperature=cases_temp,
        system=cases_prompt,
        user=cases_user,
        urlopen=opener,
    )
    if generated is None:
        print("overlay generate: cases response was not JSON; wrote nothing", file=err)
        return EXIT_CONTRACT
    parsed = _cases_from_model(generated, [item["id"] for item in functions])
    if parsed is None:
        print("overlay generate: cases JSON failed the contract; wrote nothing", file=err)
        return EXIT_CONTRACT
    title, ordered = parsed
    readiness = str(doc.front.get("readiness") or "unknown")
    if readiness not in {"ready", "not-ready", "unknown"}:
        readiness = "unknown"
    packages_raw = doc.front.get("packages") or []
    packages = [str(item) for item in packages_raw] if isinstance(packages_raw, list) else []
    suite_text = render_suite(suite_id=doc.inbox_id, title=title, packages=packages)
    cases_text = render_cases(title, readiness, ordered)
    dest = suite_yaml.parent
    dest.mkdir(parents=True, exist_ok=True)
    suite_yaml.write_text(suite_text, encoding="utf-8")
    (dest / "cases.md").write_text(cases_text, encoding="utf-8")
    rel = suite_yaml.relative_to(root).as_posix()
    print(f"overlay generate: wrote {rel} status=active", file=out)
    return EXIT_OK
