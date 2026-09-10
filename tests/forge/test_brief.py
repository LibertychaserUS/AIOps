"""PR body heading lint. Fake bodies only."""

from __future__ import annotations

import io
import unittest

from forge import EXIT_OK
from forge.__main__ import main
from forge.brief import EXIT_BRIEF, REQUIRED_H2, lint_pr_body
from forge.title import EXAMPLE


GOOD = "\n\n".join(f"## {heading}\n\n-" for heading in REQUIRED_H2)


class BriefTests(unittest.TestCase):
    def test_six_headings_in_order_pass(self) -> None:
        code, message = lint_pr_body(GOOD)
        self.assertEqual(code, EXIT_OK, message)
        self.assertEqual(message, "")

    def test_empty_fails(self) -> None:
        for body in (None, "", "   "):
            code, message = lint_pr_body(body)
            self.assertEqual(code, EXIT_BRIEF)
            self.assertTrue(message)

    def test_missing_one_fails(self) -> None:
        body = GOOD.replace("## 不做什么\n\n-", "")
        code, message = lint_pr_body(body)
        self.assertEqual(code, EXIT_BRIEF)
        self.assertIn("不做什么", message)

    def test_out_of_order_fails(self) -> None:
        swapped = (
            "## 为什么\n\n-\n\n## 做了什么\n\n-\n\n## 动了哪些门\n\n-\n\n"
            "## 怎么验\n\n-\n\n## 不做什么\n\n-\n\n## 分工\n\n-"
        )
        code, message = lint_pr_body(swapped)
        self.assertEqual(code, EXIT_BRIEF)
        self.assertIn("order", message)

    def test_cli_body_missing_heading_fails(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["pr-title", "--title", EXAMPLE, "--body", "## 做了什么\n"],
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_BRIEF)
        self.assertIn("为什么", stderr.getvalue())

    def test_cli_title_only_skips_body(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = main(
            ["pr-title", "--title", EXAMPLE],
            stdout=stdout,
            stderr=stderr,
            environ={},
        )
        self.assertEqual(code, EXIT_OK, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
