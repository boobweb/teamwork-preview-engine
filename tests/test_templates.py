"""Tests for teamwork_engine.templates module and CLI template subcommand."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from teamwork_engine.cli import main
from teamwork_engine.templates import (
    TemplateValidationError,
    get_templates_dir,
    list_templates,
    load_template,
    render_template,
    validate_template,
)


class TestTemplates(unittest.TestCase):
    """Test template loading, rendering, zero-placeholder validation, and CLI commands."""

    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Helper to run CLI and capture output."""
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                code = main(args)
            except SystemExit as se:
                code = se.code if isinstance(se.code, int) else 0
        return code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_get_templates_dir_exists(self):
        templates_dir = get_templates_dir()
        self.assertTrue(templates_dir.is_dir())
        self.assertTrue((templates_dir / "mega-prompt-claude.md").exists())

    def test_list_templates(self):
        templates = list_templates()
        self.assertIn("claude", templates)
        self.assertIn("codex", templates)
        self.assertIn("grok", templates)
        self.assertIn("universal", templates)

    def test_list_templates_non_existent_dir(self):
        empty_dir = Path(tempfile.gettempdir()) / "non_existent_templates_dir_12345"
        result = list_templates(empty_dir)
        self.assertEqual(result, [])

    def test_list_templates_custom_dir(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "mega-prompt-alpha.md").write_text("content", encoding="utf-8")
            (p / "beta.md").write_text("content", encoding="utf-8")
            result = list_templates(p)
            self.assertEqual(result, ["alpha", "beta"])

    def test_load_template_canonical_names(self):
        for name in ["claude", "codex", "grok", "universal"]:
            content = load_template(name)
            self.assertIsInstance(content, str)
            self.assertGreater(len(content), 100)
            self.assertIn("# TEAMWORK-PREVIEW", content)

    def test_load_template_variants(self):
        # By full file name
        content1 = load_template("mega-prompt-claude.md")
        # By stem
        content2 = load_template("mega-prompt-claude")
        # By short identifier
        content3 = load_template("claude")
        self.assertEqual(content1, content2)
        self.assertEqual(content2, content3)

    def test_load_template_direct_path(self):
        templates_dir = get_templates_dir()
        file_path = templates_dir / "mega-prompt-grok.md"
        content = load_template(str(file_path))
        self.assertIn("GROK BUILD SPEED ENGINE", content)

    def test_load_template_not_found(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            load_template("imaginary-agent-template-xyz")
        self.assertIn("not found in directory", str(ctx.exception))

    def test_render_template(self):
        rendered = render_template(
            "claude",
            variables={
                "TASK_DESCRIPTION": "Accelerate rendering pipeline",
                "WORKING_DIR": "/path/to/project",
                "PROTECTED_INVARIANTS": "No C: drive writes",
                "ACCEPTANCE_NUMBERS": ">= 3x speedup",
            },
        )
        self.assertIn("Accelerate rendering pipeline", rendered)
        self.assertIn("/path/to/project", rendered)
        self.assertIn("No C: drive writes", rendered)
        self.assertIn(">= 3x speedup", rendered)

    def test_render_template_no_variables(self):
        raw = load_template("claude")
        rendered_none = render_template("claude", variables=None)
        rendered_empty = render_template("claude", variables={})
        self.assertEqual(raw, rendered_none)
        self.assertEqual(raw, rendered_empty)

    def test_validate_template_clean_canonical(self):
        for name in ["claude", "codex", "grok", "universal"]:
            content = load_template(name)
            is_valid, errors = validate_template(content)
            self.assertTrue(is_valid, f"Template {name} had validation errors: {errors}")
            self.assertEqual(len(errors), 0)

    def test_validate_template_file_path(self):
        templates_dir = get_templates_dir()
        path = templates_dir / "mega-prompt-universal.md"
        is_valid, errors = validate_template(str(path))
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_validate_template_detects_forbidden_tokens(self):
        dirty_samples = [
            "This task has a TODO item on line 1",
            "Status: TBD pending review",
            "Need to FIXME this broken parser",
            "This is a PLACEHOLDER value",
            "Value: INSERT_HERE",
            "Here is <insert prompt details here> in text",
            "Review [insert missing spec here] now",
            "Release date: TBA",
            "Secret code: XXX",
        ]
        for dirty in dirty_samples:
            is_valid, errors = validate_template(dirty)
            self.assertFalse(is_valid, f"Expected validation failure for: {dirty}")
            self.assertGreater(len(errors), 0)

    def test_validate_template_detects_dirty_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md", encoding="utf-8") as tf:
            tf.write("# Incomplete Template\nLine 2 has TODO item\nLine 3 is TBD\n")
            tf.flush()
            temp_path = tf.name

        try:
            is_valid, errors = validate_template(temp_path)
            self.assertFalse(is_valid)
            self.assertEqual(len(errors), 2)
            self.assertIn("TODO", errors[0])
            self.assertIn("TBD", errors[1])
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_template_validation_error_class(self):
        err = TemplateValidationError("Validation failed", errors=["Error 1", "Error 2"])
        self.assertEqual(str(err), "Validation failed")
        self.assertEqual(err.errors, ["Error 1", "Error 2"])

    # CLI tests
    def test_cli_template_list_text(self):
        code, out, _ = self.run_cli(["template", "--list"])
        self.assertEqual(code, 0)
        self.assertIn("Available Mega-Prompt Templates:", out)
        self.assertIn("claude", out)
        self.assertIn("codex", out)
        self.assertIn("grok", out)
        self.assertIn("universal", out)

    def test_cli_template_list_json(self):
        code, out, _ = self.run_cli(["template", "--list", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("templates", data)
        self.assertIn("claude", data["templates"])

    def test_cli_template_show(self):
        code, out, _ = self.run_cli(["template", "--show", "claude"])
        self.assertEqual(code, 0)
        self.assertIn("CLAUDE CODE (PIPER) EXECUTION GOVERNOR", out)

    def test_cli_template_show_output_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md") as tf:
            temp_path = tf.name

        try:
            code, _, _ = self.run_cli(["template", "--show", "codex", "--output", temp_path])
            self.assertEqual(code, 0)
            content = Path(temp_path).read_text(encoding="utf-8")
            self.assertIn("CODEX / OPENAI AUTONOMOUS ENGINE", content)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_cli_template_show_not_found(self):
        code, _, err = self.run_cli(["template", "--show", "non_existent_agent"])
        self.assertEqual(code, 2)
        self.assertIn("Error:", err)

    def test_cli_template_validate_pass(self):
        code, out, _ = self.run_cli(["template", "--validate", "claude"])
        self.assertEqual(code, 0)
        self.assertIn("PASS: Template 'claude' contains ZERO placeholders.", out)

    def test_cli_template_validate_file_path(self):
        templates_dir = get_templates_dir()
        path = str(templates_dir / "mega-prompt-universal.md")
        code, out, _ = self.run_cli(["template", "--validate", path])
        self.assertEqual(code, 0)
        self.assertIn("contains ZERO placeholders", out)

    def test_cli_template_validate_dirty_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md", encoding="utf-8") as tf:
            tf.write("Draft with TODO\n")
            tf.flush()
            temp_path = tf.name

        try:
            code, out, _ = self.run_cli(["template", "--validate", temp_path])
            self.assertEqual(code, 1)
            self.assertIn("FAIL:", out)
            self.assertIn("TODO", out)

            # Also check json format
            code_json, out_json, _ = self.run_cli(
                ["template", "--validate", temp_path, "--format", "json"]
            )
            self.assertEqual(code_json, 1)
            data = json.loads(out_json)
            self.assertFalse(data["valid"])
            self.assertEqual(len(data["errors"]), 1)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_cli_template_render(self):
        code, out, _ = self.run_cli([
            "template",
            "--render",
            "codex",
            "--var",
            "TASK_DESCRIPTION=Write autonomous tests",
            "--var",
            "WORKING_DIR=/workspace",
        ])
        self.assertEqual(code, 0)
        self.assertIn("Write autonomous tests", out)
        self.assertIn("/workspace", out)

    def test_cli_template_render_output_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md") as tf:
            temp_path = tf.name

        try:
            code, _, _ = self.run_cli([
                "template",
                "--render",
                "grok",
                "--var",
                "TASK_DESCRIPTION=Fix compilation error",
                "--output",
                temp_path,
            ])
            self.assertEqual(code, 0)
            content = Path(temp_path).read_text(encoding="utf-8")
            self.assertIn("Fix compilation error", content)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_cli_template_render_invalid_var(self):
        code, _, err = self.run_cli([
            "template",
            "--render",
            "claude",
            "--var",
            "INVALID_VAR_WITHOUT_EQUALS",
        ])
        self.assertEqual(code, 2)
        self.assertIn("Error: Invalid variable format", err)

    def test_cli_template_render_not_found(self):
        code, _, err = self.run_cli([
            "template",
            "--render",
            "non_existent",
            "--var",
            "FOO=BAR",
        ])
        self.assertEqual(code, 2)
        self.assertIn("Error:", err)

    def test_cli_template_no_args(self):
        code, _, err = self.run_cli(["template"])
        self.assertEqual(code, 2)
        self.assertIn("Error: Must specify one of", err)

    def test_cli_template_validate_json_valid(self):
        code, out, _ = self.run_cli(["template", "--validate", "claude", "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["valid"])
        self.assertEqual(data["errors"], [])

    def test_cli_template_validate_raw_text(self):
        # Valid raw text
        code, out, _ = self.run_cli(["template", "--validate", "This is clean text without forbidden markers."])
        self.assertEqual(code, 0)
        self.assertIn("contains ZERO placeholders", out)

        # Dirty raw text
        code_fail, out_fail, _ = self.run_cli(["template", "--validate", "Contains a TODO marker."])
        self.assertEqual(code_fail, 1)
        self.assertIn("FAIL:", out_fail)

    def test_get_templates_dir_env_var(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"TEAMWORK_TEMPLATES_DIR": td}):
                resolved = get_templates_dir()
                self.assertEqual(resolved, Path(td))

    def test_get_templates_dir_fallbacks(self):
        import os
        from unittest.mock import patch
        # Test when env var points to non-existent dir, and repo dir doesn't exist
        with patch.dict(os.environ, {"TEAMWORK_TEMPLATES_DIR": "non_existent_dir_999"}):
            orig_is_dir = Path.is_dir
            def mock_is_dir(path_obj):
                # Simulate repo templates not existing, but package templates existing
                if "templates" in str(path_obj) and str(path_obj).endswith("teamwork_engine\\templates"):
                    return True
                return orig_is_dir(path_obj)

            with patch.object(Path, "is_dir", mock_is_dir):
                resolved = get_templates_dir()
                self.assertTrue(str(resolved).endswith("templates"))

    def test_load_template_with_dot_md(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "custom.md").write_text("# Custom Template\nClean content", encoding="utf-8")
            loaded = load_template("custom.md", templates_dir=p)
            self.assertIn("Custom Template", loaded)


if __name__ == "__main__":
    unittest.main()

