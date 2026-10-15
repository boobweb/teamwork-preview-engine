"""Tests for teamwork_engine.cli module."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from teamwork_engine.cli import main


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing, subcommands, and exit codes."""

    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                code = main(args)
            except SystemExit as se:
                code = se.code if isinstance(se.code, int) else 0
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_cli_help(self):
        code, out, _ = self.run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage:", out)
        self.assertIn("clarify", out)
        self.assertIn("preflight", out)
        self.assertIn("rubric", out)
        self.assertIn("guardrail", out)

    def test_cli_no_args_shows_help(self):
        code, out, _ = self.run_cli([])
        self.assertEqual(code, 0)
        self.assertIn("usage:", out)

    def test_cli_version(self):
        code, out, _ = self.run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("0.1.0", out)

    def test_clarify_subcommand(self):
        code, out, _ = self.run_cli(["clarify", "--task", "Implement M1 CLI"])
        self.assertEqual(code, 0)
        self.assertIn("# Clarified Task Specification", out)

    def test_clarify_file_input(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
            tf.write("Build core protocol from file input")
            tf.flush()
            tmp_path = tf.name

        try:
            code, out, _ = self.run_cli(["clarify", "--file", tmp_path])
            self.assertEqual(code, 0)
            self.assertIn("Build core protocol from file input", out)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_clarify_missing_file_exits_2(self):
        code, _, err = self.run_cli(["clarify", "--file", "non_existent_file_xyz.txt"])
        self.assertEqual(code, 2)
        self.assertIn("File not found", err)

    def test_clarify_output_to_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md") as tf:
            out_path = tf.name

        try:
            code, _, _ = self.run_cli(["clarify", "--task", "Save output", "--output", out_path])
            self.assertEqual(code, 0)
            content = Path(out_path).read_text(encoding="utf-8")
            self.assertIn("# Clarified Task Specification", content)
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_clarify_json_format(self):
        code, out, _ = self.run_cli(["clarify", "--task", "Implement M1 CLI", "--format", "json"])
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["goal"], "Implement M1 CLI")

    def test_clarify_empty_task_exits_2(self):
        code, _, err = self.run_cli(["clarify", "--task", ""])
        self.assertEqual(code, 2)
        self.assertIn("Error:", err)

    def test_clarify_missing_task_exits_2(self):
        code, _, err = self.run_cli(["clarify"])
        self.assertEqual(code, 2)
        self.assertIn("Error:", err)

    def test_preflight_dry_run_table(self):
        code, out, _ = self.run_cli(["preflight", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("=== Teamwork Preflight Check", out)
        self.assertIn("claude", out)

    def test_preflight_dry_run_json(self):
        code, out, _ = self.run_cli(["preflight", "--dry-run", "--format", "json"])
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertIn("agents", parsed)
        self.assertEqual(parsed["mode"], "dry_run")

    def test_preflight_custom_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            code, out, _ = self.run_cli(["preflight", "--workspace", tmpdir, "--provider", "claude"])
            self.assertEqual(code, 0)
            self.assertIn("claude", out)

    def test_rubric_subcommand(self):
        code, out, _ = self.run_cli(["rubric", "--task", "Test Task"])
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["total_points"], 100)
        self.assertEqual(len(parsed["categories"]), 5)

    def test_rubric_markdown_format(self):
        code, out, _ = self.run_cli(["rubric", "--task", "Test Task", "--format", "markdown"])
        self.assertEqual(code, 0)
        self.assertIn("# Evaluation Rubric: Test Task", out)

    def test_rubric_invalid_weights_sum_exits_2(self):
        bad_weights = json.dumps({"fidelity": 40, "feasibility": 20})
        code, _, err = self.run_cli(["rubric", "--task", "Task", "--weights", bad_weights])
        self.assertEqual(code, 2)
        self.assertIn("Error:", err)

    def test_rubric_audit_mode(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md") as tf:
            tf.write("# Execution Plan\nStep 1: Inspect files\nStep 2: Run pytest")
            tf.flush()
            plan_path = tf.name

        try:
            code, out, _ = self.run_cli(["rubric", "--task", "Audit Task", "--audit", plan_path])
            self.assertEqual(code, 0)
            parsed = json.loads(out)
            self.assertIn("letter_grade", parsed)
            self.assertEqual(parsed["verdict"], "PASS")

            # Test markdown format audit
            code_md, out_md, _ = self.run_cli(["rubric", "--task", "Audit Task", "--audit", plan_path, "--format", "markdown"])
            self.assertEqual(code_md, 0)
            self.assertIn("Adversarial Audit Report", out_md)
        finally:
            Path(plan_path).unlink(missing_ok=True)

    def test_rubric_audit_missing_file_exits_2(self):
        code, _, err = self.run_cli(["rubric", "--task", "Task", "--audit", "missing_plan.md"])
        self.assertEqual(code, 2)
        self.assertIn("Audit plan file not found", err)

    def test_guardrail_pass(self):
        code, out, _ = self.run_cli(["guardrail", "--text", "Short text\nrun_command: ls"])
        self.assertEqual(code, 0)
        self.assertIn("Verdict: PASS", out)

    def test_guardrail_file_input(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
            tf.write("Short plan in file\nrun_command: pytest")
            tf.flush()
            txt_path = tf.name

        try:
            code, out, _ = self.run_cli(["guardrail", "--file", txt_path])
            self.assertEqual(code, 0)
            self.assertIn("Verdict: PASS", out)
        finally:
            Path(txt_path).unlink(missing_ok=True)

    def test_guardrail_missing_file_exits_2(self):
        code, _, err = self.run_cli(["guardrail", "--file", "missing_file_xyz.txt"])
        self.assertEqual(code, 2)
        self.assertIn("File not found", err)

    def test_guardrail_missing_input_exits_2(self):
        code, _, err = self.run_cli(["guardrail"])
        self.assertEqual(code, 2)
        self.assertIn("Must provide either --text or --file", err)

    def test_guardrail_json_output(self):
        code, out, _ = self.run_cli(["guardrail", "--text", "Short text", "--output", "json"])
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["verdict"], "PASS")

    def test_guardrail_strict_fail(self):
        long_text = "Analysis " * 600
        code, out, _ = self.run_cli(["guardrail", "--text", long_text, "--strict"])
        self.assertEqual(code, 1)
        self.assertIn("Verdict: FAIL", out)

    def test_guardrail_protected_process_flagged(self):
        bad_text = "run_command: taskkill /im chrome.exe"
        code, out, _ = self.run_cli(["guardrail", "--text", bad_text])
        self.assertEqual(code, 0)  # non-strict exit 0
        self.assertIn("PROTECTED PROCESS VIOLATIONS", out)


if __name__ == "__main__":
    unittest.main()
