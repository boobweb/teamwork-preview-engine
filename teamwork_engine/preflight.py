"""Preflight capability and quota verification engine.

Inspects agent capability, rate limit (HTTP 429), and billing (HTTP 402) states
across fleet agents and provides deterministic routing fallbacks.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentTarget(str, Enum):
    """Supported agent targets for preflight checks."""

    CLAUDE = "claude"
    CODEX = "codex"
    GROK = "grok"
    GEMINI = "gemini"
    SQUIRE = "squire"
    COPILOT = "copilot"
    ALL = "all"


class AgentStatus(str, Enum):
    """Normalized status codes for agent readiness and quota."""

    OK = "OK"
    BLOCKED_QUOTA = "BLOCKED_QUOTA"
    BLOCKED_BILLING = "BLOCKED_BILLING"
    BLOCKED_PERMISSION = "BLOCKED_PERMISSION"
    BLOCKED_AUTH = "BLOCKED_AUTH"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    NO_RELAY = "NO_RELAY"


# Authoritative regex patterns from fleet check_preflight.py
BILLING_RE = re.compile(
    r"payment required|balance exhausted|insufficient (?:balance|credits?)|(?:status|http_status\"?:|HTTP|error)\s*\(?402\b",
    re.I,
)
QUOTA_RE = re.compile(
    r"hit your (?:session |usage |weekly |daily |monthly )?limit|usage limit|too many requests|rate[_ ]limit(?:_error| exceeded| reached)|quota (?:exceeded|reached|exhausted)|(?:status|http_status\"?:|HTTP|error)\s*\(?429\b",
    re.I,
)
AUTH_RE = re.compile(
    r"failed to authenticate|not logged in|authentication required|invalid (?:api\s*)?key|api key missing",
    re.I,
)
PERMISSION_RE = re.compile(
    r"blocked_permission|permission denied|sandbox tool restriction|policy rejection|access denied",
    re.I,
)
RETRY_RE = re.compile(
    r"try again (?:at|after)\s+(?:(?P<mon>[A-Za-z]{3})[a-z]*\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<year>\d{4}),?\s+)?(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>[AaPp][Mm])",
    re.I,
)


@dataclass
class QuotaReport:
    """Preflight status report for a single agent provider."""

    provider: str
    status: AgentStatus
    retry_at: Optional[datetime] = None
    details: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary format."""
        d = asdict(self)
        if self.retry_at:
            d["retry_at"] = self.retry_at.isoformat()
        return d


def parse_retry_timestamp(text: str) -> Optional[datetime]:
    """Extract retry-at timestamp from 429 quota message if present."""
    match = RETRY_RE.search(text)
    if not match:
        return None

    try:
        now = datetime.now()
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        ampm = match.group("ampm").upper()
        if ampm == "PM" and hour < 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0

        year = int(match.group("year")) if match.group("year") else now.year
        day = int(match.group("day")) if match.group("day") else now.day
        mon_str = match.group("mon")
        month = now.month
        if mon_str:
            months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
            mon_lower = mon_str.lower()[:3]
            if mon_lower in months:
                month = months.index(mon_lower) + 1

        retry_time = datetime(year, month, day, hour, minute)
        # If no date was provided and time is in past, advance to tomorrow
        if not match.group("day") and retry_time < now:
            retry_time = retry_time.replace(day=now.day + 1)
        return retry_time
    except Exception:
        return None


def parse_status_from_text(content: str, exit_code: Optional[int] = None) -> tuple[AgentStatus, Optional[datetime], str]:
    """Parse text content into AgentStatus, retry_at datetime, and detail message."""
    # Check 402 Billing
    if BILLING_RE.search(content):
        return AgentStatus.BLOCKED_BILLING, None, "Billing limit reached or payment required (HTTP 402)"

    # Check 429 Quota
    if QUOTA_RE.search(content):
        retry_at = parse_retry_timestamp(content)
        retry_str = f" until {retry_at.isoformat()}" if retry_at else ""
        return AgentStatus.BLOCKED_QUOTA, retry_at, f"Rate limit or quota exceeded (HTTP 429){retry_str}"

    # Check Auth
    if AUTH_RE.search(content):
        return AgentStatus.BLOCKED_AUTH, None, "Authentication failure or missing credentials (HTTP 401)"

    # Check Permission
    if PERMISSION_RE.search(content):
        return AgentStatus.BLOCKED_PERMISSION, None, "Operation blocked by permissions or policy gate (HTTP 403)"

    # Check non-zero exit code
    if exit_code is not None and exit_code != 0:
        return AgentStatus.ERROR, None, f"Execution failed with non-zero exit code: {exit_code}"

    return AgentStatus.OK, None, "Operational (Ready for execution)"


