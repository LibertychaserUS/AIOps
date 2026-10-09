# AIOps

[中文权威文档](README.zh-CN.md)

Two installable GitHub tools in one workshop: **Forge** (who may push / open a PR; humans merge) and **Overlay** (reviewable test suites; CI runs `active`, drops `blocked`). Neither deploys. Neither replaces an adopter’s existing build gate. Do not vendor `forge/` or `overlay/` into a product repo.

Need **CPython 3.12+**. Clone this repo (or your fork) **beside** the product repo. Pin a **published tag that already exists**, never floating `main`. Current published pins: `overlay-v2.0.0` / `forge-v1.1.3`. **Forge is a second checkout** — `overlay-v2.0.0` still peels Forge 1.1.0 (empty-root `check` is fake-green). Do not use GitHub Release **Latest** as a pin (it may still show `forge-v1.0.0`). Ruleset state: [`docs/STATE.md`](docs/STATE.md) (generated). Chinese entry: [`README.zh-CN.md`](README.zh-CN.md).

---

## 30 seconds

Forge keeps people and agents from pushing protected branches. Overlay turns requirement leaves into suites with `### Functional` / `### Negative` / `### Edge`. Do not write `### Depth` or `## Specified`. `blocked` suites must cite a link; they never redden Overlay CI.

```text
git clone <this-workshop> /tmp/AIOps && cd /tmp/AIOps
git checkout overlay-v2.0.0
# Forge CLI is a second pin: git checkout forge-v1.1.3
# pip does not install a `forge` console script.
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps

cd /path/to/product
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m forge check --root .
```

`--root` must contain `forge.yaml` or `overlay.yaml` or `check` exits 2. Use `python3 -m`. On `forge-v1.1.2`, do not set an empty `PR_TITLE` on `push`; `1.1.3` lints the HEAD subject instead.

CLI reference (generated, do not copy lists by hand): [`docs/cli.md`](docs/cli.md).

---

## Install skills

Canonical packages: [`skills/*/SKILL.md`](skills/). Host ids: `codex`, `cursor`, `claude-code`, `github-copilot`.

```text
gh skill install <owner>/<workshop> --agent cursor --pin overlay-v2.0.0 use-overlay design-cases
gh skill install <owner>/<workshop> --agent cursor --pin forge-v1.1.3 use-forge manage-repo dev-pr
```

Or symlink `skills/*` into `.agents/skills`, `.cursor/skills`, or `.claude/skills`. Live `forge apply` is Ops only (`$manage-repo`).

---

## Canonical docs (Chinese)

| Doc | What |
|---|---|
| [`README.zh-CN.md`](README.zh-CN.md) | Chinese entry |
| [`docs/design.md`](docs/design.md) | Design |
| [`docs/migration-v2.md`](docs/migration-v2.md) | Upgrade from 1.0.x |
| [`docs/adr/`](docs/adr/) | Decisions |
| [`CHANGELOG.md`](CHANGELOG.md) | published: overlay-2.0.0 / forge-1.1.3 |
| [`examples/acme-python/`](examples/acme-python/) | Minimal adopter (not a product fixture) |

Never pin `main`. Never self-merge. Never treat CodeRabbit as the only merge gate.

Overlay reusable `branch` defaults to empty: a pull request uses the base ref; a push uses a configured Overlay branch, then `branches.default`, then `main` only when that git ref is not configured. See [`docs/overlay-ci.md`](docs/overlay-ci.md).
