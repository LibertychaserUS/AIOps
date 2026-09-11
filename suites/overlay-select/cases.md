# Overlay select and run

## FN-overlay-select Select active only and run their commands

### Functional
- Title: main selects active functional suites
- Steps: `python -m overlay select --branch main --root .`
- Expected: overlay-select is printed; blocked suites are not
- Title: CI run executes this suite's product_command
- Steps: `python -m overlay run --branch main --root . --write-receipt receipts/`
- Expected: active commands run; receipt `wrote_by: run`; blocked suites are not executed
- INV-receipt-not-model wrote_by is select or run, never model

### Negative
- Title: blocked does not redden preview or run
- INV-never-red-blocked
- Steps: Keep overlay-generate (FN-overlay-generate) blocked; run select then run on main
- Expected: dropped with never_red_statuses; exit 0 unless an active command fails

### Edge
- Title: unknown branch falls back to main (or branches.default) and stays green
- Steps: select or run a branch not listed in overlay.yaml
- Expected: fallback note printed; uses branches.default then main; not a failure
- Title: command hitting a forbidden host is not started
- INV-no-prod-host
- Steps: active product_command contains a forbid_hosts URL
- Expected: exit 2; command does not run
