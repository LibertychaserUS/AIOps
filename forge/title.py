"""Lint a GitHub PR title. Pure: no GitHub write, no model.

Grammar: Conventional Commits 1.0.0 header
<https://www.conventionalcommits.org/en/v1.0.0/>
with Angular / @commitlint/config-conventional types and a required
scope `product/actor`. Same job as amannn/action-semantic-pull-request
(requireScope) and commitlint, implemented in CPython so this workshop
does not grow a Node toolchain.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from forge import EXIT_OK

EXIT_TITLE = 2


def optional_text(value: str | None) -> str | None:
    """Missing or whitespace-only is omitted.

    GitHub Actions ``env: PR_TITLE: ${{ github.event.pull_request.title }}``
    is an empty string on ``push`` (no pull_request payload). That is not a
    provided title.
    """
    if value is None or value.strip() == "":
        return None
    return value


def resolve_arg_or_env(
    explicit: str | None,
    environ: Mapping[str, str],
    key: str,
) -> str | None:
    """Prefer ``--title`` / ``--body``. Blank env values count as omitted.

    An explicit empty ``--title ""`` stays empty so the dedicated lint can
    still fail. Only the environment fallback strips blanks.
    """
    if explicit is not None:
        return explicit
    return optional_text(environ.get(key))

TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)
PRODUCTS = ("forge", "overlay", "ci", "docs")
ACTORS = ("dev", "admin", "agent")

TITLE_PATTERN = (
    r"^(?P<type>build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"\((?P<product>forge|overlay|ci|docs)/(?P<actor>dev|admin|agent)\)"
    r"(?P<breaking>!)?: (?P<subject>\S.*)$"
)
TITLE_RE = re.compile(TITLE_PATTERN)

_CC_HEADER = re.compile(
    r"^(?P<type>[^\s:()]+)"
    r"(?:\((?P<scope>[^()\n]*)\))?"
    r"(?P<breaking>!)?"
    r": "
    r"(?P<subject>.*)$"
)

GRAMMAR = "type(product/actor): subject"
EXAMPLE = "feat(overlay/dev): add cover triad and invariants"


@dataclass(frozen=True)
class TitleParts:
    type: str
    product: str
    actor: str
    breaking: bool
    subject: str


def lint_title(
    title: str | None,
    *,
    scopes: str | list[str] | None = None,
) -> tuple[int, str, TitleParts | None]:
    """Return (0, '', parts) or (2, reason, None). Never talks to GitHub.

    scopes:
      None  — current product/actor grammar
      "any" — Conventional Commits syntax only
      list  — current grammar, scope must be in the list
    """
    raw = "" if title is None else title
    if "\n" in raw or "\r" in raw:
        return EXIT_TITLE, "PR title must be a single line", None
    text = raw
    if text.strip() == "":
        return EXIT_TITLE, "empty PR title", None
    if text != text.strip():
        return EXIT_TITLE, "PR title has leading or trailing whitespace", None
    if text.startswith("["):
        return (
            EXIT_TITLE,
            f"use Conventional Commits {GRAMMAR}, not [role][product] (example: {EXAMPLE})",
            None,
        )

    if scopes == "any":
        return _lint_any(text)

    locked = TITLE_RE.fullmatch(text)
    if locked:
        parts = TitleParts(
            type=locked.group("type"),
            product=locked.group("product"),
            actor=locked.group("actor"),
            breaking=bool(locked.group("breaking")),
            subject=locked.group("subject"),
        )
        allowed = scopes if isinstance(scopes, list) else None
        if allowed is not None:
            scope = f"{parts.product}/{parts.actor}"
            if scope not in allowed:
                return EXIT_TITLE, f"scope {scope!r} is not in title.scopes", None
        return EXIT_OK, "", parts

    parsed = _CC_HEADER.fullmatch(text)
    if parsed is None:
        return (
            EXIT_TITLE,
            f"not Conventional Commits: expected {GRAMMAR} (example: {EXAMPLE})",
            None,
        )

    kind = parsed.group("type")
    scope = parsed.group("scope")
    subject = parsed.group("subject")

    if kind.lower() != kind:
        return EXIT_TITLE, f"type must be lowercase (got {kind!r})", None
    if kind not in TYPES:
        return EXIT_TITLE, f"unknown type {kind!r} (use {'|'.join(TYPES)})", None
    if scope is None or scope == "":
        return (
            EXIT_TITLE,
            "scope is required: product/actor "
            f"({('|'.join(PRODUCTS))})/({('|'.join(ACTORS))})",
            None,
        )
    if "/" not in scope:
        return (
            EXIT_TITLE,
            f"scope must be product/actor (got {scope!r}; example overlay/dev)",
            None,
        )
    product, _, actor = scope.partition("/")
    extra = actor.split("/", 1)[1] if actor.count("/") else ""
    actor_token = actor.split("/", 1)[0]
    if extra:
        return EXIT_TITLE, f"scope must be product/actor only (got {scope!r})", None
    if product not in PRODUCTS:
        return EXIT_TITLE, f"unknown product {product!r} (use {'|'.join(PRODUCTS)})", None
    if actor_token not in ACTORS:
        return (
            EXIT_TITLE,
            f"unknown actor {actor_token!r} (use {'|'.join(ACTORS)}; 开发=dev 管理=admin)",
            None,
        )
    if subject.strip() == "":
        return EXIT_TITLE, "missing subject after ': '", None
    if isinstance(scopes, list) and f"{product}/{actor_token}" not in scopes:
        return EXIT_TITLE, f"scope {product}/{actor_token!r} is not in title.scopes", None
    return (
        EXIT_TITLE,
        f"not Conventional Commits: expected {GRAMMAR} (example: {EXAMPLE})",
        None,
    )


def _lint_any(text: str) -> tuple[int, str, TitleParts | None]:
    if len(text) > 72:
        return EXIT_TITLE, "PR title must be <= 72 characters", None
    parsed = _CC_HEADER.fullmatch(text)
    if parsed is None:
        return (
            EXIT_TITLE,
            "not Conventional Commits: expected type(optional-scope): subject",
            None,
        )
    kind = parsed.group("type")
    subject = parsed.group("subject")
    if kind.lower() != kind:
        return EXIT_TITLE, f"type must be lowercase (got {kind!r})", None
    if kind not in TYPES:
        return EXIT_TITLE, f"unknown type {kind!r} (use {'|'.join(TYPES)})", None
    if subject.strip() == "":
        return EXIT_TITLE, "missing subject after ': '", None
    if subject.rstrip().endswith("."):
        return EXIT_TITLE, "subject must not end with a period", None
    scope = parsed.group("scope") or ""
    product, _, actor = scope.partition("/") if scope else ("", "", "")
    parts = TitleParts(
        type=kind,
        product=product or "",
        actor=actor or "",
        breaking=bool(parsed.group("breaking")),
        subject=subject,
    )
    return EXIT_OK, "", parts


def run_pr_title(
    *,
    title: str | None,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    root: Path | str | None = None,
    scopes: str | list[str] | None = None,
) -> int:
    """CLI entry. Reads --title or PR_TITLE. Exit 0 pass / 2 fail.

    Blank ``PR_TITLE`` (GitHub Actions on push) is omitted: this is the PR
    spec machine check, so no title means skip, not ``empty PR title``.
    Explicit ``--title ""`` still fails.
    """
    import os
    import sys
    from pathlib import Path

    env: Mapping[str, str] = os.environ if environ is None else environ
    err = sys.stderr if stderr is None else stderr
    resolved_scopes = scopes
    if resolved_scopes is None and root is not None:
        yaml_path = Path(root) / "forge.yaml"
        if yaml_path.is_file():
            from forge.apply import ForgeError, load_config

            try:
                resolved_scopes = load_config(yaml_path).title_scopes
            except ForgeError:
                resolved_scopes = None
    resolved = resolve_arg_or_env(title, env, "PR_TITLE")
    if resolved is None:
        return EXIT_OK
    code, message, _parts = lint_title(resolved, scopes=resolved_scopes)
    if code != EXIT_OK:
        print(message, file=err)
    return code
