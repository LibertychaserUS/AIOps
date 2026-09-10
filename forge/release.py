"""Publish Overlay and Forge GitHub Releases. Not production CD. Never merges."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, TextIO

from forge import EXIT_API, EXIT_AUTH, EXIT_CONFIG, EXIT_OK, FORBIDDEN_REPOS
from forge.apply import (
    DEFAULT_API,
    ForgeError,
    GitHubClient,
    default_urlopen,
    parse_repo,
    resolve_token,
)

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
TAG_RE = re.compile(r"^(overlay|forge)-v([0-9]+\.[0-9]+\.[0-9]+)$")
PRODUCTS = ("overlay", "forge")
VERSION_LINE_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


def assert_release_allowed(owner: str, name: str) -> None:
    key = f"{owner}/{name}".lower()
    if key in FORBIDDEN_REPOS:
        raise ForgeError(EXIT_CONFIG, f"refusing to release {owner}/{name}")
    if "ilovelearningguide" in key:
        raise ForgeError(EXIT_CONFIG, f"refusing to release {owner}/{name}")


def parse_version(version: str) -> str:
    text = (version or "").strip()
    if text.startswith("v"):
        text = text[1:]
    if not VERSION_RE.fullmatch(text):
        raise ForgeError(EXIT_CONFIG, f"illegal version: {version!r} (use 1.0.1)")
    return text


def parse_products(raw: str) -> tuple[str, ...]:
    text = (raw or "both").strip().lower()
    if text == "both":
        return PRODUCTS
    if text in PRODUCTS:
        return (text,)
    raise ForgeError(EXIT_CONFIG, f"illegal products: {raw!r} (both|overlay|forge)")


def product_tag(product: str, version: str) -> str:
    return f"{product}-v{version}"


def read_package_version(root: Path, package: str) -> str:
    path = root / package / "__init__.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ForgeError(EXIT_CONFIG, f"cannot read {path}: {exc}") from exc
    match = VERSION_LINE_RE.search(text)
    if match is None:
        raise ForgeError(EXIT_CONFIG, f"{path.as_posix()} has no __version__")
    return match.group(1)


def assert_versions_match(root: Path, version: str, products: tuple[str, ...]) -> None:
    for product in products:
        found = read_package_version(root, product)
        if found != version:
            raise ForgeError(
                EXIT_CONFIG,
                f"{product} __version__ is {found!r}, not {version!r}",
            )


def release_notes(product: str, version: str, sha: str) -> str:
    tag = product_tag(product, version)
    other = "forge" if product == "overlay" else "overlay"
    other_tag = product_tag(other, version)
    title = "Overlay" if product == "overlay" else "Forge"
    if product == "overlay":
        body = (
            f"Independent Overlay product tag `{tag}` at `{sha}`.\n\n"
            f"This repo has **two** product tags. Sister: `{other_tag}`.\n"
            "GitHub Latest is one badge; pin this tag, not `main`.\n\n"
            "Start: https://github.com/LibertychaserUS/AIOps#aiops\n\n"
            "- CLI: `validate`, `select`, `run`, `cover`. No `generate`.\n"
            "- Reusable `.github/workflows/overlay.yml`: `tool_repository` / `tool_ref`.\n"
            "- Never checkout LearningGuidePortal. Do not vendor `overlay/`.\n"
            "- Suite states: `draft` | `blocked` | `armed`.\n"
        )
    else:
        body = (
            f"Independent Forge product tag `{tag}` at `{sha}`.\n\n"
            f"This repo has **two** product tags. Sister: `{other_tag}`.\n"
            "GitHub Latest is one badge; pin this tag, not `main`.\n\n"
            "Start: https://github.com/LibertychaserUS/AIOps#aiops\n\n"
            "- `forge apply` writes Ruleset `required_status_checks`.\n"
            "- `forge check` then `submit` with `FORGE_SUBMIT_TOKEN`. Never merges.\n"
            "- `forge release` publishes product tags. Not production CD.\n"
            "- Do not live-apply LearningGuidePortal. Do not replace adopter Verify.\n"
        )
    return f"{title} {version}\n\n{body}"


def release_payload(product: str, version: str, sha: str) -> dict[str, Any]:
    tag = product_tag(product, version)
    title = "Overlay" if product == "overlay" else "Forge"
    return {
        "tag_name": tag,
        "target_commitish": sha,
        "name": f"{title} {version}",
        "body": release_notes(product, version, sha),
        "draft": False,
        "prerelease": False,
        "make_latest": "false",
    }


def resolve_sha(client: GitHubClient, owner: str, name: str, sha: str | None) -> str:
    text = (sha or "").strip()
    if text:
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", text):
            raise ForgeError(EXIT_CONFIG, f"illegal sha: {sha!r}")
        return text.lower()
    ref = client.request("GET", f"/repos/{owner}/{name}/git/ref/heads/main")
    if not isinstance(ref, dict):
        raise ForgeError(EXIT_API, "GitHub API returned a non-object main ref")
    obj = ref.get("object")
    if not isinstance(obj, dict) or not isinstance(obj.get("sha"), str):
        raise ForgeError(EXIT_API, "main ref has no sha")
    return obj["sha"]


def existing_release(client: GitHubClient, owner: str, name: str, tag: str) -> dict[str, Any] | None:
    payload = client.request(
        "GET",
        f"/repos/{owner}/{name}/releases/tags/{tag}",
        not_found_ok=True,
    )
    return payload if isinstance(payload, dict) else None


def run_release(
    *,
    repo: str,
    version: str,
    products: str = "both",
    sha: str | None = None,
    root: Path | str | None = None,
    dry_run: bool = False,
    token: str | None = None,
    urlopen: Any | None = None,
    base_url: str = DEFAULT_API,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: dict[str, str] | os._Environ[str] | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        owner, name = parse_repo(repo)
        assert_release_allowed(owner, name)
        ver = parse_version(version)
        chosen = parse_products(products)
        workshop = Path(root) if root is not None else Path(".")
        if (workshop / "overlay" / "__init__.py").is_file():
            assert_versions_match(workshop, ver, chosen)
        planned = [release_payload(product, ver, (sha or "").strip() or "main") for product in chosen]
        if dry_run:
            print("dry-run", file=out)
            print("publish GitHub Releases (not production CD)", file=out)
            print(json.dumps(planned, indent=2), file=out)
            return EXIT_OK
        resolved = token if token is not None else resolve_token(environ)
        if not resolved:
            print("missing FORGE_GITHUB_TOKEN or GITHUB_TOKEN", file=err)
            return EXIT_AUTH
        opener = urlopen or default_urlopen
        client = GitHubClient(resolved, urlopen=opener, base_url=base_url)
        target = resolve_sha(client, owner, name, sha)
        for product in chosen:
            tag = product_tag(product, ver)
            found = existing_release(client, owner, name, tag)
            if found is not None:
                raise ForgeError(EXIT_API, f"release {tag} already exists")
            payload = release_payload(product, ver, target)
            created = client.request("POST", f"/repos/{owner}/{name}/releases", payload)
            url = created.get("html_url") if isinstance(created, dict) else None
            print(f"published {tag} sha={target} {url or ''}".rstrip(), file=out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
