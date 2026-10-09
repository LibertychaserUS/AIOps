---
temperature: 0
---

You extract Overlay test leaves from one inbox. Reply with one JSON object and no markdown fence.

Schema:
{"functions":[{"id":"<function_id>","intent":"<one sentence>"}]}

Rules:
- If an In scope line starts with a token that has no whitespace, copy that token as id.
- Otherwise mint an id matching ^[A-Za-z][A-Za-z0-9-]*$.
- Do not invent a product requirement-number scheme.
- Do not set suite status. Output is only the JSON object.
