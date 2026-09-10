# AIOps

Public workshop for two reusable GitHub products: **Forge** (ordered PRs) and **Overlay** (reviewable tests; CI runs only `armed` suites). Not the empty First-Light `AIOps` repo. Learning Guide is a fixture, not the product. Neither deploys. Neither replaces an adopter’s existing build gate (Learning Guide Verify is the first example of that rule).

**Other agents: start in this file.** Pin the two product tags. Do not pin floating `main`. Do not copy `forge/`, `overlay/`, `schema/`, or `prompts/` into a product git repo.

| Product | Pin this tag | Release | Job |
|---|---|---|---|
| **Overlay** | [`overlay-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/overlay-v1.0.0) | [Overlay 1.0.0](https://github.com/LibertychaserUS/AIOps/releases/tag/overlay-v1.0.0) | Inbox → reviewable suites. Push runs only `armed`. No `generate` in 1.0.0. |
| **Forge** | [`forge-v1.0.0`](https://github.com/LibertychaserUS/AIOps/releases/tag/forge-v1.0.0) | [Forge 1.0.0](https://github.com/LibertychaserUS/AIOps/releases/tag/forge-v1.0.0) | Local `check` then `submit` opens a draft PR. Humans + Ruleset merge. Never auto-merges. |

These are **two tags**. GitHub allows only one **Latest** badge per repository, so `/releases/latest` currently lands on Forge. Overlay is not missing; open the Overlay link above. After a squash/merge onto `main`, retarget both tags (or cut `v1.0.1`) onto the new `main` SHA — do not pin `main`.

Need: CPython **3.12+**. Clone this repo (or your fork) **beside** the product repo.

```text
../AIOps/        # this workshop or your fork — tool source stays here
./my-product/    # adopter git: thin yaml + inbox/suites only
```

---

## 1. What you are allowed to change

| Lives in this workshop (or your fork) | Lives in the product repo |
|---|---|
| `forge/`, `overlay/`, `schema/`, `prompts/` | `forge.yaml` and/or `overlay.yaml` |
| reusable `.github/workflows/overlay.yml` | `inbox/`, `suites/`, optional `invariants.yaml` |
| skills and docs | one thin workflow: `uses: LibertychaserUS/AIOps/.github/workflows/overlay.yml@overlay-v1.0.0` |

Local CLI: `PYTHONPATH=../AIOps`. Do not `git add` the tool tree so imports work. When the product repo has no `overlay/__init__.py`, the reusable workflow checkouts `tool_repository` (default `LibertychaserUS/AIOps`) into `_aiops`. That checkout is the correct reuse path.

---

## 2. Overlay — start using

Skill (read next): [`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md).

States: `draft` (AI/human draft, not run) · `blocked` (reviewed, not ready — payment/login stay here) · `armed` (reviewed and claimed testable). Agents never write `reviewed_by` and never arm. CI never auto-arms. No generate on push.

### In this workshop (smoke)

```text
git clone https://github.com/LibertychaserUS/AIOps.git
cd AIOps
git checkout overlay-v1.0.0
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
4. Hand-write `suites/<id>/` (`suite.yaml` starts `draft`). 1.0.0 has **no** `generate`. Cover method: [`skills/design-cases/SKILL.md`](skills/design-cases/SKILL.md).
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

If you forked the workshop, point `uses:`, `tool_repository`, and `tool_ref` at **your fork** and a pin. Never checkout `First-Light-TechHK/LearningGuidePortal`. Never `workflow_call` a product Verify job.

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

1. Copy [`forge/forge.example.yaml`](forge/forge.example.yaml) → product `forge.yaml`. Set `protect`, `deny_paths` (the adopter’s **existing** build workflow name).
2. Paste policy **text** from [`forge/agent-policy.md`](forge/agent-policy.md) into the product `AGENTS.md`. Do not copy the `forge/` directory.
3. Dry-run apply from the product cwd:

```text
cd my-product
PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml --dry-run
```

4. A human with Administration runs live `apply`. Agents do not.
5. Land code: green `forge check` + `FORGE_SUBMIT_TOKEN` + `forge submit`. PR title: `type(product/actor): subject` (see below).

---

## 4. PR title and body (this workshop and adopters who install the check)

```text
type(product/actor): subject
```

- type: `build|chore|ci|docs|feat|fix|perf|refactor|style|test|revert`
- product: `forge|overlay|ci|docs`
- actor: `dev|admin|agent`

Body needs these six headings, verbatim: `做了什么` / `为什么` / `动了哪些门` / `怎么验` / `不做什么` / `分工`. Spec: [`docs/pr-brief.md`](docs/pr-brief.md). Template: [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).

**通用检查 ≠ 产品门.** `pr-title` and `sop-lock` always run. `overlay-check` / `forge-check` are selected via `forge.yaml` `ci` (skip = success).

PRs into `main` are a capstone: squash, then start the next branch from the **new** `main` SHA. Do not stack on a `cursor/` head that is about to be squashed.

---

## 5. Skills (Codex / Agent Skills)

| Read this | When |
|---|---|
| [`skills/use-overlay/SKILL.md`](skills/use-overlay/SKILL.md) | Adopt Overlay, write inbox/suites, wire overlay CI |
| [`skills/use-forge/SKILL.md`](skills/use-forge/SKILL.md) | Adopt Forge, check / submit / apply |
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

## 7. What 1.0.0 does not include

Overlay `generate` is not shipped. There is no “drop a PRD, get reviewed cases today” loop yet — hand-write suites. Forge `apply` is live only when a human runs it with an admin token; this workshop’s CI is dry-run only. Guard workflow is a later slice.
