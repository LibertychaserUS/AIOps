---
name: use-forge
description: Install and operate Forge (开发侧 submit 代推 PR; Ops apply/status + required checks + human merge) without vendoring the tool into a product repo. This skill should be used when adopting Forge, writing forge.yaml, running forge submit/apply/status, pasting agent policy, or asking how people and agents land code. Do not use for Overlay inbox or suites (use use-overlay). Do not auto-merge.
metadata:
  short-description: Install Forge without vendoring the tool
---

# Use Forge

Forge is a standard part: 开发侧 `submit`（代推 draft PR）+ Ops Ruleset / `apply` + optional guard. It does not generate tests, must not edit Overlay `status`, and **does not merge**.

**Who reviews and merges:** GitHub humans + Ruleset, not Overlay, not a portal. RBAC: [`docs/rbac.md`](../../docs/rbac.md). **管理端** (apply, required checks, CODEOWNERS, merge, Overlay arm/block; do not push for developers): [`../manage-repo/SKILL.md`](../manage-repo/SKILL.md). **开发端** (`forge submit`, fix armed-red, no live apply, no self-merge): [`../dev-pr/SKILL.md`](../dev-pr/SKILL.md). Agents: this SOP + [`forge/agent-policy.md`](../../forge/agent-policy.md) — no self-merge, no self-approve.

## Lock / 不绿不能合

原则：skill 里能机器判的标准，程序不绿不能合。见 [`docs/rbac.md`](../../docs/rbac.md)。只锁可机器判定的子集，不 NLP 扫散文。

- LearningGuidePortal apply/submit 拒绝、dry-run 不写 API：`python -m forge apply --dry-run` / `python -m forge submit --dry-run` + Forge 单测 → CI **`overlay-check`**
- PR 标题：`python -m forge pr-title` → CI **`pr-title`**
- 仓级 SOP（若已装）：`python -m forge sop-lock` → **`sop-lock`**
- 不绿不能合。人审：谁合、要不要 live apply、别的仓有没有 vendor 工具。

## Instructions

Follow these steps. Stay imperative. Do not invent a second constitution.

### Reuse — keep the tool out of the product commit repo

Do not upload or vendor the tool into the adopter's product git repo (the repo they commit and push). 不要把工具上传到接入方要提交、推送的产品仓。

| Keep here | Never `git add` into the product tree |
|---|---|
| This workshop `LibertychaserUS/AIOps`, **or** the adopter's **fork** of this workshop | `forge/`, `overlay/`, `schema/`, `prompts/`, this workshop's Python packages |

The product repo commits **only** thin files:

- `forge.yaml` (copy from `forge/forge.example.yaml`, then edit `protect` / `deny_paths`)
- a thin workflow that `uses:` the reusable workflow from the **tool** repo — pin a **tag or commit SHA**, not floating `main`
- optional: pasted policy text in `AGENTS.md`, `.github/CODEOWNERS` from the examples

Local CLI: checkout the tool repo or fork **beside** the product. Set `PYTHONPATH` to that checkout. Do **not** copy `forge/` into the product tree so imports work, and do not submodule-vendor the packages.

```text
# sibling checkouts — product git must not contain the tool tree
../AIOps/          # LibertychaserUS/AIOps or your fork
./my-product/      # adopter product repo (only thin files)

cd my-product
PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml --dry-run
```

CI reuse path: `uses: LibertychaserUS/AIOps/.github/workflows/forge-guard.yml@<tag-or-sha>` (guard is a later slice). If you forked the workshop, `uses:` **your fork** at a pin. Never pin floating `main`.

### Install / apply

1. **Read the adopter repo first.** Add only `forge.yaml` (from `forge/forge.example.yaml`). Set `protect`, `agent_branch_prefixes`, `deny_paths` (the existing build workflow; never invent a product Verify name unless the adopter already has one).
2. **Paste policy text**, do not invent a second constitution, and do not vendor `forge/`. Copy the wording from [`forge/agent-policy.md`](../../forge/agent-policy.md) into the adopter `AGENTS.md`.
3. **Dry-run before write.** Run from the product cwd with `PYTHONPATH` pointing at the tool checkout (see above).
   ```text
   PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml --dry-run
   ```
   Must print the payload and `copy these files`. Exit 0. No API write. "Copy these files" means paste policy / CODEOWNERS **text**, not `git add forge/`.
