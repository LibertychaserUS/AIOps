# Overlay select preview

## FN-overlay-select Select armed only

### Functional
- Title: main selects armed functional suites
- Steps: `python -m overlay select --branch main --root .`
- Expected: overlay-select is printed; blocked suites are not

### Negative
- Title: blocked does not redden preview
- Steps: Keep overlay-generate blocked; run select on main
- Expected: dropped with never_red_statuses; exit 0

### Edge
- Title: unknown branch is empty and green
- Steps: select a branch not listed in overlay.yaml
- Expected: empty set; not a failure
