---
id: forge-apply
kind: user-case
readiness: ready
source:
  repo: LibertychaserUS/AIOps
  path: docs/design.md
  ref: 1f78cf58ce03dba187a784488a5ef37eab39abc7
packages:
  - forge
locale: zh-CN
---

# Intent

Forge apply on this workshop prints a Ruleset payload in dry-run and does not write GitHub.

# In scope

- FN-forge-apply `apply --dry-run` prints the payload, exits 0, and does not POST or PUT.
- FN-forge-submit `submit --dry-run` without `FORGE_SUBMIT_TOKEN` exits 2 (fail closed). With the named secret set, it prints the intended remote branch + PR title/body headings and does not push. Red `forge check` refuses submit.
- FN-forge-check `python -m forge check` is the local pre-submit gate. Red means no push and no PR.
- FN-forge-sop-lock `sop-lock` reddens when a decidable skill SOP is violated.

# Out of scope

- Live apply to LearningGuidePortal.
- forge-guard.yml (later slice).

# User cases

1. FN-forge-apply Missing token on a real apply exits 2 and writes nothing.
2. FN-forge-submit Missing `FORGE_SUBMIT_TOKEN` on submit (including `--dry-run`) exits 2 and does not push. `GITHUB_TOKEN` alone is not enough.
3. FN-forge-check A red check blocks submit dry-run and live push.
4. FN-forge-sop-lock A push workflow that runs overlay generate exits 2.

# Notes

This repo may dry-run from overlay-check. The armed command sets a dummy `FORGE_SUBMIT_TOKEN` so dry-run can stay green; that placeholder is not a live GitHub credential. Live apply needs an admin token (`FORGE_GITHUB_TOKEN`) and is not part of overlay-check. Live submit is not part of overlay-check.
