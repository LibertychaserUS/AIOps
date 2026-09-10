# My Learning — overview and progress

## REQ-1 Overview lists entitled courses

### Functional
- Title: Entitled user sees active access
- Steps: Sign in; open `/en-GB/my-learning`
- Expected: Courses with access appear; progress is an integer 0–100

### Negative
- Title: Signed-out user is rejected
- Steps: Open `/en-GB/my-learning` with no session
- Expected: Redirect or unauthorised; no other user's data

### Edge
- Title: Zero progress still listed when access exists
- Steps: Entitled course with no study events
- Expected: Row exists; progress 0
