"""CI selector: common always; product by title facet or paths."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from forge import EXIT_OK
from forge.__main__ import main
from forge.apply import load_config
from forge.ci_select import decide, load_ci_config, path_matches

ROOT = Path(__file__).resolve().parents[2]


def _select(
    check: str,
    *,
    title: str | None = None,
    changed: list[str] | None = None,
    root: Path | None = None,
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    argv = ["ci-select", "--root", str(root or ROOT), "--check", check]
    if title is not None:
        argv.extend(["--title", title])
    if changed is not None:
        argv.append("--changed")
        argv.extend(changed)
    code = main(argv, stdout=stdout, stderr=stderr, environ={})
    return code, stdout.getvalue(), stderr.getvalue()


class WorkshopSelectorConfigTests(unittest.TestCase):
    def test_workshop_forge_yaml_loads_and_keeps_apply(self) -> None:
        config = load_ci_config(ROOT)
        self.assertEqual(config.common, ("pr-title", "sop-lock"))
        self.assertEqual(config.products["overlay"].check, "overlay-check")
        self.assertEqual(config.products["forge"].check, "forge-check")
        self.assertIn("overlay/", config.products["overlay"].paths)
        self.assertIn("forge/", config.products["forge"].paths)
        apply_cfg = load_config(ROOT / "forge.yaml")
        main_checks = apply_cfg.rule_for("main").required_checks
        self.assertIn("overlay-check", main_checks)
        self.assertIn("forge-check", main_checks)
        self.assertIn("pr-title", main_checks)
        self.assertIn("sop-lock", main_checks)
        self.assertIn("unittest", main_checks)


class TitleFacetTests(unittest.TestCase):
    def test_overlay_title_runs_overlay_skips_forge(self) -> None:
        overlay = _select("overlay-check", title="feat(overlay/dev): add cover triad")
        forge = _select("forge-check", title="feat(overlay/dev): add cover triad")
        self.assertEqual(overlay[0], EXIT_OK, overlay[2])
        self.assertIn("run: true", overlay[1])
        self.assertIn("reason: title:overlay", overlay[1])
        self.assertEqual(forge[0], EXIT_OK, forge[2])
        self.assertIn("run: false", forge[1])
        self.assertIn("reason: title:overlay", forge[1])

    def test_forge_title_runs_forge_skips_overlay(self) -> None:
        overlay = _select("overlay-check", title="feat(forge/dev): add submit middleware")
        forge = _select("forge-check", title="feat(forge/dev): add submit middleware")
        self.assertEqual(overlay[0], EXIT_OK, overlay[2])
        self.assertIn("run: false", overlay[1])
        self.assertEqual(forge[0], EXIT_OK, forge[2])
        self.assertIn("run: true", forge[1])
        self.assertIn("reason: title:forge", forge[1])

    def test_ci_title_runs_both(self) -> None:
        overlay = _select("overlay-check", title="ci(ci/dev): wire selectable product gates")
        forge = _select("forge-check", title="ci(ci/dev): wire selectable product gates")
        self.assertEqual(overlay[0], EXIT_OK, overlay[2])
        self.assertIn("run: true", overlay[1])
        self.assertEqual(forge[0], EXIT_OK, forge[2])
        self.assertIn("run: true", forge[1])
        self.assertIn("reason: title:ci", overlay[1])

    def test_docs_title_skips_both_products(self) -> None:
        overlay = _select("overlay-check", title="docs(docs/admin): record CI layering")
        forge = _select("forge-check", title="docs(docs/admin): record CI layering")
        self.assertEqual(overlay[0], EXIT_OK, overlay[2])
        self.assertIn("run: false", overlay[1])
        self.assertEqual(forge[0], EXIT_OK, forge[2])
        self.assertIn("run: false", forge[1])
        self.assertIn("reason: title:docs", overlay[1])

    def test_common_never_skips_on_docs_title(self) -> None:
        title = "docs(docs/admin): record CI layering"
        for check in ("pr-title", "sop-lock"):
            code, out, err = _select(check, title=title)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn("run: true", out)
            self.assertIn("reason: common", out)

    def test_common_never_skips_on_overlay_title(self) -> None:
        title = "feat(overlay/dev): add cover triad"
        for check in ("pr-title", "sop-lock"):
            code, out, err = _select(check, title=title)
            self.assertEqual(code, EXIT_OK, err)
            self.assertIn("run: true", out)
            self.assertIn("reason: common", out)


class PathFallbackTests(unittest.TestCase):
    def test_overlay_paths_only(self) -> None:
        overlay = _select("overlay-check", changed=["overlay/select.py", "docs/readme.md"])
        forge = _select("forge-check", changed=["overlay/select.py", "docs/readme.md"])
        self.assertIn("run: true", overlay[1])
        self.assertIn("run: false", forge[1])
        self.assertIn("reason: paths", overlay[1])

    def test_forge_paths_only(self) -> None:
        overlay = _select("overlay-check", changed=["forge/apply.py"])
        forge = _select("forge-check", changed=["forge.yaml"])
        self.assertIn("run: false", overlay[1])
        self.assertIn("run: true", forge[1])

    def test_both_paths(self) -> None:
        changed = ["overlay/run.py", "forge/apply.py"]
        overlay = _select("overlay-check", changed=changed)
        forge = _select("forge-check", changed=changed)
        self.assertIn("run: true", overlay[1])
        self.assertIn("run: true", forge[1])

    def test_docs_paths_skip_products(self) -> None:
        changed = ["docs/design.md", "README.md"]
        overlay = _select("overlay-check", changed=changed)
        forge = _select("forge-check", changed=changed)
        self.assertIn("run: false", overlay[1])
        self.assertIn("run: false", forge[1])
        title = _select("pr-title", changed=changed)
        sop = _select("sop-lock", changed=changed)
        self.assertIn("run: true", title[1])
        self.assertIn("run: true", sop[1])

    def test_title_wins_over_paths(self) -> None:
        overlay = _select(
            "overlay-check",
            title="docs(docs/dev): mention overlay",
            changed=["overlay/select.py"],
        )
        self.assertIn("run: false", overlay[1])
        self.assertIn("reason: title:docs", overlay[1])

    def test_path_match_prefix(self) -> None:
        self.assertTrue(path_matches("overlay/select.py", "overlay/"))
        self.assertTrue(path_matches("forge.yaml", "forge.yaml"))
        self.assertFalse(path_matches("docs/design.md", "forge/"))
        self.assertFalse(path_matches("forge-extra/x.py", "forge.yaml"))


class GithubOutputTests(unittest.TestCase):
    def test_github_output_appends_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = main(
                [
                    "ci-select",
                    "--root",
                    str(ROOT),
                    "--check",
                    "forge-check",
                    "--title",
                    "feat(overlay/dev): x",
                    "--github-output",
                ],
                stdout=stdout,
                stderr=stderr,
                environ={"GITHUB_OUTPUT": str(dest)},
            )
            self.assertEqual(code, EXIT_OK, stderr.getvalue())
            text = dest.read_text(encoding="utf-8")
            self.assertIn("run=false", text)
            self.assertIn("reason=title:overlay", text)


class DecideUnitTests(unittest.TestCase):
    def test_undecided_runs_all_products(self) -> None:
        config = load_ci_config(ROOT)
        overlay = decide(config, "overlay-check", title=None, changed=None)
        forge = decide(config, "forge-check", title=None, changed=None)
        self.assertTrue(overlay.run)
        self.assertTrue(forge.run)
        self.assertEqual(overlay.reason, "undecided-run-all")

    def test_unknown_check_skips(self) -> None:
        config = load_ci_config(ROOT)
        decision = decide(
            config, "mystery-check", title="feat(overlay/dev): x", changed=None
        )
        self.assertFalse(decision.run)
        self.assertEqual(decision.reason, "unknown-check-skip")

    def test_thin_yaml_without_products_skips_unknown_product_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "forge.yaml").write_text(
                "schema: forge-config/v1\nprotect:\n  - main\n",
                encoding="utf-8",
            )
            config = load_ci_config(root)
            decision = decide(config, "overlay-check", title=None, changed=["src/a.py"])
            self.assertFalse(decision.run)
            self.assertEqual(decision.reason, "unknown-check-skip")


if __name__ == "__main__":
    unittest.main()
