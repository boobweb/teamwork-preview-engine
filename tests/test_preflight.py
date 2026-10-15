"""Tests for teamwork_engine.preflight module."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from teamwork_engine.preflight import (
    AgentStatus,
    AgentTarget,
    QuotaReport,
    check_preflight,
    get_fallback_recommendations,
    parse_retry_timestamp,
    parse_status_from_text,
)


class TestPreflight(unittest.TestCase):
    """Test preflight checking, quota parsing, and fallback matrix."""

    def test_dry_run_all_providers(self):
        reports = check_preflight(target=AgentTarget.ALL, dry_run=True)
        self.assertEqual(len(reports), 6)
        for r in reports:
            self.assertIsInstance(r, QuotaReport)
            self.assertEqual(r.status, AgentStatus.OK)
            self.assertEqual(r.source, "dry_run_simulation")
            d = r.to_dict()
            self.assertEqual(d["status"], "OK")

    def test_dry_run_single_provider(self):
        reports = check_preflight(target=AgentTarget.CLAUDE, dry_run=True)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].provider, "claude")

    def test_parse_status_blocked_quota_with_retry(self):
        text = "Error: You have hit your usage limit. Please try again at 11:30 PM."
        status, retry_at, details = parse_status_from_text(text)
        self.assertEqual(status, AgentStatus.BLOCKED_QUOTA)
        self.assertIsNotNone(retry_at)
        self.assertEqual(retry_at.hour, 23)
        self.assertEqual(retry_at.minute, 30)
        self.assertIn("HTTP 429", details)

    def test_parse_status_blocked_billing(self):
        text = "Error: Payment required. Balance exhausted. HTTP 402."
        status, retry_at, details = parse_status_from_text(text)
        self.assertEqual(status, AgentStatus.BLOCKED_BILLING)
        self.assertIsNone(retry_at)
        self.assertIn("HTTP 402", details)

    def test_parse_status_blocked_auth(self):
        text = "API error: Failed to authenticate. API key missing."
        status, retry_at, details = parse_status_from_text(text)
        self.assertEqual(status, AgentStatus.BLOCKED_AUTH)
        self.assertIn("HTTP 401", details)

    def test_parse_status_blocked_permission(self):
        text = "Fatal: BLOCKED_PERMISSION sandbox tool restriction."
        status, retry_at, details = parse_status_from_text(text)
        self.assertEqual(status, AgentStatus.BLOCKED_PERMISSION)
        self.assertIn("HTTP 403", details)

    def test_parse_status_error_exit_code(self):
        text = "SyntaxError: invalid syntax"
        status, retry_at, details = parse_status_from_text(text, exit_code=1)
        self.assertEqual(status, AgentStatus.ERROR)
        self.assertIn("non-zero exit code: 1", details)

    def test_parse_retry_timestamp_full_date(self):
        text = "try again after Oct 25 2026, 04:15 PM"
        dt = parse_retry_timestamp(text)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 10)
        self.assertEqual(dt.day, 25)
        self.assertEqual(dt.hour, 16)
        self.assertEqual(dt.minute, 15)

    def test_parse_retry_timestamp_past_hour_advances_day(self):
        # A time earlier than now today should advance day
        dt = parse_retry_timestamp("try again at 01:00 AM")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.hour, 1)

    def test_parse_retry_timestamp_invalid(self):
        self.assertIsNone(parse_retry_timestamp("No time here"))

    def test_parse_retry_timestamp_month_end_rollover(self):
        """Simulate month-end dates (Jan 31, Dec 31) when advancing day past midnight."""
        from unittest.mock import patch
        # Test Jan 31 -> Feb 1
        with patch("teamwork_engine.preflight.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 31, 23, 30)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            res = parse_retry_timestamp("try again at 01:00 AM")
            self.assertIsNotNone(res)
            self.assertEqual(res.year, 2026)
            self.assertEqual(res.month, 2)
            self.assertEqual(res.day, 1)

        # Test Dec 31 -> Jan 1 (year rollover)
        with patch("teamwork_engine.preflight.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 12, 31, 23, 30)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            res = parse_retry_timestamp("try again at 01:00 AM")
            self.assertIsNotNone(res)
            self.assertEqual(res.year, 2027)
            self.assertEqual(res.month, 1)
            self.assertEqual(res.day, 1)

    def test_fallback_recommendations(self):
        reports = [
            QuotaReport(provider="claude", status=AgentStatus.BLOCKED_QUOTA),
            QuotaReport(provider="codex", status=AgentStatus.OK),
            QuotaReport(provider="grok", status=AgentStatus.OK),
            QuotaReport(provider="gemini", status=AgentStatus.OK),
            QuotaReport(provider="squire", status=AgentStatus.OK),
            QuotaReport(provider="copilot", status=AgentStatus.OK),
        ]
        fallbacks = get_fallback_recommendations(reports)
        self.assertIn("claude", fallbacks)
        self.assertEqual(fallbacks["claude"], "gemini")

    def test_fallback_all_blocked_recommends_local_gpu_queue(self):
        reports = [
            QuotaReport(provider="claude", status=AgentStatus.BLOCKED_QUOTA),
            QuotaReport(provider="codex", status=AgentStatus.BLOCKED_QUOTA),
            QuotaReport(provider="grok", status=AgentStatus.BLOCKED_QUOTA),
            QuotaReport(provider="gemini", status=AgentStatus.BLOCKED_QUOTA),
            QuotaReport(provider="squire", status=AgentStatus.BLOCKED_QUOTA),
            QuotaReport(provider="copilot", status=AgentStatus.BLOCKED_QUOTA),
        ]
        fallbacks = get_fallback_recommendations(reports)
        for agent in ["claude", "codex", "grok", "gemini"]:
            self.assertIn("Local GPU Queue", fallbacks[agent])

    def test_live_check_with_workspace_outbox(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            claude_outbox = tmp_root / "shared" / "CLAUDE_OUTBOX"
            claude_outbox.mkdir(parents=True)
            res_file = claude_outbox / "RESPONSE_20261014_120000_000.md"
            res_file.write_text("Operation completed successfully. Exit code: 0\nAll tests pass.", encoding="utf-8")

            reports = check_preflight(target=AgentTarget.CLAUDE, dry_run=False, workspace_root=tmp_root)
            self.assertEqual(len(reports), 1)
            self.assertEqual(reports[0].provider, "claude")
            self.assertEqual(reports[0].status, AgentStatus.OK)
            self.assertIn(str(res_file), reports[0].source)

    def test_live_check_with_env_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key"
            try:
                reports = check_preflight(target=AgentTarget.CLAUDE, dry_run=False, workspace_root=tmp_root)
                self.assertEqual(len(reports), 1)
                self.assertEqual(reports[0].provider, "claude")
                self.assertEqual(reports[0].status, AgentStatus.OK)
                self.assertIn("environment_variable", reports[0].source)
            finally:
                del os.environ["ANTHROPIC_API_KEY"]


if __name__ == "__main__":
    unittest.main()
