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
