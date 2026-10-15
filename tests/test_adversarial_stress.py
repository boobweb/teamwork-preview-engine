"""Adversarial stress test suite for Rubric scoring math and Task Clarification.

Tests weight validations, edge grade thresholds, negative constraint detection,
and JSON export schemas under extreme, boundary, and adversarial inputs.
"""

from __future__ import annotations

import json
import math
import unittest
from typing import Any, Dict

from teamwork_engine.clarify import ClarifiedTask, clarify_task
from teamwork_engine.rubric import (
    AuditResult,
    Rubric,
    RubricCategory,
    calculate_letter_grade,
    create_default_rubric,
    evaluate_audit,
)


class TestRubricWeightValidations(unittest.TestCase):
    """Stress tests on rubric weights, sum enforcement, and category models."""

    def test_rejection_of_non_100_sums(self):
        """Rubric must strictly reject category sums not equal to total_points."""
        invalid_sums = [99, 101, 0, 50, 150, -100, 1000]
        for bad_sum in invalid_sums:
            with self.subTest(bad_sum=bad_sum):
                with self.assertRaises(ValueError) as ctx:
                    create_default_rubric(
                        "Invalid Sum Rubric",
                        weights={
                            "fidelity": bad_sum,
                            "feasibility": 0,
                            "safety": 0,
                            "resources": 0,
                            "verification": 0,
                        },
                    )
                self.assertIn("must sum to exactly 100", str(ctx.exception))

    def test_partial_custom_weights_dict_handling(self):
        """Providing only a subset of keys in weights dict must not silently produce invalid totals."""
        with self.assertRaises(ValueError):
            create_default_rubric(
                "Partial Keys",
                weights={"fidelity": 60, "feasibility": 40},
            )

    def test_unknown_keys_in_weights_dict_rejection(self):
        """Unknown keys in weights dict must raise ValueError rather than being silently ignored."""
        with self.assertRaises(ValueError):
            create_default_rubric(
                "Unknown Key",
                weights={"custom_category": 100},
            )

    def test_negative_weight_in_weights_dict_rejection(self):
        """Category weights <= 0 or negative weights summing to 100 must be rejected."""
        with self.assertRaises(ValueError):
            create_default_rubric(
                "Negative Weight Rubric",
                weights={
                    "fidelity": 120,
                    "feasibility": -20,
                    "safety": 0,
                    "resources": 0,
                    "verification": 0,
                },
            )

    def test_rubric_direct_instantiation_mismatched_sum(self):
        """Direct instantiation of Rubric with mismatch between total_points and categories."""
        cats = [
            RubricCategory("c1", "Cat 1", 30, "Desc 1"),
            RubricCategory("c2", "Cat 2", 30, "Desc 2"),
        ]
        with self.assertRaises(ValueError) as ctx:
            Rubric(task_name="Direct Mismatch", categories=cats, total_points=100)
        self.assertIn("must sum to exactly 100 (got 60)", str(ctx.exception))

    def test_zero_total_points_instantiation(self):
        """Rubric with 0 total points must not be evaluated or divide by zero."""
        rubric = Rubric(task_name="Zero Points", categories=[], total_points=0)
        self.assertEqual(rubric.total_points, 0)
        with self.assertRaises((ValueError, ZeroDivisionError)):
            evaluate_audit(rubric, {})