4. **Apply only with an admin token** (`FORGE_GITHUB_TOKEN` or `GITHUB_TOKEN`, Administration: write). Never apply to `First-Light-TechHK/LearningGuidePortal` from this workshop. Never apply in Overlay CI. Humans run apply; agents do not live-apply. That human is **管理端** (`$manage-repo`).
   ```text
   PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/NAME --path forge.yaml
   PYTHONPATH=../AIOps python3 -m forge status --repo OWNER/NAME
   ```
5. **Humans and agents land the same way:** `python -m forge submit --repo OWNER/NAME [--title T] [--dry-run]`. Dry-run prints the intended remote branch + PR title + body headings and does not push. Live submit needs a token, still never merges, never applies a Ruleset. No push to protected branches. No self-merge. No self-approve. Do not edit the adopter’s existing build workflow. Developers follow `$dev-pr`. Merge is a GitHub click after checks are green — `$manage-repo`, not Forge CI. Aligns with [`gh pr create`](https://cli.github.com/manual/gh_pr_create), not a Graphite clone.
6. **Do not touch Overlay gates.** Forge must not write `reviewed_by`, receipts, or `status: armed`. Agents must not arm.
7. **Required checks** stay the adopter’s names (their build job, plus `overlay-check` only if they installed Overlay, plus `pr-title` if they installed the title workflow). This workshop lists `overlay-check` and `pr-title`. Forge does not create those jobs. Title lock: `python -m forge pr-title` — [`../../docs/pr-brief.md`](../../docs/pr-brief.md).

Guard workflow is later. First slice is Ruleset + policy + CLI.

### Never

- Do not vendor `forge/` / `overlay/` / `schema/` / `prompts/` into the product commit repo.
- Do not apply live to Learning Guide Portal. Do not press production (`ilovelearningguide.com`).
- Do not change LearningGuidePortal Verify. Do not attach / run / gate intern-workspace Proctor. Do not edit Deepseek3.
- Do not generate on push. Do not arm as an agent. Do not write receipts / `reviewed_by`.
- CI only; no CD. Two products stay independent: Forge does not write Overlay `status`.
- Do not build an admin Web or a second RBAC database. Review/merge stay on GitHub (`$manage-repo`).

## Examples

```text
# This workshop (it IS the tool repo — local forge/ is correct here only)
python3 -m forge apply --repo LibertychaserUS/AIOps --path forge.yaml --dry-run
python3 -m forge submit --repo LibertychaserUS/AIOps --title "feat(forge/dev): add submit" --dry-run

# Another product (tool stays next door)
PYTHONPATH=../AIOps python3 -m forge apply --repo OWNER/PRODUCT --path forge.yaml --dry-run
PYTHONPATH=../AIOps python3 -m forge submit --repo OWNER/PRODUCT --title "feat(overlay/dev): fix armed select" --dry-run
```

Product workflow (when guard exists), pin a tag or SHA:

```yaml
# .github/workflows/forge-guard.yml  — thin caller only
name: forge-guard
on: pull_request
jobs:
  guard:
    uses: LibertychaserUS/AIOps/.github/workflows/forge-guard.yml@<tag-or-sha>
```

Illegal: `apply --repo First-Light-TechHK/LearningGuidePortal`. Illegal: apply on `on: push` Overlay jobs. Illegal: `git add forge/` inside the product repo.

## Performance Notes

Dry-run is local JSON. Live apply is one GET + one POST or PUT. No model. No CD. Token only on explicit apply, never on Overlay push.

## Troubleshooting

| 现象 | 处理 |
|---|---|
| 想把 `forge/` 拷进产品仓好 import | 停。工具留在本工作本或 fork；产品仓只留 `forge.yaml` + 薄 workflow。本地用 `PYTHONPATH`。 |
| 退出码 2 | 缺 token。不要部分写入。 |
| 退出码 3 | `forge.yaml` 非法。对照 example。 |
| 退出码 4 | GitHub API 失败。看权限，不要改 Ruleset JSON 结构凑合。 |
| 想直推 main 省事 | 停。`forge submit`。`$dev-pr`。 |
| 想让 Forge 把 suite 标 armed | 停。那是人审 Overlay。`$manage-repo`。 |
| 谁来 merge | GitHub 上的人 + Ruleset。见 [`docs/rbac.md`](../../docs/rbac.md)。 |
| 想对 LearningGuidePortal live apply | 停。fixture，不是试验场。 |
