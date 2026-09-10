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
- Use Forge: `skills/use-forge/SKILL.md`. Use Overlay: `skills/use-overlay/SKILL.md`. SOP index: `docs/sop.md`.
- Compile skill: `docs/agents/overlay-contract.md`. Case design / cover: `docs/agents/case-design.md`. IEEE profile (id / level / trace, not 20 Word docs): `docs/agents/ieee-test-system.md`.
- This repo is also an Overlay adopter: root `overlay.yaml` + `inbox/` + `suites/`; CI job `overlay-check` (validate + select + run). Test and CI are the same gate.