class TestRubricScoringMathAndThresholds(unittest.TestCase):
    """Stress tests on scoring bounds, letter grades, and verdicts."""

    def test_letter_grade_exact_boundaries(self):
        """Test exact float threshold boundaries for letter grades."""
        # A+: >= 100.0
        self.assertEqual(calculate_letter_grade(100.0), "A+")
        self.assertEqual(calculate_letter_grade(105.0), "A+")

        # A: >= 90.0 and < 100.0
        self.assertEqual(calculate_letter_grade(99.999), "A")
        self.assertEqual(calculate_letter_grade(90.0), "A")

        # B: >= 80.0 and < 90.0
        self.assertEqual(calculate_letter_grade(89.999), "B")
        self.assertEqual(calculate_letter_grade(80.0), "B")

        # C: >= 70.0 and < 80.0
        self.assertEqual(calculate_letter_grade(79.999), "C")
        self.assertEqual(calculate_letter_grade(70.0), "C")

        # D: >= 60.0 and < 70.0
        self.assertEqual(calculate_letter_grade(69.999), "D")
        self.assertEqual(calculate_letter_grade(60.0), "D")

        # F: < 60.0
        self.assertEqual(calculate_letter_grade(59.999), "F")
        self.assertEqual(calculate_letter_grade(0.0), "F")
        self.assertEqual(calculate_letter_grade(-10.0), "F")

    def test_verdict_exact_thresholds(self):
        """Test PASS (>=90.0), REVISE (>=70.0), and FAIL (<70.0) verdict thresholds."""
        rubric = create_default_rubric("Verdict Test")

        # 90.0 -> PASS
        res_pass = evaluate_audit(
            rubric,
            {"fidelity": 22.5, "feasibility": 18.0, "safety": 18.0, "resources": 13.5, "verification": 18.0},
        )
        self.assertAlmostEqual(res_pass.percentage, 90.0)
        self.assertEqual(res_pass.verdict, "PASS")

        # 89.9 -> REVISE
        res_revise_upper = evaluate_audit(
            rubric,
            {"fidelity": 22.4, "feasibility": 18.0, "safety": 18.0, "resources": 13.5, "verification": 18.0},
        )
        self.assertAlmostEqual(res_revise_upper.percentage, 89.9)
        self.assertEqual(res_revise_upper.verdict, "REVISE")

        # 70.0 -> REVISE
        res_revise_lower = evaluate_audit(
            rubric,
            {"fidelity": 17.5, "feasibility": 14.0, "safety": 14.0, "resources": 10.5, "verification": 14.0},
        )
        self.assertAlmostEqual(res_revise_lower.percentage, 70.0)
        self.assertEqual(res_revise_lower.verdict, "REVISE")

        # 69.9 -> FAIL
        res_fail = evaluate_audit(
            rubric,
            {"fidelity": 17.4, "feasibility": 14.0, "safety": 14.0, "resources": 10.5, "verification": 14.0},
        )
        self.assertAlmostEqual(res_fail.percentage, 69.9)
        self.assertEqual(res_fail.verdict, "FAIL")

        # 0.0 -> FAIL
        res_zero = evaluate_audit(
            rubric,
            {"fidelity": 0.0, "feasibility": 0.0, "safety": 0.0, "resources": 0.0, "verification": 0.0},
        )
        self.assertEqual(res_zero.percentage, 0.0)
        self.assertEqual(res_zero.verdict, "FAIL")
        self.assertEqual(res_zero.letter_grade, "F")

    def test_score_clamp_bounds_enforcement(self):
        """Scores outside [0.0, max_points] must raise ValueError."""
        rubric = create_default_rubric("Clamp Test")

        # Exceeds max weight
        with self.assertRaises(ValueError) as ctx:
            evaluate_audit(rubric, {"fidelity": 25.01})
        self.assertIn("exceeds maximum weight", str(ctx.exception))

        # Negative score
        with self.assertRaises(ValueError) as ctx:
            evaluate_audit(rubric, {"fidelity": -0.01})
        self.assertIn("cannot be negative", str(ctx.exception))

    def test_nan_and_inf_score_inputs(self):
        """Adversarial float values (NaN, Inf) in score_inputs must be rejected."""
        rubric = create_default_rubric("Adversarial Floats")

        # Infinity
        with self.assertRaises(ValueError):
            evaluate_audit(rubric, {"fidelity": float("inf")})

        with self.assertRaises(ValueError):
            evaluate_audit(rubric, {"fidelity": float("-inf")})

        # NaN handling: NaN must raise ValueError, not silently produce NaN totals
        with self.assertRaises(ValueError):
            evaluate_audit(rubric, {"fidelity": float("nan")})

    def test_missing_category_keys_in_score_inputs(self):
        """Verify behavior when category keys are missing or empty in score_inputs."""
        rubric = create_default_rubric("Default Scoring")
        res = evaluate_audit(rubric, {})
        self.assertEqual(res.total_score, 100.0)
        self.assertEqual(res.percentage, 100.0)

    def test_markdown_table_rendering_with_deductions(self):
        """AuditResult markdown table rendering must include all columns, deductions, and scores."""
        rubric = create_default_rubric("Markdown Report")
        scores = {"fidelity": 20.0, "feasibility": 15.0, "safety": 20.0, "resources": 15.0, "verification": 18.0}
        deductions = {
            "fidelity": ["Omitted 1 constraint"],
            "feasibility": ["Untested GPU fallback", "Missing port config"],
        }
        res = evaluate_audit(rubric, scores, deductions=deductions)
        md = res.to_markdown_table()
        self.assertIn("| Category | Weight | Deductions / Gaps | Points Earned | Letter Grade |", md)
        self.assertIn("Omitted 1 constraint", md)
        self.assertIn("Untested GPU fallback; Missing port config", md)
        self.assertIn("Total / Overall", md)


