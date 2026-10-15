"""Tests for __main__.py module."""

import subprocess
import sys
import unittest


class TestMain(unittest.TestCase):
    """Test module invocation via python -m teamwork_engine."""

    def test_module_execution(self):
        result = subprocess.run(
            [sys.executable, "-m", "teamwork_engine", "--version"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("0.1.0", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
