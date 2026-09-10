---
id: example-inbox
kind: prd
readiness: ready
source:
  repo: owner/name
  path: docs/prd.md
  ref: abc123def456
packages:
  - web
locale: zh-CN
---

# Intent

What this inbox is asking Overlay to turn into cases.

# In scope

- FN-first-path First user-visible path.

# Out of scope

- Payment and login.

# User cases

1. A signed-in user opens the first page and sees their own data.

# Notes

Pinned `source.ref`. An In scope line may carry an adopter-minted id.
Do not put `status` or `reviewed_by` here.
