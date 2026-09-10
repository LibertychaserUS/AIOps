# Forge dry-run

## FN-forge-apply Dry-run writes nothing

### Functional
- Title: dry-run prints payload
- Steps: `python -m forge apply --repo LibertychaserUS/AIOps --path forge.yaml --dry-run`
- Expected: exit 0; payload mentions forge-protected-default; no API write
- Title: CI run executes forge unit tests then dry-run
- Steps: overlay-check `product_command` for this suite
- Expected: fake-API tests green; dry-run exit 0; no Ruleset write
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
- Title: Forge does not arm Overlay
- INV-forge-does-not-arm
- Steps: inspect apply payload and agent-policy
- Expected: no suite.yaml write; no reviewed_by; no status change

### Edge
- Title: LearningGuidePortal is refused
- Steps: apply --repo First-Light-TechHK/LearningGuidePortal
- Expected: rejected; product Verify untouched

## FN-forge-submit 开发侧代推

### Functional
- Title: dry-run does not push
- Steps: `python -m forge submit --repo LibertychaserUS/AIOps --title "feat(forge/dev): add submit middleware" --dry-run`
- Expected: exit 0; prints head, title, six body headings; no push
- FN-forge-apply stays the apply leaf

### Negative
- Title: submit protect branch is refused
- Steps: submit with head `main`
- Expected: exit 3; no push
- Title: live submit without token
- Steps: unset tokens; submit without --dry-run
- Expected: exit 2; no push

### Edge
- Title: LearningGuidePortal submit is refused
- Steps: submit --repo First-Light-TechHK/LearningGuidePortal
- Expected: rejected; no push
- Title: fake live submit never merges
- Steps: submit with token against FakeGitHub
- Expected: POST draft PR; second call PATCH; no `/merge`

## FN-forge-sop-lock Decidable SOP is program-locked

### Functional
- Title: workshop sop-lock is green
- Steps: `python -m forge sop-lock --root .`
- Expected: exit 0; required_checks list overlay-check, pr-title, sop-lock
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
- Title: unittest discover on push is red
- Steps: a `self-test` workflow runs `unittest discover` on push
- Expected: exit 2; tests belong in armed product_command
