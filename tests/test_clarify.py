"""Tests for teamwork_engine.clarify module."""

import unittest
from teamwork_engine.clarify import ClarifiedTask, clarify_task


class TestClarify(unittest.TestCase):
    """Test clarify parsing, branch conditions, and specification generation."""

    def test_clarify_basic_task(self):
        raw = "Build the standalone CLI for teamwork protocol in S:\\claude file dump\\teamwork-preview-engine"
        result = clarify_task(raw)
        self.assertIsInstance(result, ClarifiedTask)
        self.assertIn("CLI", result.goal)
        self.assertIn("S:\\claude file dump\\teamwork-preview-engine", result.environment_context.get("Working Directory", ""))
        self.assertTrue(len(result.required_work) >= 1)
        md = result.to_markdown()
        self.assertIn("# Clarified Task Specification", md)
        self.assertIn("## Goal", md)
        self.assertIn("## Required Work", md)

    def test_clarify_empty_task_raises_error(self):
        with self.assertRaises(ValueError):
            clarify_task("")
        with self.assertRaises(ValueError):
            clarify_task("   \n\t  ")

    def test_clarify_preserves_negative_constraints(self):
        raw = (
            "Optimize render pipeline.\n"
            "- Never kill user processes like chrome or discord\n"
            "- Zero saves on C:\n"
            "- Do not touch production databases"
        )
        result = clarify_task(raw)
        self.assertTrue(len(result.constraints_and_invariants) >= 2)
        defects = result.validate_against_raw(raw)
        self.assertEqual(defects, [])

    def test_clarify_detects_omitted_constraints(self):
        task = ClarifiedTask(
            goal="Test Goal",
            constraints_and_invariants=["Do unrelated stuff"],
        )
        raw = "Never delete active records and zero saves on C:"
        defects = task.validate_against_raw(raw)
        self.assertTrue(len(defects) >= 1)

    def test_clarify_detects_missing_path_in_validation(self):
        task = ClarifiedTask(
            goal="Test Goal without paths",
            constraints_and_invariants=["None"],
        )
        raw = "Ensure files in S:\\missing\\path\\dir are processed"
        defects = task.validate_against_raw(raw)
        self.assertTrue(any("Referenced path" in d for d in defects))

    def test_clarify_environment_linux_bash(self):
        raw = "Deploy on Linux using bash shell.\nTarget directory: /var/app/deploy"
        result = clarify_task(raw)
        self.assertEqual(result.environment_context.get("OS"), "Linux")
        self.assertEqual(result.environment_context.get("Shell"), "Bash")
        self.assertEqual(result.environment_context.get("Working Directory"), "/var/app/deploy")

    def test_clarify_environment_macos(self):
        raw = "Run tests on macOS darwin platform."
        result = clarify_task(raw)
        self.assertEqual(result.environment_context.get("OS"), "macOS")

    def test_clarify_numbered_and_bullet_steps(self):
        raw_num = (
            "Perform refactor:\n"
            "1. Step one\n"
            "2. Step two\n"
            "3. Step three"
        )
        res_num = clarify_task(raw_num)
        self.assertEqual(len(res_num.required_work), 3)
        self.assertEqual(res_num.required_work[0], "Step one")

        raw_bullets = (
            "Perform tasks:\n"
            "- Task alpha\n"
            "- Task beta\n"
            "- Never fail"
        )
        res_bullets = clarify_task(raw_bullets)
        self.assertIn("Task alpha", res_bullets.required_work)
        self.assertIn("Task beta", res_bullets.required_work)

    def test_clarify_deliverables_and_metrics(self):
        raw = (
            "Goal: Accelerate swap pipeline\n"
            "Must pass pytest with code coverage >= 90%.\n"
            "Achieve 12.95x speedup and ensure CLI exits 0."
        )
        res = clarify_task(raw)
        metrics = [d["metric"] for d in res.deliverables_and_acceptance_numbers]
        self.assertIn("Test Suite Pass Rate", metrics)
        self.assertIn("Code Coverage", metrics)
        self.assertIn("Performance Acceleration", metrics)
        self.assertIn("CLI Exit Code", metrics)

    def test_clarify_with_context_and_references(self):
        raw = "Improve algorithm"
        ctx = (
            "Reference: Survey report 1\n"
            "Survey: Handoff from architect\n"
            "branch feature-fast"
        )
        res = clarify_task(raw, context=ctx)
        self.assertTrue(any("Survey report" in s for s in res.inputs_and_existing_work))
        self.assertTrue(any("Git branch" in s for s in res.inputs_and_existing_work))

    def test_clarify_to_markdown_formatting(self):
        task = ClarifiedTask(
            goal="Comprehensive formatting test",
            environment_context={"OS": "Windows", "GPU": "RTX 5070 Ti"},
            inputs_and_existing_work=["Handoff 1", "Reference doc"],
            required_work=["Step A", "Step B"],
            constraints_and_invariants=["No deletes", "No C:"],
            deliverables_and_acceptance_numbers=[
                {"metric": "Speedup", "target": "3x", "description": "Faster clip render"},
                {"metric": "Coverage", "target": "90%"},
            ],
            material_assumptions=["Assumption 1"],
        )
        md = task.to_markdown()
        self.assertIn("**OS**: Windows", md)
        self.assertIn("- Handoff 1", md)
        self.assertIn("1. Step A", md)
        self.assertIn("- **Speedup**: 3x (Faster clip render)", md)
        self.assertIn("- **Coverage**: 90%", md)
        self.assertIn("- Assumption 1", md)

    def test_clarify_to_dict(self):
        result = clarify_task("Simple task")
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["goal"], "Simple task")
        self.assertIn("required_work", d)
        self.assertIn("deliverables_and_acceptance_numbers", d)


if __name__ == "__main__":
    unittest.main()
