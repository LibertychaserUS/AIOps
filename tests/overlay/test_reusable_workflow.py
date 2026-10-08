"""Reusable overlay.yml contract for adopters (not Learning Guide specific)."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "overlay.yml"


def _load() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _steps(job: dict) -> list[dict]:
    return [step for step in job.get("steps", []) if isinstance(step, dict)]


class ReusableWorkflowTests(unittest.TestCase):
    def test_empty_branch_omits_flag_and_workshop_does_not_pin_main(self) -> None:
        data = _load()
        select_runs = [
            str(step.get("run") or "")
            for step in _steps(data["jobs"]["select"])
            if step.get("name") == "overlay select"
        ]
        self.assertTrue(select_runs, data["jobs"]["select"])
        self.assertIn('python -m overlay select --root', select_runs[0])
        self.assertIn('if [ -n "${{ steps.br.outputs.name }}" ]', select_runs[0])
        caller = yaml.safe_load((ROOT / ".github" / "workflows" / "overlay-check.yml").read_text(encoding="utf-8"))
        workshop = caller["jobs"]["overlay"]["with"]
        fixture = caller["jobs"]["fixture"]["with"]
        self.assertNotIn("branch", workshop)
        self.assertEqual(fixture.get("branch"), "main")
        self.assertNotIn("python -m overlay generate", (ROOT / ".github" / "workflows" / "overlay.yml").read_text())
    def test_run_job_can_install_product_dependencies(self) -> None:
        # Learning Guide had to abandon this reusable and write an inline job
        # only to `npm ci`; a standard part must let the product install its
        # own toolchain before product_command runs.
        data = _load()
        on_field = data.get("on") or data.get(True)
        inputs = on_field["workflow_call"]["inputs"]
        self.assertIn("setup_command", inputs)
        self.assertEqual(inputs["setup_command"].get("type"), "string")
        self.assertEqual(inputs["setup_command"].get("default", ""), "")
        run_job = data["jobs"]["run"]
        names = [str(step.get("name", "")) for step in _steps(run_job)]
        setup_index = next((i for i, n in enumerate(names) if "product dependencies" in n.lower()), None)
        self.assertIsNotNone(setup_index, names)
        run_index = next(i for i, n in enumerate(names) if n == "overlay run")
        self.assertLess(setup_index, run_index)
        setup_step = _steps(run_job)[setup_index]
        self.assertIn("inputs.setup_command", str(setup_step.get("if", "")))
        self.assertIn("inputs.setup_command", str(setup_step.get("run", "")))

    def test_setup_command_does_not_leak_into_validate_or_select(self) -> None:
        data = _load()
        for job_name in ("validate", "select"):
            text = yaml.safe_dump(data["jobs"][job_name])
            self.assertNotIn("setup_command", text, job_name)

    def test_no_tokens_persist_in_any_job(self) -> None:
        data = _load()
        for job_name, job in data["jobs"].items():
            for step in _steps(job):
                if str(step.get("uses", "")).startswith("actions/checkout"):
                    with_field = step.get("with") or {}
                    self.assertIs(with_field.get("persist-credentials"), False, job_name)


if __name__ == "__main__":
    unittest.main()
