# Payment Management

This is a scoped test spec, not a mirror of Payment_Management_PRD.
Status stays `blocked` so Overlay does not run these cases and does not go red.

## REQ-1 Entitlement updates after a configured payment

### Functional
- Title: Configured payment completes
- Steps: Complete the already-configured payment path
- Expected: Entitlement state updates for that user

### Negative
- Title: Incomplete payment
- Steps: Abandon checkout before completion
- Expected: Entitlement unchanged

### Edge
- Title: Repeat confirmation of a completed payment
- Steps: Open the completed payment again
- Expected: No second entitlement grant
