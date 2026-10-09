---
temperature: 0
---

You write Overlay cases for one suite. Reply with one JSON object and no markdown fence.

Schema:
{"title":"<short suite title>","functions":[{"id":"<same id>","heading":"<rest of the h2>","functional":"<text>","negative":"<text>","edge":"<text>"}]}

Rules:
- Keep every id from the extract step, in the same order.
- Each function needs non-empty functional, negative, and edge text.
- Do not set suite status. The compiler writes status active.
- Output is only the JSON object.
