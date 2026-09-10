# Overlay select and run

## FN-overlay-select Select armed only and run their commands

### Functional
- Title: main selects armed functional suites
- Steps: `python -m overlay select --branch main --root .`
- Expected: overlay-select is printed; blocked suites are not
- Title: CI run executes this suite's product_command
- Steps: `python -m overlay run --branch main --root . --write-receipt receipts/`
- Expected: armed commands run; receipt `wrote_by: run`; blocked suites are not executed

### Negative
- Title: blocked does not redden preview or run
- Steps: Keep overlay-generate blocked; run select then run on main
- Expected: dropped with never_red_statuses; exit 0 unless an armed command fails

### Edge
- Title: unknown branch is empty and green
- Steps: select or run a branch not listed in overlay.yaml
- Expected: empty set; not a failure
