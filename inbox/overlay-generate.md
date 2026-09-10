---
id: overlay-generate
kind: user-case
readiness: not-ready
source:
  repo: LibertychaserUS/AIOps
  path: docs/design.md
  ref: 1f78cf58ce03dba187a784488a5ef37eab39abc7
packages:
  - overlay
locale: zh-CN
---

# Intent

generate turns one inbox into a draft suite. The command is specified but not shipped. Cases may exist; the suite stays blocked.

# In scope

- FN-overlay-generate Draft output only; never writes armed; never runs on push.

# Out of scope

- Auto-arm.
- Token spend on push.

# User cases

1. FN-overlay-generate A future generate over an armed suite refuses unless --force-draft.

# Notes

readiness: not-ready. Humans keep status blocked so overlay-check stays green.
