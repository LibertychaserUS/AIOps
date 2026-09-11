<!-- inbox-readiness: not-ready -->
# Overlay generate (blocked)

## FN-overlay-generate Generate is not on the push path

### Functional
- Title: generate writes a suite
- Steps: future `python -m overlay generate --inbox inbox/overlay-select.md`
- Expected: status active or omitted (default active); does not set blocked

### Negative
- Title: no generate on push
- INV-no-generate-on-push
- Steps: inspect overlay-check and overlay.yml
- Expected: no generate job; no model token

### Edge
- Title: refuse to clobber an existing suite
- Steps: generate onto an existing suite without --force
- Expected: non-zero; suite status unchanged
