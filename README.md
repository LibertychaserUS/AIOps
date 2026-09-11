# AIOps

[中文说明](README.zh-CN.md)

Public workshop for two reusable GitHub products: **Forge** (who may push / merge) and **Overlay** (reviewable tests; CI runs only `armed` suites). Not the empty First-Light `AIOps` repo. Learning Guide is a fixture, not the product. Neither deploys. Neither replaces an adopter’s existing build gate (Learning Guide Verify is the first example of that rule).

**Other agents: start in this file, or [README.zh-CN.md](README.zh-CN.md).** Pin **published** tags only. Do not pin floating `main`. Do not copy `forge/`, `overlay/`, `schema/`, or `prompts/` into a product git repo.

| Product | Pin this tag | SHA | Job |
|---|---|---|---|
| **Overlay** | [`overlay-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/overlay-v1.0.0) | `235e514e673fa68b24879c8e139f2a5c6633ebb5` | Inbox → reviewable suites. Push runs only `armed`. No `generate`. |
| **Forge** | [`forge-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/forge-v1.0.0) | same SHA | Local `check` then `submit` opens a draft PR. Humans + Ruleset merge. Never auto-merges. |

`main` may already contain unreleased `1.0.1` code (`pyproject.toml`). **Tags `overlay-v1.0.1` / `forge-v1.0.1` do not exist until a human publishes them** ([`docs/release.md`](docs/release.md)). Agents must pin **v1.0.0**. Do not `git checkout overlay-v1.0.1`. Do not pin `main`. GitHub Latest is one badge; pin the two tags, not Latest.

Need: CPython **3.12+**. Clone this repo (or your fork) **beside** the product repo.

---

## 30 seconds

1. **Forge** decides who can push / open a PR, which paths are denied, and which **CI job names** must be green. It does not merge.
2. **Overlay** decides which requirement leaves become reviewable suites. CI runs only **`armed`**. `draft` / `blocked` are not red.
3. Clone this repo next to the product, `git checkout overlay-v1.0.0` (or `forge-v1.0.0` — same commit), `python3 -m pip install -r requirements.txt`, set `PYTHONPATH`, then `python -m forge check` and `python -m overlay validate`.
4. Agents may `check` / `submit`. Agents must **not** live-`apply` Rulesets, fill `reviewed_by`, or flip a suite to `armed`.

```text
../AIOps/        # this workshop or your fork — tool source stays here
./my-product/    # adopter git: thin yaml + inbox/suites only
```

---

## Native skills — standard paths (one agent at a time)

