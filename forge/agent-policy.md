# Forge agent policy (paste into the consuming repo AGENTS.md)

- Open a pull request. Do not push protected branches (`main` unless the repo lists others).
- Do not merge your own PR. Do not approve your own PR.
- Do not edit the consuming repo's existing build workflow (the Verify equivalent).
- Do not write Overlay `reviewed_by`, receipts, or change `status` to `armed`.
- Do not call production URLs. Do not deploy.
- You may `workflow_dispatch` Overlay `generate` when a human asked.
