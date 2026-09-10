from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LG = REPO / "examples" / "learning-guide"


def copy_lg(dest: Path) -> Path:
    root = dest / "root"
    shutil.copytree(LG, root)
    return root


def run_overlay(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    return subprocess.run(
        [sys.executable, "-m", "overlay", *args],
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GENERIC_OVERLAY = """\
schema: overlay-config/v1
product:
  repo: owner/name
  default_ref: pin-me
branches:
  main:
    run: [functional, regression]
  hotfix:
    run: [functional]
kinds:
  concurrency: later
  agent: later
never_red_statuses:
  - draft
  - blocked
forbid_hosts:
  - prod.example.com
"""


GENERIC_INBOX = """\
---
id: checkout-retry
kind: user-case
readiness: ready
source:
  repo: owner/name
  path: docs/prd.md
  ref: pin-me
---

# Intent

Retry checkout without a double charge for the same receipt.

# In scope

- FN-login-retry Retry on the failure page.

# Out of scope

- New payment rails.

# User cases

1. Timeout then retry stays one payment.
"""


GENERIC_SUITE = """\
id: checkout-retry
title: Checkout retry without double charge
status: armed
kind: functional
subject: product
source: inbox/checkout-retry.md
packages:
  - src/checkout
reviewed_by: fixture
reviewed_at: 2026-09-10T00:00:00Z
blocked_reason: null
armed_reason: Pin already ships the retry path.
product_command: null
"""


GENERIC_CASES = """\
# Checkout retry

## FN-login-retry Retry without double charge

### Functional
- Title: Retry
- Steps: Fail then retry
- Expected: One charge

### Negative
- Title: Double submit
- Steps: Click retry twice
- Expected: Still one charge

### Edge
- Title: Already completed receipt
- Steps: Retry a finished receipt
- Expected: No second charge
"""


def write_generic_root(dest: Path) -> Path:
    root = dest / "generic"
    write(root / "overlay.yaml", GENERIC_OVERLAY)
    write(root / "inbox" / "checkout-retry.md", GENERIC_INBOX)
    write(root / "suites" / "checkout-retry" / "suite.yaml", GENERIC_SUITE)
    write(root / "suites" / "checkout-retry" / "cases.md", GENERIC_CASES)
    return root
