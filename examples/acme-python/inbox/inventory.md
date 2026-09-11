---
id: inventory
kind: user-case
readiness: ready
source:
  repo: acme/inventory
  path: docs/prd/inventory.md
  ref: pin-me
packages:
  - inventory
---

# Intent

Warehouse clerks reserve stock for a known SKU without going negative.

# In scope

- INV-01 Reserve reduces on-hand quantity for a known SKU.
- INV-02 Missing SKU or non-positive quantity is rejected.

# Out of scope

- Purchasing, payments, or production hosts.

# User cases

1. INV-01 Clerk reserves 1 unit of sku-1; remaining quantity is 2.
2. INV-02 Clerk reserves a missing SKU or quantity 0; the command fails and stock is unchanged.

# Notes

Ready to gate. Suite stays `active`. Isolation of unready work would be `blocked` with a linked reason.
