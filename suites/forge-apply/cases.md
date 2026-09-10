# Forge dry-run

## FN-forge-apply Dry-run writes nothing

### Functional
- Title: dry-run prints payload
- Steps: `python -m forge apply --repo LibertychaserUS/AIOps --path forge.yaml --dry-run`
- Expected: exit 0; payload mentions forge-protected-default; no API write

### Negative
- Title: apply without token
- Steps: unset FORGE_GITHUB_TOKEN and GITHUB_TOKEN; apply without --dry-run
- Expected: exit 2; no partial write

### Edge
- Title: LearningGuidePortal is refused
- Steps: apply --repo First-Light-TechHK/LearningGuidePortal
- Expected: rejected; product Verify untouched
