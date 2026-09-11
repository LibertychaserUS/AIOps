# AIOps

[中文权威文档](README.zh-CN.md)

Two installable GitHub tools in one workshop: **Forge** (who may push / open a PR; humans merge) and **Overlay** (reviewable test suites; CI runs `active`, drops `blocked`). Neither deploys. Neither replaces an adopter’s existing build gate. Do not vendor `forge/` or `overlay/` into a product repo.

Need **CPython 3.12+**. Clone this repo (or your fork) **beside** the product repo. Pin a **published tag**, never floating `main`. Current pins and Ruleset state: [`docs/STATE.md`](docs/STATE.md) (generated). Chinese design source: [`docs/design.md`](docs/design.md).

---

## 30 seconds

Forge keeps people and agents from pushing protected branches. Overlay turns requirement leaves into suites with `### Functional` / `### Negative` / `### Edge`. `blocked` suites must cite a link; they never redden Overlay CI.

```text
git clone <this-workshop> /tmp/AIOps && cd /tmp/AIOps
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps

cd /path/to/product
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m forge check --root .
```

CLI reference (generated, do not copy lists by hand): [`docs/cli.md`](docs/cli.md).

---

## Install skills

Canonical packages: [`skills/*/SKILL.md`](skills/). Host ids: `codex`, `cursor`, `claude-code`, `github-copilot`.

```text
gh skill install <owner>/<workshop> --agent cursor --pin overlay-v2.0.0 --all
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
| [`CHANGELOG.md`](CHANGELOG.md) | overlay-2.0.0 / forge-1.1.0 |
| [`examples/acme-python/`](examples/acme-python/) | Minimal adopter (not a product fixture) |

Never pin `main`. Never self-merge. Never treat CodeRabbit as the only merge gate.
