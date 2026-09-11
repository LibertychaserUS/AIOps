---
name: use-forge
description: Developer cold start for Forge — pin a published tag, pip install, write thin forge.yaml, run python -m forge check, then submit a draft PR. Live apply and Rulesets belong to manage-repo. Do not use for Overlay inbox or suites (use use-overlay). Do not auto-merge. Do not submit when local check is red.
metadata:
  short-description: Six-step Forge cold start; no live apply
---

# Use Forge

Forge is the developer gate: local `check`, then `submit` (draft PR). It does not generate tests, must not edit Overlay `status`, and **does not merge**.

**Who reviews and merges:** GitHub humans + Ruleset. RBAC: [`docs/rbac.md`](../../docs/rbac.md). **开发端** after this skill: [`../dev-pr/SKILL.md`](../dev-pr/SKILL.md). **管理端** (live `apply`, required checks, merge, Overlay arm/block): [`../manage-repo/SKILL.md`](../manage-repo/SKILL.md). Agents: [`forge/agent-policy.md`](../../forge/agent-policy.md) — no self-merge, no self-approve.

Pin **published** tags only: `overlay-v1.0.1` / `forge-v1.0.1` (same commit). Do not pin `main`. Do not force-move `1.0.0`. Start: [`../../README.md`](../../README.md) / [`../../README.zh-CN.md`](../../README.zh-CN.md).

## First run vs default-run

Forge is **full-stack post-dev GitHub landing** (`check` → `submit`). It is not a test tool. Do not change Overlay or Verify norms to “make Forge work.”

**Init vs later — do not silently replace the adopter’s process.**

1. **If they already have a landing path** (`gh pr create`, husky, push-to-main, Verify-only, their own branch names): **remind and inform** them of the Forge norm, then **wait for confirmation** before initializing (`forge.yaml`, policy paste, making `submit` the landing path). Do not write those files or switch the path on a silent assumption.

2. **Initialization needs more interaction than later runs.** Contrast old vs new. State what Forge **will** do (local `check`, then `submit` as the GitHub landing) and what it **will not** do: no merge, no live `apply`, no Overlay arm, no Verify rewrite. Get an **explicit yes** before steps 3–4 below.

3. **After one confirmation:** later in this session — and in later sessions if a marker exists (product already has `forge.yaml` **and** they said 同意) — **ask once**. If they agree, say 「之后默认按 Forge 落地」 and **default-run** `check` / `submit` without re-explaining the constitution.

4. Never ask on every file save. Never treat init confirm as permission to live-apply Rulesets or arm Overlay.

## Real CLI

`python -m forge --help` today:

`apply` `status` `check` `submit` `pr-title`/`title` `sop-lock` `ci-select` `ops-review` `bounce` `release`

There is **no** `brief`, `credential`, `ops-chain`, or `revoke` subcommand. Do not invent them. Token rules: [`docs/submit-credential.md`](../../docs/submit-credential.md).

| Action | Agent | Human / Ops |
|---|---|---|
| `forge check` | yes | — |
| `forge submit` | yes, with `FORGE_SUBMIT_TOKEN` | — |
| live `forge apply` | **no** | Ops (`$manage-repo`). Learning Guide **does not** live-apply |
| write `reviewed_by` / `armed` | **no** | human review |

`FORGE_SUBMIT_TOKEN` is the submit key. Ops `FORGE_GITHUB_TOKEN` is the Ruleset key. Do not mix them. `gh auth` / `GITHUB_TOKEN` are not enough.

## Lock / 不绿不能合

原则：[`docs/sop-lock.md`](../../docs/sop-lock.md)。只锁可机器判定的子集。

- **代推锁：** `python -m forge check` 必须绿 **并且** 持有非空 `FORGE_SUBMIT_TOKEN`。缺密钥或 check 红：`submit`（含 `--dry-run`）退出 2。细节只看 [`docs/submit-credential.md`](../../docs/submit-credential.md)。
- GitHub required checks 锁合入，不锁提交。`required_checks` 必须是 **CI job / check 名**（PR 页面上看到的字符串），不是 workflow `name:`，除非两者相同。
- **通用检查 ≠ 产品门。** `pr-title` / `sop-lock` 是通用检查；`overlay-check` / `forge-check` 是产品门。
- 进 `main` 默认 squash：**封顶**再压，压完**换底**。`submit` base 是 `protect`。
- 不绿不能提交。不绿不能合。Agent 不 live-apply。

## Instructions

Stay imperative. Six cold-start steps. Live apply is **not** in this list. Steps 3–4 are **initialization** — only after First run vs default-run is satisfied.

### 1. Checkout a published pin beside the product

```text
git clone https://github.com/LibertychaserUS/AIOps.git /tmp/AIOps
cd /tmp/AIOps
git checkout overlay-v1.0.1
```

`forge-v1.0.1` is the same commit. Need CPython **3.12+**. Do not vendor `forge/` into the product git repo.

### 2. Install Python deps

