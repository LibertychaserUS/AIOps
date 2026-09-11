"""Publish Overlay and Forge GitHub Releases. Not production CD. Never merges."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from forge import EXIT_API, EXIT_AUTH, EXIT_CONFIG, EXIT_OK
from forge.apply import (
    DEFAULT_API,
    ForgeError,
    GitHubClient,
    default_urlopen,
    load_config,
    parse_repo,
    resolve_token,
    assert_live_repo_allowed,
)

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
TAG_RE = re.compile(r"^(overlay|forge)-v([0-9]+\.[0-9]+\.[0-9]+)$")
PRODUCTS = ("overlay", "forge")
VERSION_LINE_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


CHANGELOG_HEADING_RE = re.compile(r"^## \[([^\]]+)\]\s*$", re.MULTILINE)


def assert_release_allowed(owner: str, name: str, forbidden: Sequence[str] | None = None) -> None:
    assert_live_repo_allowed(owner, name, forbidden, action="release")


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
    found_versions = {product: read_package_version(root, product) for product in products}
    if products == PRODUCTS:
        overlay_ver = found_versions.get("overlay")
        forge_ver = found_versions.get("forge")
        if overlay_ver != forge_ver:
            raise ForgeError(
                EXIT_CONFIG,
                f"--products both requires equal __version__ (overlay={overlay_ver!r}, "
                f"forge={forge_ver!r}); run twice with --products overlay|forge",
            )
    for product, found in found_versions.items():
        if found != version:
            raise ForgeError(
                EXIT_CONFIG,
                f"{product} __version__ is {found!r}, not {version!r}",
            )


def changelog_section(root: Path, product: str, version: str) -> str:
    path = root / "CHANGELOG.md"
    heading = f"{product}-{version}"
    if not path.is_file():
        raise ForgeError(EXIT_CONFIG, f"CHANGELOG.md missing heading ## [{heading}]")
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(heading)}\]\s*$",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match is None:
        raise ForgeError(EXIT_CONFIG, f"CHANGELOG.md missing heading ## [{heading}]")
    start = match.end()
    nxt = re.search(r"^## \[", text[start:], re.MULTILINE)
    body = text[start : start + nxt.start() if nxt else None].strip()
    return body


RELEASE_FOOTER = (
    "\n\n---\nPublished by `python -m forge release`. Pin this tag, not `main`.\n"
)


def release_notes(product: str, version: str, sha: str, section: str) -> str:
    tag = product_tag(product, version)
    title = "Overlay" if product == "overlay" else "Forge"
    return f"{title} {version} (`{tag}` @ `{sha}`)\n\n{section}{RELEASE_FOOTER}"


def release_payload(product: str, version: str, sha: str, section: str = "") -> dict[str, Any]:
    tag = product_tag(product, version)
    title = "Overlay" if product == "overlay" else "Forge"
    return {
        "tag_name": tag,
        "target_commitish": sha,
        "name": f"{title} {version}",
        "body": release_notes(product, version, sha, section),
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


def existing_tag_sha(client: GitHubClient, owner: str, name: str, tag: str) -> str | None:
    """Commit SHA an existing tag points at (annotated tags peeled). None if absent."""
    ref = client.request("GET", f"/repos/{owner}/{name}/git/ref/tags/{tag}", not_found_ok=True)
    if not isinstance(ref, dict):
        return None
    obj = ref.get("object")
    if not isinstance(obj, dict) or not isinstance(obj.get("sha"), str):
        raise ForgeError(EXIT_API, f"tag {tag} ref has no sha")
    sha = obj["sha"]
    if obj.get("type") != "tag":
        return sha.lower()
    tag_obj = client.request("GET", f"/repos/{owner}/{name}/git/tags/{sha}")
    peeled = tag_obj.get("object") if isinstance(tag_obj, dict) else None
    if not isinstance(peeled, dict) or not isinstance(peeled.get("sha"), str):
        raise ForgeError(EXIT_API, f"annotated tag {tag} has no target")
    return peeled["sha"].lower()


def assert_tag_matches_target(tag: str, tag_sha: str | None, target: str) -> bool:
    """True when the tag already exists at target. Red when it exists elsewhere.

    GitHub's create-release ignores target_commitish for an existing tag, so
    publishing would silently point the Release at the wrong commit.
    """
    if tag_sha is None:
        return False
    if tag_sha.startswith(target.lower()):
        return True
    raise ForgeError(
        EXIT_CONFIG,
        f"tag {tag} already exists at {tag_sha[:12]}, not {target[:12]}; "
        "refusing to force-move (bump the version instead)",
    )


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
        workshop = Path(root) if root is not None else Path(".")
        yaml_path = workshop / "forge.yaml"
        config = load_config(yaml_path if yaml_path.is_file() else None)
        assert_release_allowed(owner, name, config.forbidden_live_repos)
        ver = parse_version(version)
        chosen = parse_products(products)
        if (workshop / "overlay" / "__init__.py").is_file():
            assert_versions_match(workshop, ver, chosen)
        sections = {product: changelog_section(workshop, product, ver) for product in chosen}
        planned = [
            release_payload(product, ver, (sha or "").strip() or "main", sections[product])
            for product in chosen
        ]
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
            if assert_tag_matches_target(tag, existing_tag_sha(client, owner, name, tag), target):
                print(f"tag {tag} exists at {target}; attaching the Release only", file=out)
            payload = release_payload(product, ver, target, sections[product])
            created = client.request("POST", f"/repos/{owner}/{name}/releases", payload)
            url = created.get("html_url") if isinstance(created, dict) else None
            print(f"published {tag} sha={target} {url or ''}".rstrip(), file=out)
        return EXIT_OK
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