Canonical packages live in [`skills/*/SKILL.md`](skills/) ([Agent Skills](https://agentskills.io/specification): frontmatter `name` + `description`; `name` = folder). `use-forge` / `use-overlay` teach `python -m forge` / `python -m overlay` with `PYTHONPATH` to this workshop. Do not vendor `forge/` or `overlay/` into a product repo.

This workshop already symlinks the same packages into each product’s **project** path. Opening **this** repo is enough. To import into **another** product repo, use that product’s path only (sibling checkout `../AIOps`, pin a tag, not `main`).

### Codex

Spec: [Codex Agent Skills](https://developers.openai.com/codex/skills). Codex scans `.agents/skills` from `$CWD` up to the git root.

| Scope | Standard path |
|---|---|
| This workshop (already wired) | [`.agents/skills/use-forge`](.agents/skills/use-forge)、[`.agents/skills/use-overlay`](.agents/skills/use-overlay) |
| Other product repo (project) | `.agents/skills/<name>/SKILL.md` |
| Your machine (all repos) | `~/.agents/skills/<name>/SKILL.md` |

```text
# other product repo — Codex project path (all five skills)
mkdir -p .agents/skills
for s in use-forge use-overlay design-cases dev-pr manage-repo; do
  ln -s ../../AIOps/skills/$s .agents/skills/$s
done

# or all repos on this machine
mkdir -p ~/.agents/skills
for s in use-forge use-overlay design-cases dev-pr manage-repo; do
  ln -s /abs/path/to/AIOps/skills/$s ~/.agents/skills/$s
done

# GitHub CLI — Codex host id is `codex` (not `copilot`).
# `--agent github-copilot` also writes `.agents/skills` at project scope.
gh skill install LibertychaserUS/AIOps --agent codex --pin overlay-v1.0.0 --all
```

(`gh skill` host ids: `codex`, `cursor`, `claude-code`, `github-copilot`. There is no `--agent copilot`. Several hosts share `.agents/skills` at project scope.)

### Cursor

Spec: [Cursor Agent Skills](https://cursor.com/docs/skills). Prefer `.cursor/skills/`. Cursor also loads `.agents/skills/` and, for compatibility, `.claude/skills/`.

| Scope | Standard path |
|---|---|
| This workshop (already wired) | [`.cursor/skills/use-forge`](.cursor/skills/use-forge)、[`.cursor/skills/use-overlay`](.cursor/skills/use-overlay) |
| Other product repo (project) | `.cursor/skills/<name>/SKILL.md` |
| Your machine (all local workspaces) | `~/.cursor/skills/<name>/SKILL.md` |

```text
# other product repo — Cursor project path
mkdir -p .cursor/skills
for s in use-forge use-overlay design-cases dev-pr manage-repo; do
  ln -s ../../AIOps/skills/$s .cursor/skills/$s
done

# or all local workspaces
mkdir -p ~/.cursor/skills
for s in use-forge use-overlay design-cases dev-pr manage-repo; do
  ln -s /abs/path/to/AIOps/skills/$s ~/.cursor/skills/$s
done

gh skill install LibertychaserUS/AIOps --agent cursor --pin overlay-v1.0.0 --all
```

Cloud Agents only see **project** skills in the repo, or `~/.cursor/skills` if you turn on Sync Skills. UI: Customize → Skills, or add this GitHub repo as a remote skill source.

### Claude Code

Spec: project `.claude/skills/<name>/SKILL.md`, user `~/.claude/skills/<name>/SKILL.md`.

| Scope | Standard path |
|---|---|
| This workshop (already wired) | [`.claude/skills/use-forge`](.claude/skills/use-forge)、[`.claude/skills/use-overlay`](.claude/skills/use-overlay) |
| Other product repo (project) | `.claude/skills/<name>/SKILL.md` |
| Your machine (all repos) | `~/.claude/skills/<name>/SKILL.md` |

```text
# other product repo — Claude Code project path
mkdir -p .claude/skills
for s in use-forge use-overlay design-cases dev-pr manage-repo; do
  ln -s ../../AIOps/skills/$s .claude/skills/$s
done

# or all repos on this machine
mkdir -p ~/.claude/skills
for s in use-forge use-overlay design-cases dev-pr manage-repo; do
  ln -s /abs/path/to/AIOps/skills/$s ~/.claude/skills/$s
done

gh skill install LibertychaserUS/AIOps --agent claude-code --pin overlay-v1.0.0 --all
```

Restart the agent after adding paths. Then `/use-forge` or `/use-overlay`, or let it pick from the description.

---

## 1. What you are allowed to change

| Lives in this workshop (or your fork) | Lives in the product repo |
|---|---|
| `forge/`, `overlay/`, `schema/`, `prompts/` | `forge.yaml` and/or `overlay.yaml` |
| reusable `.github/workflows/overlay.yml` | `inbox/`, `suites/`, optional `invariants.yaml` |
| skills and docs | reusable: `uses: LibertychaserUS/AIOps/.github/workflows/overlay.yml@overlay-v1.0.0`. If the product already has an inline `overlay-check.yml`, keep it — do not replace a working inline job with the reusable workflow. |

Local CLI: `PYTHONPATH=../AIOps`. Do not `git add` the tool tree so imports work. When the product repo has no `overlay/__init__.py`, the reusable workflow checkouts `tool_repository` (default `LibertychaserUS/AIOps`) into `_aiops`. That checkout is the correct reuse path.

---

## 2. Overlay — start using

Skill (read next): [`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md).

States: `draft` (AI/human draft, not run) · `blocked` (reviewed, not ready) · `armed` (reviewed and claimed testable). Agents never write `reviewed_by` and never arm. CI never auto-arms. No generate on push. This workshop’s Learning Guide **fixture** keeps login/payment `blocked`. A real product may already have those suites `armed` — copy the product’s `suite.yaml`, not the fixture status.

### In this workshop (smoke)

```text
git clone https://github.com/LibertychaserUS/AIOps.git
cd AIOps
git checkout overlay-v1.0.0
python3 -m pip install -r requirements.txt
python3 -m overlay validate --root .
python3 -m overlay cover --root .
python3 -m overlay select --branch main --root .
python3 -m unittest discover -s tests/overlay -t . -q
```

Use `-t .` so `tests/overlay` does not shadow the `overlay` package.

### In a product repo (first hour)

1. Checkout this workshop next door. `git checkout overlay-v1.0.0`.
2. In the product repo add `overlay.yaml` (copy shape from this workshop’s [`overlay.yaml`](overlay.yaml); set `product.repo` to **that** product).
3. Add one `inbox/<id>.md` (one slice, one id). Contract: [`docs/inbox.md`](docs/inbox.md). `function_id` is whatever stable unique string the adopter docs already use — do not invent `REQ-n`.
4. Hand-write `suites/<id>/` (`suite.yaml` starts `draft`). 1.0.x has **no** `generate`. Cover method: [`skills/design-cases/SKILL.md`](skills/design-cases/SKILL.md).
5. A human (not the agent) sets `blocked` or `armed` and writes `reviewed_by`.
6. Validate, then pin CI:

```text
cd my-product
PYTHONPATH=../AIOps python3 -m overlay validate --root .
PYTHONPATH=../AIOps python3 -m overlay cover --root .
PYTHONPATH=../AIOps python3 -m overlay select --branch main --root .
```

```yaml
# .github/workflows/overlay-check.yml  (product repo — do not copy forge/ or overlay/)
name: overlay-check
on: [push, pull_request]
jobs:
  overlay:
    uses: LibertychaserUS/AIOps/.github/workflows/overlay.yml@overlay-v1.0.0
    with:
      enable_run: true
      tool_repository: LibertychaserUS/AIOps
      tool_ref: overlay-v1.0.0
```

If the product already has an **inline** `overlay-check.yml` (checkout the pin, then `python -m overlay …`), keep it. Do not replace a working inline job with this reusable caller. If you forked the workshop, point `uses:`, `tool_repository`, and `tool_ref` at **your fork** and a pin. Never checkout `First-Light-TechHK/LearningGuidePortal`. Never `workflow_call` a product Verify job.

Worked fixture (not something to vendor): [`examples/learning-guide/`](examples/learning-guide/).

---

## 3. Forge — start using

Skill (read next): [`skills/use-forge/SKILL.md`](skills/use-forge/SKILL.md).

- **Dev:** `python -m forge check` must be green **and** `FORGE_SUBMIT_TOKEN` must be set, then `python -m forge submit` pushes a feature branch and opens/updates a **draft** PR. Host `gh auth` / `GH_TOKEN` is not enough. Missing token fails even `--dry-run`. Forge never merges.
- **Ops:** `python -m forge apply` installs a Ruleset from `forge.yaml` (`required_checks` → `required_status_checks`). Humans merge after required checks. No live apply to LearningGuidePortal from this workshop.

### In this workshop (smoke)

```text
git checkout forge-v1.0.0
python3 -m forge check --root . --title "docs(docs/agent): example title" --body "$(cat .github/PULL_REQUEST_TEMPLATE.md)"
python3 -m forge sop-lock --root .
python3 -m unittest discover -s tests/forge -t . -q
python3 -m forge apply --repo LibertychaserUS/AIOps --dry-run
```

### In a product repo (first hour)

1. Copy [`forge/forge.example.yaml`](forge/forge.example.yaml) → product `forge.yaml`. Set `protect`, `deny_paths`, and `required_checks` to the adopter’s **actual GitHub check / job names** (the names that appear on a PR). The example lists `Verify` only because this workshop’s example job is called that. Learning Guide uses `Typecheck` / `Lint` / `Build and test` / `overlay-check`. Do not copy `Verify` unless that is the real job name.
2. Paste policy **text** from [`forge/agent-policy.md`](forge/agent-policy.md) into the product `AGENTS.md`. Do not copy the `forge/` directory.
3. From the product cwd, after `pip install -r requirements.txt` in the tool checkout:

```text
cd my-product
PYTHONPATH=../AIOps python3 -m forge check --root .
```

4. Live `forge apply` is **Ops only** ([`skills/manage-repo/SKILL.md`](skills/manage-repo/SKILL.md)). Agents may `--dry-run` if a human asked; they never live-apply. Learning Guide does not live-apply.
5. Land code: green `forge check` + `FORGE_SUBMIT_TOKEN` + `forge submit`. Token details: [`docs/submit-credential.md`](docs/submit-credential.md). PR title: `type(product/actor): subject` (see below).

---

## 4. PR title and body (this workshop and adopters who install the check)

```text
type(product/actor): subject
```

- type: `build|chore|ci|docs|feat|fix|perf|refactor|style|test|revert`
- product: `forge|overlay|ci|docs`
- actor: `dev|admin|agent`

Body needs these six headings, verbatim: `做了什么` / `为什么` / `动了哪些门` / `怎么验` / `不做什么` / `分工`. Spec: [`docs/pr-brief.md`](docs/pr-brief.md). Template: [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).

**通用检查 ≠ 产品门.** In **this workshop**, common CI is `.github/workflows/ci.yml` (jobs `pr-title` + `sop-lock`). Forge / Overlay product doors stay in `forge-check.yml` / `overlay-check.yml`. Required check names are unchanged. Adopters do **not** copy this workshop `ci.yml`; Overlay adopters still pin reusable `overlay.yml` from a thin product-repo `overlay-check.yml`. `pr-title` and `sop-lock` always run. `overlay-check` / `forge-check` are selected via `forge.yaml` `ci` (skip = success).

PRs into `main` are a capstone: squash, then start the next branch from the **new** `main` SHA. Do not stack on a `cursor/` head that is about to be squashed.

---

## 5. Skills (Codex / Agent Skills)

| Read this | When |
|---|---|
| [`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md) | Adopt Overlay, write inbox/suites, wire overlay CI |
| [`skills/use-forge/SKILL.md`](skills/use-forge/SKILL.md) | Adopt Forge — six-step cold start, then `check` / `submit`. Live `apply` is `$manage-repo` only. |
| [`skills/design-cases/SKILL.md`](skills/design-cases/SKILL.md) | Case cover (triad + invariants) |
| [`skills/dev-pr/SKILL.md`](skills/dev-pr/SKILL.md) | Agent/developer lands a PR |
| [`skills/manage-repo/SKILL.md`](skills/manage-repo/SKILL.md) | Humans: Ruleset, merge, arm/block |
| [`docs/sop.md`](docs/sop.md) | Index |
| [`docs/products.md`](docs/products.md) | Full adopt / do-not-vendor rules |
| [`docs/design.md`](docs/design.md) | Implementer source of truth |
| [`AGENTS.md`](AGENTS.md) | Hard constraints for agents in **this** repo |

Codex also loads `.agents/skills/` (symlinks to `skills/`).

---

## 6. Never

- Do not change LearningGuidePortal Verify. Do not clone `First-Light-TechHK/LearningGuidePortal` from here.
- Do not attach, run, or gate intern-workspace Proctor. Do not edit Deepseek3.
- Do not press production (`ilovelearningguide.com`). No CD.
- Do not vendor the tool into a product commit repo.
- Do not generate on push. Do not auto-arm. Do not write receipts or `reviewed_by` as a model.
- Do not self-merge, self-approve, or treat CodeRabbit as the only merge gate.
- Do not live-apply Forge to LearningGuidePortal.

---

## 7. What the published 1.0.0 pin does not include

Overlay `generate` is not shipped. There is no “drop a PRD, get reviewed cases today” loop yet — hand-write suites. Forge `apply` is live only when a human runs it with an admin token; this workshop’s CI is dry-run only. Guard workflow is a later slice. Unreleased `main` may already say 1.0.1 in `pyproject.toml`. **Do not checkout tags that are not on GitHub.** A human publishes `overlay-v1.0.1` / `forge-v1.0.1` later (`forge release` / Actions `release`). Until those tags exist, pin **v1.0.0**.

## 8. Publish after merge (not production CD)

Spec: [`docs/release.md`](docs/release.md). After squash/merge to `main`:

```text
python3 -m forge release --repo LibertychaserUS/AIOps --version 1.0.1 --dry-run
# or Actions: workflow "release" → Run workflow → version=1.0.1, products=both
```

Does not deploy. Does not run on push. Does not merge.