```text
python3 -m pip install -r requirements.txt
export PYTHONPATH=/tmp/AIOps
```

### 3. Write thin `forge.yaml` — job names, not workflow names

Copy [`forge/forge.example.yaml`](../../forge/forge.example.yaml). Set `protect`, `agent_branch_prefixes`, `deny_paths`.

`required_checks` = the adopter’s **actual GitHub check / job names**:

| Repo | `required_checks` |
|---|---|
| This workshop | `overlay-check` / `pr-title` / `forge-check` / `sop-lock` |
| Learning Guide | `Typecheck` / `Lint` / `Build and test` / `overlay-check` |
| Example file | `Verify` — only if that is the real job name |

Do not copy `Verify` into Learning Guide. Do not invent a product Verify name.

### 4. Paste policy text; do not copy `forge/`

Copy wording from [`forge/agent-policy.md`](../../forge/agent-policy.md) into the product `AGENTS.md`. “Copy these files” means **text**, not `git add forge/`.

### 5. `python -m forge check` from the product cwd

```text
cd /path/to/product
PYTHONPATH=/tmp/AIOps python3 -m forge check --root .
```

If the product has `overlay.yaml`, check also runs `overlay validate` + `overlay cover`. Red → stop. Do not push. Do not submit.

Overlay contract that turns this red: [`../use-overlay/SKILL.md`](../use-overlay/SKILL.md) (triad headings, unique `function_id`, invariants cite `##` titles).

### 6. Submit a draft PR only when check is green

Hold `FORGE_SUBMIT_TOKEN`. Then [`../dev-pr/SKILL.md`](../dev-pr/SKILL.md):

```text
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(forge/dev): subject" --dry-run
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/NAME --title "feat(forge/dev): subject"
```

Never merge. Never approve. Never arm. Never live-apply.

If a human asked you to **diagnose** a Ruleset, `--dry-run` apply is allowed. Live apply is `$manage-repo` only. Never apply to `First-Light-TechHK/LearningGuidePortal`. Learning Guide Ops does not live-apply in Phase 1.

Guard workflow is later. Overlay CI: if the product already has an inline `overlay-check.yml`, keep it — do not replace it with a reusable `uses:` caller.

## Examples

```text
# Product cwd, tool at /tmp/AIOps @ overlay-v1.0.1
PYTHONPATH=/tmp/AIOps python3 -m forge check --root . --title "feat(overlay/dev): fix armed select"
# submit requires FORGE_SUBMIT_TOKEN even on --dry-run
PYTHONPATH=/tmp/AIOps python3 -m forge submit --repo OWNER/PRODUCT --title "feat(overlay/dev): fix armed select" --dry-run
```

Illegal: `git checkout` a tag that is not on GitHub. Illegal: `git add forge/` in the product repo. Illegal: live `forge apply` as an agent. Illegal: `python -m forge revoke` / `brief` / `credential` / `ops-chain`. Illegal: `required_checks: [Verify]` on a repo whose jobs are `Typecheck` / `Lint` / `Build and test`.

## Performance Notes

`check` is local. `submit` is one push + one draft PR. No model. Token details stay in [`docs/submit-credential.md`](../../docs/submit-credential.md). Humans publish tags with `$manage-repo` `python -m forge release` ([`docs/release.md`](../../docs/release.md)) — agents do not invent tags.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想把 `forge/` 拷进产品仓好 import | 停。工具留在 `/tmp/AIOps` 或 fork；产品仓只留 `forge.yaml`。本地用 `PYTHONPATH`。 |
| checkout `overlay-v1.0.1` 失败 | `git fetch --tags` 后再 pin `overlay-v1.0.1`。不要 pin `main`。 |
| 退出码 2 | 缺 `FORGE_SUBMIT_TOKEN`，或本机 `forge check` 红。不要用 `GITHUB_TOKEN` / `gh auth` 凑。 |
| `forge check` 因 Overlay 契约红 | 叶子必须 `### Functional` / `### Negative` / `### Edge`。不要 `### Depth`。不要 `## Specified`。`$use-overlay`。 |
| 抄了 `required_checks: Verify` 但对不上 CI | 改成 PR 上真实的 job 名。 |
| 想 live apply / 直推 main | 停。`$manage-repo` / `$dev-pr`。Learning Guide 现在不 apply。 |
| 想让 Forge 把 suite 标 armed | 停。人审 Overlay。`$manage-repo`。 |
| 把 `FORGE_SUBMIT_TOKEN` 和 Ops 钥匙搅在一起 | 停。代推看 [`docs/submit-credential.md`](../../docs/submit-credential.md)。 |
| 接入方已有 `gh pr create` / husky / 直推 main / 只走 Verify | 先提醒对照新旧，等人明确同意再写 `forge.yaml`。不要默默替换。 |
| 每次存盘都想再讲一遍 Forge 宪法 | 停。同意过一次（或已有 `forge.yaml` 且说过同意）就默认跑 `check` / `submit`。初始化同意 ≠ live-apply / arm。 |
