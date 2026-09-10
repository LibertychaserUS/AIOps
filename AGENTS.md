# AIOps

Workshop for two reusable products: **Forge** (ordered GitHub collab) and **Overlay** (testgen + armed CI). Learning Guide is the first fixture, not the product. Not Proctor.

- Do not change LearningGuidePortal Verify.
- Do not attach/run/gate the intern workspace Proctor from here.
- Do not edit Deepseek3.
- Do not press production (`ilovelearningguide.com`).
- Do not couple Forge/Overlay core to one product’s routes, domains, or numbering.
- Overlay freezes the contract (fields, states, leaf id rules). Adopter docs pick the strings and tree shapes. Agents read those docs and compile into `schema/`.
- Do not require `REQ-n`, `ML-FR-*`, `PAY-01`, `LOGIN-01`, or `^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$` in kernel/schema. `function_id` is a free, stable, unique, non-whitespace string.
- Constraints: `docs/2026-09-10-对话整理.md`. Full design: `docs/design.md`.
- Use Forge: `skills/use-forge/SKILL.md`. Use Overlay: `skills/use-overlay/SKILL.md`. Design cases: `skills/design-cases/SKILL.md`. SOP index: `docs/sop.md`.
- PR review and merge: GitHub humans + Ruleset, not Overlay, not a portal. RBAC: `docs/rbac.md`. 管理端: `skills/manage-repo/SKILL.md`. 开发端: `skills/dev-pr/SKILL.md`. Agents do not self-merge, self-approve, or write `reviewed_by`.
- PR 名分工只写 GitHub **标题前缀** `[<role>][<product>]`（role: `管理`|`开发`|`agent`；product: `Forge`|`Overlay`|`CI`|`docs`）+ 正文六节（`做了什么` `为什么` `动了哪些门` `怎么验` `不做什么` `分工`）。规格：`docs/pr-brief.md`。模板：`.github/PULL_REQUEST_TEMPLATE.md`。开发写，管理拒收无规格。不要发明分支 / workflow / skill 前缀；`cursor/…-6842` 保持原样。标题前缀不是 merge 权限。正文「分工」是人，不是前缀。
- Skills are Codex / Agent Skills `SKILL.md` (frontmatter `name` + `description`; `name` matches the directory). Codex also loads `.agents/skills/` (symlinks to `skills/`).
- Reuse on another product: keep the tool in this workshop or a **fork**. Do not vendor `forge/`, `overlay/`, `schema/`, `prompts/`, or this workshop’s Python packages into the adopter’s product commit repo. Product repo: thin `forge.yaml` / `overlay.yaml` + `inbox/` + `suites/` + optional `invariants.yaml` + a workflow that `uses:` this repo’s reusable workflow (pin a tag or SHA, not floating `main`). Local CLI: `PYTHONPATH` to a sibling checkout. See `docs/products.md`.
- Compile method: `docs/agents/overlay-contract.md`. Case design / cover: `skills/design-cases/SKILL.md` (old path `docs/agents/case-design.md`). IEEE profile (id / level / trace, not 20 Word docs): `docs/agents/ieee-test-system.md`.
- This repo is also an Overlay adopter: root `overlay.yaml` + `inbox/` + `suites/`; CI job `overlay-check` (validate + select + run). Test and CI are the same gate. Local `overlay/` here is correct **because this is the tool repo** — adopters must not copy that package.