def check_preflight(
    target: AgentTarget = AgentTarget.ALL,
    dry_run: bool = False,
    workspace_root: Optional[Path] = None,
) -> List[QuotaReport]:
    """Check live quota and operational readiness across agent providers.

    If dry_run is True, returns simulated telemetry without network or file I/O.
    """
    providers_to_check: List[str]
    if target == AgentTarget.ALL:
        providers_to_check = ["claude", "codex", "grok", "gemini", "squire", "copilot"]
    else:
        providers_to_check = [target.value]

    reports: List[QuotaReport] = []

    if dry_run:
        for p in providers_to_check:
            reports.append(
                QuotaReport(
                    provider=p,
                    status=AgentStatus.OK,
                    details="Simulated active provider (dry-run)",
                    source="dry_run_simulation",
                )
            )
        return reports

    # Live inspection mode
    root = workspace_root or Path(r"s:\claude file dump")
    shared_dir = root / "shared"

    outbox_mapping = {
        "claude": shared_dir / "CLAUDE_OUTBOX",
        "codex": shared_dir / "CODEX_OUTBOX",
        "grok": shared_dir / "GROK_OUTBOX",
        "gemini": shared_dir / "ANTIGRAVITY_OUTBOX",
        "squire": shared_dir / "NEMOTRON_OUTBOX",
        "copilot": shared_dir / "COPILOT_OUTBOX",
    }

    env_key_mapping = {
        "claude": "ANTHROPIC_API_KEY",
        "codex": "OPENAI_API_KEY",
        "grok": "XAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "copilot": "GITHUB_TOKEN",
    }

    for p in providers_to_check:
        outbox_path = outbox_mapping.get(p)
        found_report = False

        if outbox_path and outbox_path.exists():
            files = sorted(
                list(outbox_path.glob("RESPONSE_*.md")) + list(outbox_path.glob("ERROR_*.md")),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if files:
                newest = files[0]
                try:
                    text = newest.read_text(encoding="utf-8", errors="replace")
                    status, retry_at, details = parse_status_from_text(text)
                    reports.append(
                        QuotaReport(
                            provider=p,
                            status=status,
                            retry_at=retry_at,
                            details=details,
                            source=str(newest),
                        )
                    )
                    found_report = True
                except Exception as ex:
                    reports.append(
                        QuotaReport(
                            provider=p,
                            status=AgentStatus.ERROR,
                            details=f"Failed reading telemetry: {ex}",
                            source=str(newest),
                        )
                    )
                    found_report = True

        if not found_report:
            # Check environment variables as secondary signal
            env_var = env_key_mapping.get(p)
            if env_var and os.environ.get(env_var):
                reports.append(
                    QuotaReport(
                        provider=p,
                        status=AgentStatus.OK,
                        details=f"Configured via environment variable {env_var}",
                        source="environment_variable",
                    )
                )
            else:
                reports.append(
                    QuotaReport(
                        provider=p,
                        status=AgentStatus.UNKNOWN,
                        details="No recent outbox telemetry or API key configured",
                        source="none",
                    )
                )

    return reports


def get_fallback_recommendations(reports: List[QuotaReport]) -> Dict[str, str]:
    """Calculate deterministic fallback routing for unavailable agents."""
    status_map = {r.provider: r.status for r in reports}
    fallbacks: Dict[str, str] = {}

    preference_matrix = {
        "claude": ["gemini", "codex", "grok", "squire"],
        "codex": ["gemini", "claude", "grok", "squire"],
        "grok": ["claude", "gemini", "codex", "squire"],
        "gemini": ["codex", "claude", "grok", "squire"],
        "squire": ["codex", "gemini", "claude"],
        "copilot": ["claude", "gemini"],
    }

    for agent, pref_list in preference_matrix.items():
        current_status = status_map.get(agent, AgentStatus.UNKNOWN)
        if current_status not in (AgentStatus.OK,):
            # Agent is blocked or unknown; find first available
            recommended = None
            for candidate in pref_list:
                if status_map.get(candidate) == AgentStatus.OK:
                    recommended = candidate
                    break
            if not recommended:
                recommended = "Local GPU Queue / SQUIRE (Standalone)"
            fallbacks[agent] = recommended

    return fallbacks
