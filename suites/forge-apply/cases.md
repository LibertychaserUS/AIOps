# Forge dry-run

## FN-forge-apply Dry-run writes nothing

### Functional
- Title: dry-run prints payload
- Steps: `python -m forge apply --repo LibertychaserUS/AIOps --path forge.yaml --dry-run`
- Expected: exit 0; payload mentions forge-protected-default; no API write
- Title: Forge product gate runs unit tests then dry-run when selected
- Steps: `.github/workflows/forge-check.yml` starts, `python -m forge ci-select --check forge-check`, then (if selected) `unittest discover -s tests/forge` and `forge apply --dry-run`
- Expected: skip is success when selector says skip; when run: fake-API tests green; dry-run exit 0; Overlay select does not run this suite
- Title: conventional PR title with product/actor passes
- Steps: `python -m forge pr-title --title "feat(overlay/dev): add cover triad and invariants"`
- Expected: exit 0; no GitHub write

### Negative
- Title: empty or unscoped PR title fails
- Steps: `python -m forge pr-title --title ""` ; `python -m forge pr-title --title "feat(overlay): missing actor"`
- Expected: exit 2
- Title: apply without token
- Steps: unset FORGE_GITHUB_TOKEN and GITHUB_TOKEN; apply without --dry-run
- Expected: exit 2; no partial write
- Title: Forge does not flip Overlay status
- INV-forge-does-not-arm
- Steps: inspect apply payload and agent-policy
- Expected: no suite.yaml write; no status change

### Edge
- Title: a repo in forbidden_live_repos is refused
- Steps: apply --repo example-org/production-app with that repo in forbidden_live_repos
- Expected: rejected; the product build workflow is untouched

## FN-forge-submit 开发侧代推

### Functional
- Title: dry-run with FORGE_SUBMIT_TOKEN does not push
- Steps: set FORGE_SUBMIT_TOKEN to a dummy; `python -m forge submit --repo LibertychaserUS/AIOps --title "feat(forge/dev): add submit middleware" --dry-run`
- Expected: exit 0 after green `forge check`; prints head, title, six body headings, `would require FORGE_SUBMIT_TOKEN`; no push; token value not printed
- FN-forge-apply stays the apply leaf
- FN-forge-check is the local gate submit runs first

### Negative
- Title: submit protect branch is refused
- Steps: submit with head `main`
- Expected: exit 3; no push
- Title: submit without FORGE_SUBMIT_TOKEN (including dry-run)
- Steps: unset FORGE_SUBMIT_TOKEN; GITHUB_TOKEN and FORGE_GITHUB_TOKEN may be set; submit --dry-run and live
- Expected: exit 2; missing FORGE_SUBMIT_TOKEN; no push
- Title: red check blocks submit even with token
- INV-local-check-before-submit
- Steps: FORGE_SUBMIT_TOKEN set; submit with a check_fn that returns 2, dry-run and live
- Expected: exit 2; refusing (local check is red); no push; no PR; token not printed

### Edge
- Title: submit onto the upstream fixture is refused
- Steps: submit --repo <upstream fixture listed in FORBIDDEN_REPOS>
- Expected: rejected; no push
- Title: fake live submit never merges
- Steps: submit with FORGE_SUBMIT_TOKEN against FakeGitHub
- Expected: POST draft PR; second call PATCH; no `/merge`; token not in PR body

## FN-forge-check 提交前本地门

### Functional
- Title: workshop check is green
- Steps: `python -m forge check --root . --title "feat(forge/dev): add submit middleware"`
- Expected: exit 0; checklist includes overlay validate, cover, pr-title, schema/check.py
- FN-forge-submit calls this gate before push

### Negative
- Title: check failure blocks submit
- INV-local-check-before-submit
- Steps: submit dry-run and live with a red check_fn
- Expected: exit 2; no push; no PR

### Edge
- Title: adopter root without overlay.yaml or schema/ skips those steps
- Steps: temp product root; title provided; no schema/
- Expected: overlay validate/cover skip; schema skip; pr-title runs; exit 0 if title ok

## FN-forge-sop-lock Decidable SOP is program-locked

### Functional
- Title: workshop sop-lock is green
- Steps: `python -m forge sop-lock --root .`
- Expected: exit 0; required_checks list overlay-check, pr-title, forge-check, sop-lock
- FN-forge-apply dry-run stays the apply leaf; this leaf locks SOP files

### Negative
- Title: generate on push is red
- INV-no-generate-on-push
- INV-sop-decidable
- Steps: a fixture workflow `on: push` runs `python -m overlay generate`
- Expected: `sop-lock` exit 2
- Title: skill without ## Lock is red
- Steps: skills/x/SKILL.md has no Lock heading
- Expected: exit 2

### Edge
- Title: comment "No generate" on push is green
- Steps: push workflow whose only generate token is a comment
- Expected: not a generate-on-push failure
- Title: Overlay-bypass unittest discover on push is red
- Steps: a `self-test` workflow runs `unittest discover` on push
- Expected: exit 2; Overlay tests stay in Overlay active `product_command`; Forge tests stay on `forge-check`
