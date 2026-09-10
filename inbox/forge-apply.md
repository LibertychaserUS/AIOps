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
- FN-forge-submit `submit --dry-run` prints the intended remote branch + PR title/body headings, exits 0, and does not push.
- FN-forge-sop-lock `sop-lock` reddens when a decidable skill SOP is violated.

# Out of scope

- Live apply to LearningGuidePortal.
- forge-guard.yml (later slice).

# User cases

1. FN-forge-apply Missing token on a real apply exits 2 and writes nothing.
2. FN-forge-submit Missing token on a live submit exits 2 and does not push.
3. FN-forge-sop-lock A push workflow that runs overlay generate exits 2.

# Notes

This repo may dry-run from overlay-check. Live apply needs an admin token and is not part of overlay-check.
