---
id: login
kind: prd
readiness: not-ready
source:
  repo: First-Light-TechHK/LearningGuidePortal
  path: docs/phase1/source-prd/Registration_Authentication_PRD_v1.0_0814.docx
  ref: pin-me
packages:
  - modules/user-registration
locale: zh-CN
---

# Intent

Registration and session. Cases may exist; the suite must stay `blocked` so the overlay check does not go red.

# In scope

- Draft cases for login and session user paths.

# Out of scope

- Using login as a merge gate.
- Changing LearningGuidePortal Verify.

# User cases

1. A user with a valid session opens a protected page and sees their own data.

# Notes

`readiness: not-ready` is a hint only. After review, humans mark the suite `blocked`, never `armed`. Excerpt only; do not vendor the docx.