class TestClarifyNegativeConstraintsAndEdgeCases(unittest.TestCase):
    """Stress tests on task clarification, negative constraints, and boundary inputs."""

    def test_empty_and_whitespace_inputs(self):
        """Empty, whitespace-only, and blank string inputs must be rejected with ValueError."""
        blank_inputs = ["", "   ", "\t", "\n\n", " \t \r\n "]
        for s in blank_inputs:
            with self.subTest(s=repr(s)):
                with self.assertRaises(ValueError):
                    clarify_task(s)

    def test_negative_constraint_preservation_semantics(self):
        """CRITICAL: Negative constraints must preserve negation words (Never, Zero, Do not, etc.).

        Stripping negation words inverts the constraint from prohibitive to permissive/mandatory.
        """
        raw = (
            "Task: Optimize database queries\n"
            "- Never delete production records\n"
            "- Zero saves on C:\n"
            "- Do not terminate user processes\n"
            "- Must not alter production schema"
        )
        task = clarify_task(raw)

        # The constraints MUST NOT simply say "delete production records" without "never" / "do not"
        for prohibitive in ["delete production records", "saves on C:", "terminate user processes", "alter production schema"]:
            for item in task.constraints_and_invariants:
                if prohibitive.lower() in item.lower():
                    has_negation = any(
                        neg in item.lower()
                        for neg in ["never", "zero", "not", "don't", "no ", "prohibit", "must not"]
                    )
                    self.assertTrue(
                        has_negation,
                        f"SEMANTIC REVERSAL BUG: Constraint '{item}' stripped negation keyword! "
                        f"Instructs agent to perform the prohibited action.",
                    )

    def test_inline_negative_constraints_extraction(self):
        """Negative constraints written as inline prose (not bulleted) must be captured."""
        raw = (
            "Implement image resizing service. "
            "Never delete source photos under S:\\raw. "
            "Prohibited from touching production configs. "
            "Zero downtime during deployment."
        )
        task = clarify_task(raw)
        defects = task.validate_against_raw(raw)

        self.assertEqual(
            defects,
            [],
            f"Failed to extract inline negative constraints: {defects}",
        )

    def test_validate_against_raw_detects_omissions(self):
        """validate_against_raw must detect when negative constraints are omitted."""
        raw = (
            "Deploy application.\n"
            "- Never touch billing accounts\n"
            "- Zero writes to C:\n"
            "- Do not restart proxy"
        )
        task = ClarifiedTask(
            goal="Deploy application",
            constraints_and_invariants=["Zero writes to C:", "Do not restart proxy"],
        )
        defects = task.validate_against_raw(raw)
        self.assertTrue(
            any("billing" in d.lower() for d in defects),
            "Expected defect for omitted billing constraint",
        )

    def test_validate_against_raw_detects_missing_paths(self):
        """validate_against_raw must detect when file/dir paths from raw_task are missing."""
        raw = "Process logs from S:\\data\\logs and write to E:\\archive\\results"
        task = ClarifiedTask(
            goal="Process logs",
            inputs_and_existing_work=["S:\\data\\logs"],
            # Omitting E:\archive\results
        )
        defects = task.validate_against_raw(raw)
        self.assertTrue(
            any("E:\\archive\\results" in d or "E:/archive/results" in d for d in defects),
            f"Expected defect for omitted path E:\\archive\\results, got {defects}",
        )

    def test_adversarial_large_and_special_char_input(self):
        """Test resilience against large inputs and regex special characters."""
        special_raw = (
            "Task: Handle regex chars [.*+?^${}()|[]\\] in filenames.\n"
            "Working directory: S:\\test\\regex-special\n"
            "- Never delete files matching /^[a-z]+$/\n"
            "- Preserve {version: '1.0'}\n"
            "Must pass pytest with code coverage >= 95%."
        )
        task = clarify_task(special_raw)
        self.assertEqual(task.environment_context.get("Working Directory"), "S:\\test\\regex-special")
        md = task.to_markdown()
        self.assertIn("Code Coverage", md)


