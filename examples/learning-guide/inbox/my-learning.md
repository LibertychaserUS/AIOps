---
id: my-learning
kind: prd
readiness: ready
source:
  repo: First-Light-TechHK/LearningGuidePortal
  path: docs/phase1/source-prd/My_Learning_PRD_v1.0_0814.docx
  ref: pin-me
packages:
  - modules/my-learning
  - "app/[locale]/account"
locale: zh-CN
---

# Intent

Signed-in first page: My Learning. This is Overlay's first fixture inbox, not the product core.

# In scope

- ML-FR-004 Course cards on the My Learning overview.
- ML-FR-007 Unique Learning Point progress 0–100.

# Out of scope

- Payment (see `inbox/payment.md`).
- Login page itself (see `inbox/login.md`). Session gate is `AUTH-01`.

# User cases

1. A signed-in user opens My Learning and sees their own progress, not someone else's.

# Notes

Excerpt only. Do not vendor the docx. Replace `source.ref` with a commit SHA before a real generate. Payment and login inboxes are `not-ready`. Ids are copied from Learning Guide tests (`ML-FR-004-006-course-cards.test.ts`, `ML-FR-007-unique-lp-progress.test.ts`), not invented here.
