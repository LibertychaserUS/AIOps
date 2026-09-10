# AIOps

Workshop for two reusable products: **Forge** (ordered GitHub collab) and **Overlay** (testgen + armed CI). Learning Guide is the first fixture, not the product. Not Proctor.

**Start:** public README [`README.md`](README.md) § Native skills. Standard paths — Codex: `.agents/skills/` / `~/.agents/skills/`; Cursor: `.cursor/skills/` / `~/.cursor/skills/`; Claude Code: `.claude/skills/` / `~/.claude/skills/`. Pin `overlay-v1.0.1` / `forge-v1.0.1` after publish. Do not vendor the tool.

- Do not change LearningGuidePortal Verify.
- Do not attach/run/gate the intern workspace Proctor from here.
- Do not edit Deepseek3.
- Do not press production (`ilovelearningguide.com`).
- Do not couple Forge/Overlay core to one product’s routes, domains, or numbering.
- Overlay freezes the contract (fields, states, leaf id rules). Adopter docs pick the strings and tree shapes. Agents read those docs and compile into `schema/`.
- Do not require `REQ-n`, `ML-FR-*`, `PAY-01`, `LOGIN-01`, or `^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$` in kernel/schema. `function_id` is a free, stable, unique, non-whitespace string.
- Constraints: `docs/2026-09-10-对话整理.md`. Full design: `docs/design.md`.
- Use Forge: `skills/use-forge/SKILL.md`. Use Overlay: `skills/use-overlay/SKILL.md`. Design cases: `skills/design-cases/SKILL.md`. SOP index: `docs/sop.md`.
- PR review and merge: GitHub humans + Ruleset, not Overlay, not a portal. 开发侧先 `python -m forge check` 绿，且持有 `FORGE_SUBMIT_TOKEN`（环境变量 `FORGE_SUBMIT_TOKEN`；`gh auth` 不够），才能 `python -m forge submit` 代推开 PR（无凭证含 `--dry-run` 也红）。Forge 不保管密钥。Ops 侧 GitHub required checks（合入锁）+ 人合。Overlay「token 只在 generate」是模型密钥，不是 GitHub 写权限。RBAC: `docs/rbac.md`. 管理端: `skills/manage-repo/SKILL.md`. 开发端: `skills/dev-pr/SKILL.md`. Agents do not self-merge, self-approve, or write `reviewed_by`.
- PR 标题必须过 `python -m forge pr-title`：Conventional Commits `type(product/actor): subject`（product: `forge`\|`overlay`\|`ci`\|`docs`；actor: `dev`\|`admin`\|`agent`）。CI 检查名 `pr-title`。仓内 SOP：`python -m forge sop-lock`（检查名 `sop-lock`）。原则：`docs/sop-lock.md`。正文六节：`做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`。规格：`docs/pr-brief.md`。模板：`.github/PULL_REQUEST_TEMPLATE.md`。不绿不能合。不要发明分支 / workflow / skill 前缀；`cursor/…-6842` 保持原样。标题 `actor` 不是 merge 权限。正文「分工」是人，不是标题。
- Skills are Codex / Agent Skills `SKILL.md` (frontmatter `name` + `description`; `name` matches the directory). Codex also loads `.agents/skills/` (symlinks to `skills/`).
- Reuse on another product: keep the tool in this workshop or a **fork**. Do not vendor `forge/`, `overlay/`, `schema/`, `prompts/`, or this workshop’s Python packages into the adopter’s product commit repo. Product repo: thin `forge.yaml` / `overlay.yaml` + `inbox/` + `suites/` + optional `invariants.yaml` + a workflow that `uses:` this repo’s reusable workflow (pin a tag or SHA, not floating `main`). Local CLI: `PYTHONPATH` to a sibling checkout. See `docs/products.md`.
- Compile method: `docs/agents/overlay-contract.md`. Case design / cover: `skills/design-cases/SKILL.md` (old path `docs/agents/case-design.md`). IEEE profile (id / level / trace, not 20 Word docs): `docs/agents/ieee-test-system.md`.
- This repo is also an Overlay adopter: root `overlay.yaml` + `inbox/` + `suites/`. **通用检查 ≠ 产品门.** Common CI (`pr-title`, `sop-lock`) always runs. Product CI (`overlay-check` = validate + select + run Overlay armed; `forge-check` = Forge unit + apply --dry-run) starts then skip-with-success via `forge.yaml` `ci`. Overlay test and Overlay CI are the same Overlay gate. Do not arm `forge-apply` on Overlay run. Local `overlay/` here is correct **because this is the tool repo** — adopters must not copy that package.
