"""Machine-decidable CI selector from forge.yaml.

Common checks always run. Product checks start, then skip-with-success
when the selector says skip. Title product facet wins on a valid
Conventional Commits title; otherwise changed paths decide.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from forge import EXIT_CONFIG, EXIT_OK
from forge.apply import ForgeError, parse_simple_yaml
from forge.title import lint_title

DEFAULT_COMMON = ("pr-title", "sop-lock")
DEFAULT_TITLE_MAP: dict[str, tuple[str, ...]] = {
    "overlay": ("overlay",),
    "forge": ("forge",),
    "ci": ("overlay", "forge"),
    "docs": (),
}
PRODUCT_NAMES = ("overlay", "forge")


@dataclass(frozen=True)
class ProductGate:
    name: str
    check: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class CiConfig:
    common: tuple[str, ...]
    products: dict[str, ProductGate]
    title_map: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Decision:
    check: str
    run: bool
    reason: str
    source: str
    products: tuple[str, ...]
    common: tuple[str, ...] = field(default_factory=tuple)


def _as_string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raise ForgeError(EXIT_CONFIG, f"illegal ci.{field}: expected a list")
    if not isinstance(value, list):
        raise ForgeError(EXIT_CONFIG, f"illegal ci.{field}: expected a list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ForgeError(EXIT_CONFIG, f"illegal ci.{field} item: {item!r}")
        out.append(item.strip())
    return out


def load_ci_config(root: Path, raw: dict[str, Any] | None = None) -> CiConfig:
    if raw is None:
        path = root / "forge.yaml"
        if not path.is_file():
            return CiConfig(
                common=DEFAULT_COMMON,
                products={},
                title_map={key: tuple(val) for key, val in DEFAULT_TITLE_MAP.items()},
            )
        try:
            raw = parse_simple_yaml(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ForgeError(EXIT_CONFIG, f"illegal forge.yaml: {exc}") from exc
    ci = raw.get("ci")
    if ci is None:
        return CiConfig(
            common=DEFAULT_COMMON,
            products={},
            title_map={key: tuple(val) for key, val in DEFAULT_TITLE_MAP.items()},
        )
    if not isinstance(ci, dict):
        raise ForgeError(EXIT_CONFIG, "illegal ci: expected a mapping")

    common = tuple(_as_string_list(ci.get("common"), "common") or list(DEFAULT_COMMON))
    products_raw = ci.get("products") or {}
    if not isinstance(products_raw, dict):
        raise ForgeError(EXIT_CONFIG, "illegal ci.products: expected a mapping")
    products: dict[str, ProductGate] = {}
    for name, spec in products_raw.items():
        product = str(name)
        if product not in PRODUCT_NAMES:
            raise ForgeError(EXIT_CONFIG, f"illegal ci.products key {product!r} (not a third product)")
        if not isinstance(spec, dict):
            raise ForgeError(EXIT_CONFIG, f"illegal ci.products.{product}: expected a mapping")
        check = spec.get("check")
        if not isinstance(check, str) or not check.strip():
            raise ForgeError(EXIT_CONFIG, f"illegal ci.products.{product}.check")
        paths = tuple(_as_string_list(spec.get("paths"), f"products.{product}.paths"))
        products[product] = ProductGate(name=product, check=check.strip(), paths=paths)

    title_map = {key: tuple(val) for key, val in DEFAULT_TITLE_MAP.items()}
    select = ci.get("select")
    if isinstance(select, dict):
        raw_title = select.get("title")
        if isinstance(raw_title, dict):
            for facet, mapped in raw_title.items():
                names = _as_string_list(mapped, f"select.title.{facet}")
                illegal = [item for item in names if item not in PRODUCT_NAMES]
                if illegal:
                    raise ForgeError(
                        EXIT_CONFIG,
                        f"illegal ci.select.title.{facet}: {illegal[0]!r} is not a product",
                    )
                title_map[str(facet)] = tuple(names)
    return CiConfig(common=common, products=products, title_map=title_map)


def path_matches(path: str, prefix: str) -> bool:
    rel = path.replace("\\", "/").lstrip("./")
    rule = prefix.replace("\\", "/").lstrip("./")
    if rule.endswith("/"):
        return rel == rule[:-1] or rel.startswith(rule)
    return rel == rule or rel.startswith(rule + "/")


def products_from_paths(paths: Sequence[str], products: Mapping[str, ProductGate]) -> tuple[str, ...]:
    hit: list[str] = []
    for name, gate in products.items():
        if any(path_matches(item, prefix) for item in paths for prefix in gate.paths):
            hit.append(name)
    return tuple(hit)


def products_from_title(title: str | None, title_map: Mapping[str, tuple[str, ...]]) -> tuple[tuple[str, ...] | None, str]:
    text = (title or "").strip()
    if not text:
        return None, "no-title"
    code, _, parts = lint_title(text)
    if code != EXIT_OK or parts is None:
        return None, "invalid-title"
    if parts.product not in title_map:
        return None, f"unknown-product:{parts.product}"
    return tuple(title_map[parts.product]), f"title:{parts.product}"


def git_changed(root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def select_products(
    config: CiConfig,
    *,
    title: str | None,
    changed: Sequence[str] | None,
) -> tuple[tuple[str, ...], str, str]:
    mapped, reason = products_from_title(title, config.title_map)
    if mapped is not None:
        return mapped, reason, "title"
    if changed is not None:
        return products_from_paths(changed, config.products), "paths", "paths"
    return tuple(config.products), "undecided-run-all", "default"


def decide(
    config: CiConfig,
    check: str,
    *,
    title: str | None,
    changed: Sequence[str] | None,
) -> Decision:
    products, reason, source = select_products(config, title=title, changed=changed)
    if check in config.common:
        return Decision(
            check=check,
            run=True,
            reason="common",
            source="common",
            products=products,
            common=config.common,
        )
    for gate in config.products.values():
        if gate.check == check:
            return Decision(
                check=check,
                run=gate.name in products,
                reason=reason,
                source=source,
                products=products,
                common=config.common,
            )
    return Decision(
        check=check,
        run=False,
        reason="unknown-check-skip",
        source="default",
        products=products,
        common=config.common,
    )


def format_decision(decision: Decision) -> str:
    products = ",".join(decision.products) if decision.products else "(none)"
    return (
        f"check: {decision.check}\n"
        f"run: {'true' if decision.run else 'false'}\n"
        f"reason: {decision.reason}\n"
        f"source: {decision.source}\n"
        f"products: {products}\n"
    )


def write_github_output(path: Path, decision: Decision) -> None:
    text = (
        f"run={'true' if decision.run else 'false'}\n"
        f"reason={decision.reason}\n"
        f"source={decision.source}\n"
        f"products={','.join(decision.products)}\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def run_ci_select(
    root: Path,
    *,
    check: str,
    title: str | None = None,
    changed: Sequence[str] | None = None,
    github_output: bool = False,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    env: Mapping[str, str] = {} if environ is None else environ
    root = root.resolve()
    resolved_title = title if title is not None else env.get("PR_TITLE")
    try:
        config = load_ci_config(root)
        if changed is None and products_from_title(resolved_title, config.title_map)[0] is None:
            changed = git_changed(root)
        decision = decide(config, check, title=resolved_title, changed=changed)
    except ForgeError as exc:
        print(exc.message, file=err)
        return exc.code
    print(format_decision(decision), end="", file=out)
    if github_output:
        dest = env.get("GITHUB_OUTPUT")
        if not dest:
            print("GITHUB_OUTPUT is unset", file=err)
            return EXIT_CONFIG
        write_github_output(Path(dest), decision)
    return EXIT_OK
