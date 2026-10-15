"""Tests for teamwork_engine.guardrail module."""

import unittest
from teamwork_engine.guardrail import (
    GuardrailReport,
    GuardrailVerdict,
    check_guardrail,
    estimate_tokens,
)


class TestGuardrail(unittest.TestCase):
    """Test token estimation, execution-first detection, and process safety rules."""

    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("Hello world"), 3)
        long_str = "word " * 100
        tokens = estimate_tokens(long_str)
        self.assertTrue(120 <= tokens <= 150)

    def test_guardrail_pass_short_planning(self):
        text = "I will inspect the workspace and run the build.\nrun_command: pytest"
        report = check_guardrail(text, max_tokens=500)
        self.assertEqual(report.verdict, GuardrailVerdict.PASS)
        self.assertEqual(report.tool_call_count, 2)
        self.assertTrue(report.token_count < 100)
        summary = report.summary()
        self.assertIn("Verdict: PASS", summary)
        d = report.to_dict()
        self.assertEqual(d["verdict"], "PASS")

    def test_guardrail_warn_long_planning_without_tools(self):
        long_essay = "Theoretical architectural analysis of system design principles and paradigms. " * 60
        report = check_guardrail(long_essay, max_tokens=500, strict=False)
        self.assertEqual(report.verdict, GuardrailVerdict.WARN)
        self.assertEqual(report.tool_call_count, 0)
        self.assertTrue(report.token_count > 500)
        self.assertTrue(any("Exceeded 500 token" in w for w in report.warnings))

    def test_guardrail_strict_fail_long_planning(self):
        long_essay = "Theoretical architectural analysis of system design principles and paradigms. " * 60
        report = check_guardrail(long_essay, max_tokens=500, strict=True)
        self.assertEqual(report.verdict, GuardrailVerdict.FAIL)
        self.assertEqual(report.tool_call_count, 0)

    def test_guardrail_warn_long_planning_with_late_tool(self):
        long_prefix = "Extensive preliminary discourse on system requirements and architectural abstractions. " * 60
        full_text = long_prefix + "\nrun_command: git status"
        report = check_guardrail(full_text, max_tokens=500)
        self.assertEqual(report.verdict, GuardrailVerdict.WARN)
        self.assertTrue(report.tool_call_count >= 1)
        self.assertTrue(any("High pre-action prose" in w for w in report.warnings))

    def test_guardrail_pass_long_text_with_early_tool(self):
        early_action = "run_command: git status\n" + ("Long explanation following the tool call. " * 60)
        report = check_guardrail(early_action, max_tokens=500)
        self.assertEqual(report.verdict, GuardrailVerdict.PASS)
        self.assertTrue(report.token_count < 100)

    def test_guardrail_protected_process_violation(self):
        bad_commands = [
            "Stop-Process -Name chrome",
            "taskkill /f /im discord.exe",
            "kill -9 claude",
        ]
        for cmd in bad_commands:
            report = check_guardrail(cmd, max_tokens=500)
            self.assertEqual(report.verdict, GuardrailVerdict.FAIL)
            self.assertTrue(len(report.protected_process_violations) >= 1)
            summary = report.summary()
            self.assertIn("VIOLATIONS:", summary)

    def test_guardrail_bureaucracy_antipattern(self):
        text = "First, touch shared/LEASE.md and claim the lock."
        report = check_guardrail(text, max_tokens=500)
        self.assertTrue(any("lease or lock" in w.lower() for w in report.warnings))


if __name__ == "__main__":
    unittest.main()
