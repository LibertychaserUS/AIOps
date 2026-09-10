# Registration and Authentication

This is a scoped test spec, not a mirror of Registration_Authentication_PRD.
Status stays `blocked` so Overlay does not run these cases and does not go red.

## REQ-1 Valid session sees own data

### Functional
- Title: Signed-in user opens a protected page
- Steps: Use a valid session; open a protected page
- Expected: Own data only

### Negative
- Title: No session
- Steps: Open the same page signed out
- Expected: Rejected; no other user's data

### Edge
- Title: Expired session
- Steps: Open the page with an expired session
- Expected: Rejected; no stale user data
