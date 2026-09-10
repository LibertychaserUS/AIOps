---
id: overlay-select
kind: user-case
readiness: ready
source:
  repo: LibertychaserUS/AIOps
  path: docs/design.md
  ref: 1f78cf58ce03dba187a784488a5ef37eab39abc7
packages:
  - overlay
locale: zh-CN
---

# Intent

This workshop uses Overlay on itself. Push and pull_request run validate + select + run. Only armed suites are selected; their product_command is the test gate.

# In scope

- FN-overlay-select `select --branch main` includes armed functional suites and drops draft/blocked.

# Out of scope

- FN-overlay-generate
- Calling a product Verify workflow.

# User cases

1. FN-overlay-select On main, a blocked suite does not appear in the selected list and does not fail the preview.

# Notes

Hand-written. generate is not in this slice. readiness is a hint only.