class TestJSONExportSchemas(unittest.TestCase):
    """Stress tests on JSON schema validation and export serialization."""

    def test_rubric_json_schema_conformance(self):
        """Rubric to_dict() must conform to expected schema and be valid JSON."""
        rubric = create_default_rubric("Schema Test")
        data = rubric.to_dict()

        self.assertIsInstance(data, dict)
        self.assertIn("task_name", data)
        self.assertIn("total_points", data)
        self.assertIn("categories", data)
        self.assertEqual(data["total_points"], 100)
        self.assertIsInstance(data["categories"], list)
        self.assertEqual(len(data["categories"]), 5)

        for cat in data["categories"]:
            self.assertIn("id", cat)
            self.assertIn("name", cat)
            self.assertIn("max_points", cat)
            self.assertIn("description", cat)
            self.assertIn("evaluation_criteria", cat)
            self.assertIsInstance(cat["id"], str)
            self.assertIsInstance(cat["max_points"], int)
            self.assertIsInstance(cat["evaluation_criteria"], list)

        # Strict JSON compliance test (no NaN/Inf)
        json_str = json.dumps(data, indent=2, allow_nan=False)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["task_name"], "Schema Test")
        self.assertEqual(parsed["total_points"], 100)

    def test_audit_result_json_schema_conformance(self):
        """AuditResult to_dict() must conform to expected schema and be strictly RFC 8259 JSON compliant."""
        rubric = create_default_rubric("Audit Schema Test")
        scores = {"fidelity": 23.0, "feasibility": 18.0, "safety": 19.0, "resources": 14.0, "verification": 19.0}
        deductions = {"fidelity": ["Slight ambiguity in requirement 3"]}
        res = evaluate_audit(rubric, scores, deductions=deductions)
        data = res.to_dict()

        required_fields = ["task_name", "total_score", "max_score", "percentage", "letter_grade", "verdict", "scores"]
        for f in required_fields:
            self.assertIn(f, data, f"Missing field in AuditResult.to_dict(): {f}")

        self.assertIsInstance(data["scores"], list)
        self.assertEqual(len(data["scores"]), 5)

        for s in data["scores"]:
            self.assertIn("category_id", s)
            self.assertIn("score", s)
            self.assertIn("deductions", s)
            self.assertIn("rationale", s)
            self.assertIsInstance(s["deductions"], list)

        # Strict JSON compliance test (no NaN/Inf)
        json_str = json.dumps(data, indent=2, allow_nan=False)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["letter_grade"], "A")
        self.assertEqual(parsed["verdict"], "PASS")

    def test_clarified_task_json_schema_conformance(self):
        """ClarifiedTask to_dict() must conform to expected schema and be valid JSON."""
        raw = (
            "Goal: Deploy service on Windows using pwsh.\n"
            "Working directory: S:\\claude file dump\\teamwork-preview-engine\n"
            "Reference: Prior handoff doc\n"
            "- Step 1: Install packages\n"
            "- Step 2: Run verification\n"
            "- Never terminate active chrome sessions\n"
            "Must pass pytest with 100% pass rate."
        )
        task = clarify_task(raw)
        data = task.to_dict()

        expected_fields = [
            "goal",
            "environment_context",
            "inputs_and_existing_work",
            "required_work",
            "constraints_and_invariants",
            "deliverables_and_acceptance_numbers",
            "material_assumptions",
        ]
        for field in expected_fields:
            self.assertIn(field, data, f"Missing field in ClarifiedTask.to_dict(): {field}")

        self.assertIsInstance(data["environment_context"], dict)
        self.assertIsInstance(data["inputs_and_existing_work"], list)
        self.assertIsInstance(data["required_work"], list)
        self.assertIsInstance(data["constraints_and_invariants"], list)
        self.assertIsInstance(data["deliverables_and_acceptance_numbers"], list)
        self.assertIsInstance(data["material_assumptions"], list)

        json_str = json.dumps(data, indent=2, allow_nan=False)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["environment_context"]["OS"], "Windows")


if __name__ == "__main__":
    unittest.main()
