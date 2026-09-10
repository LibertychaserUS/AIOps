---
id: my-learning
source:
  repo: First-Light-TechHK/LearningGuidePortal
  path: docs/phase1/source-prd/My_Learning_PRD_v1.0_0814.docx
  ref: pin-me
kind: prd
packages:
  - modules/my-learning
  - "app/[locale]/account"
---

Paste a short user-case or PRD excerpt here. Do not vendor the 700KB+ docx.

Known first-slice split:

- Ready enough to arm after review: My Learning overview / progress for entitled courses
  (product already ships `/my-learning` and related routes).
- Must stay blocked after review: payment, login, Stripe webhook, live entitlement
  grant from the browser return page.
