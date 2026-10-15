"""Tests for teamwork_engine.rubric module."""

import unittest
from teamwork_engine.rubric import (
    AuditResult,
    Rubric,
    calculate_letter_grade,
    create_default_rubric,
    evaluate_audit,
)


class TestRubric(unittest.TestCase):
    """Test 100-point rubric mathematical rules and audit grading."""

    def test_default_rubric_sums_to_100(self):
        rubric = create_default_rubric("Test Build Task")
        self.assertEqual(rubric.total_points, 100)
        self.assertEqual(len(rubric.categories), 5)
        total_category_weight = sum(c.max_points for c in rubric.categories)
        self.assertEqual(total_category_weight, 100)
        d = rubric.to_dict()
        self.assertEqual(d["total_points"], 100)
        md = rubric.to_markdown()
        self.assertIn("# Evaluation Rubric: Test Build Task", md)

    def test_invalid_weights_sum_raises_error(self):
        with self.assertRaises(ValueError):
            create_default_rubric("Invalid Rubric", weights={"fidelity": 50, "feasibility": 20})

    def test_letter_grade_thresholds(self):
        self.assertEqual(calculate_letter_grade(100.0), "A+")
        self.assertEqual(calculate_letter_grade(95.0), "A")
        self.assertEqual(calculate_letter_grade(85.0), "B")
        self.assertEqual(calculate_letter_grade(75.0), "C")
        self.assertEqual(calculate_letter_grade(65.0), "D")
        self.assertEqual(calculate_letter_grade(50.0), "F")

    def test_audit_evaluation_full_marks(self):
        rubric = create_default_rubric("Perfect Plan")
        scores = {
            "fidelity": 25.0,
            "feasibility": 20.0,
            "safety": 20.0,
            "resources": 15.0,
            "verification": 20.0,
        }
        res = evaluate_audit(rubric, scores)
        self.assertIsInstance(res, AuditResult)
        self.assertEqual(res.total_score, 100.0)
        self.assertEqual(res.percentage, 100.0)
        self.assertEqual(res.letter_grade, "A+")
        self.assertEqual(res.verdict, "PASS")
        table = res.to_markdown_table()
        self.assertIn("Letter Grade**: A+", table)

    def test_audit_evaluation_deductions(self):
        rubric = create_default_rubric("Imperfect Plan")
        scores = {
            "fidelity": 20.0,
            "feasibility": 18.0,
            "safety": 15.0,
            "resources": 10.0,
            "verification": 12.0,
        }
        deductions = {
            "fidelity": ["Dropped 1 negative constraint"],
            "safety": ["Missing process isolation check"],
        }
        res = evaluate_audit(rubric, scores, deductions=deductions)
        self.assertEqual(res.total_score, 75.0)
        self.assertEqual(res.letter_grade, "C")
        self.assertEqual(res.verdict, "REVISE")

    def test_audit_evaluation_out_of_bounds_scores(self):
        rubric = create_default_rubric("Boundary Test")
        with self.assertRaises(ValueError):
            evaluate_audit(rubric, {"fidelity": -1.0})
        with self.assertRaises(ValueError):
            evaluate_audit(rubric, {"fidelity": 30.0})


if __name__ == "__main__":
    unittest.main()
