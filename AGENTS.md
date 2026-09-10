# AIOps

Workshop for two reusable products: **Forge** (ordered GitHub collab) and **Overlay** (testgen + armed CI). Learning Guide is the first fixture, not the product. Not Proctor.

- Do not change LearningGuidePortal Verify.
- Do not attach/run/gate the intern workspace Proctor from here.
- Do not edit Deepseek3.
- Do not press production (`ilovelearningguide.com`).
- Do not couple Forge/Overlay core to one product’s routes, domains, or numbering.
- Overlay freezes the contract: fields, states, and the product-agnostic `function_id` grammar. Do not bake one product’s routes, domains, or FR catalog into Overlay core.
- `function_id`: `^[A-Z]{2,8}(-[A-Z]{1,6})?-[0-9]{2,3}$`. Same id as the PRD function across unit/integration/smoke/k6/e2e. Deprecate `REQ-n`. Do not invent `E2E-B1` / `UT-007`.
- Constraints: `docs/2026-09-10-对话整理.md`. Full design: `docs/design.md`.
- Test-system skill: `docs/agents/ieee-test-system.md`. Compile skill: `docs/agents/overlay-contract.md`.
