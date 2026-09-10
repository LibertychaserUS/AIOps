<!-- inbox-readiness: not-ready -->
# Overlay generate (blocked)

## FN-overlay-generate Draft only

### Functional
- Title: generate writes draft
- Steps: future `python -m overlay generate --inbox inbox/overlay-select.md`
- Expected: status draft; reviewed_by empty

### Negative
- Title: no generate on push
- Steps: inspect overlay-check and overlay.yml
- Expected: no generate job; no model token

### Edge
- Title: refuse to clobber armed
- Steps: generate onto an armed suite without --force-draft
- Expected: non-zero; suite stays armed
