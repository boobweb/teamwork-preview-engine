"""Execution-First guardrail and token efficiency validation engine.

Detects analysis paralysis, enforces the 500-token planning limit before tool calls,
and guards against protected process termination and bureaucratic lease antipatterns.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GuardrailVerdict(str, Enum):
    """Guardrail outcome evaluation verdict."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


# Protected processes that must never be terminated
PROTECTED_PROCESSES = [
    "chrome",
    "discord",
    "code",
    "claude",
    "agy",
    "codex",
    "grok",
    "relaywatcher",
    "gpuq",
    "comfyui",
    "tailscale",
    "streamdeck",
    "openrgb",
]

# Standard tool call patterns in agent environments
DEFAULT_TOOL_PATTERNS = [
    r"\brun_command\b",
    r"\bview_file\b",
    r"\bwrite_to_file\b",
    r"\breplace_file_content\b",
    r"\blist_dir\b",
    r"\bgrep_search\b",
    r"\bcall_mcp_tool\b",
    r"\bsend_message\b",
    r"```(?:powershell|pwsh|bash|sh|cmd|python)",
    r"\bgpuq\.py\s+add\b",
    r"\bpytest\b",
    r"\bpython\s+-m\b",
    r"\bgit\s+(?:commit|add|status|diff|checkout|init)\b",
]

# Bureaucratic antipatterns
ANTIPATTERN_PATTERNS = [
    (r"\b(?:create|write|touch)\s+['\"`]?\w*[\\/]*(?:LEASE|TAKEOVER|LOCKS)\.md\b", "Creation of bureaucratic lease or lock manifests (prohibited by Execution-First rule)"),
    (r"\bcompute\s+sha-?256\s+hash(?:es)?\s+of\s+all\b", "Redundant recursive hashing loop detected"),
]


@dataclass
class GuardrailReport:
    """Detailed guardrail analysis report."""

    verdict: GuardrailVerdict
    token_count: int
    token_threshold: int
    tool_call_count: int
    warnings: List[str] = field(default_factory=list)
    protected_process_violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "verdict": self.verdict.value,
            "token_count": self.token_count,
            "token_threshold": self.token_threshold,
            "tool_call_count": self.tool_call_count,
            "warnings": self.warnings,
            "protected_process_violations": self.protected_process_violations,
        }

    def summary(self) -> str:
        """Render concise human-readable summary."""
        parts = [
            f"Verdict: {self.verdict.value}",
            f"Pre-action tokens: {self.token_count} / {self.token_threshold}",
            f"Tool calls detected: {self.tool_call_count}",
        ]
        if self.protected_process_violations:
            parts.append(f"VIOLATIONS: {'; '.join(self.protected_process_violations)}")
        if self.warnings:
            parts.append(f"Warnings: {'; '.join(self.warnings)}")
        return " | ".join(parts)


def estimate_tokens(text: str) -> int:
    """Calculate token count using fast character-and-word heuristic."""
    if not text:
        return 0

    char_based = math.ceil(len(text) / 4.0)
    words = len(text.split())
    word_based = math.ceil(words * 1.33)
    return max(char_based, word_based)


def check_guardrail(
    text: str,
    max_tokens: int = 500,
    strict: bool = False,
    tool_call_patterns: Optional[List[str]] = None,
) -> GuardrailReport:
    """Analyze agent response text against execution-first guardrails.

    Detects:
    1. Pre-action theoretical planning token volume (> max_tokens without tools).
    2. Protected user process termination attempts.
    3. Bureaucracy antipatterns (leases, takeover files, excessive hashing).
    """
    patterns = tool_call_patterns or DEFAULT_TOOL_PATTERNS
    warnings: List[str] = []
    process_violations: List[str] = []

    # 1. Check for protected process termination
    # Forward command termination: Stop-Process, taskkill, kill, pkill, killall
    termination_regex = re.compile(
        r"(?:Stop-Process|kill|taskkill|pkill|killall)\b(?:\s+-(?:[a-zA-Z0-9]+|Name|ProcessName|Force|Confirm:false|\d+)|/[a-zA-Z0-9]+|[\s\"'])*?\b("
        + "|".join(PROTECTED_PROCESSES)
        + r")(?:\.exe)?\b",
        re.IGNORECASE,
    )
    for match in termination_regex.finditer(text):
        proc = match.group(1)
        violation_str = f"Attempted termination of protected process: '{proc}'. Violates fleet coexistence safety invariant."
        if violation_str not in process_violations:
            process_violations.append(violation_str)

    # Pipeline process termination: Get-Process <proc> | Stop-Process
    pipeline_regex = re.compile(
        r"(?:Get-Process|gps)\s+(?:-Name\s+)?['\"]?("
        + "|".join(PROTECTED_PROCESSES)
        + r")['\"]?\b[^\n\r|]*?\|\s*(?:Stop-Process|spps|kill)\b",
        re.IGNORECASE,
    )
    for match in pipeline_regex.finditer(text):
        proc = match.group(1)
        violation_str = f"Attempted termination of protected process: '{proc}'. Violates fleet coexistence safety invariant."
        if violation_str not in process_violations:
            process_violations.append(violation_str)

    # 2. Check for administrative antipatterns
    for pat, desc in ANTIPATTERN_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            warnings.append(desc)

    # 3. Locate earliest tool call or executable action
    earliest_tool_pos: Optional[int] = None
    tool_call_count = 0

    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            tool_call_count += 1
            if earliest_tool_pos is None or match.start() < earliest_tool_pos:
                earliest_tool_pos = match.start()

    # Pre-action text is everything before the first tool call
    if earliest_tool_pos is not None:
        pre_action_text = text[:earliest_tool_pos].strip()
    else:
        pre_action_text = text.strip()

    pre_action_tokens = estimate_tokens(pre_action_text)

    # Determine verdict
    if process_violations:
        verdict = GuardrailVerdict.FAIL
    elif pre_action_tokens > max_tokens and tool_call_count == 0:
        warning_msg = (
            f"Exceeded {max_tokens} token theoretical planning limit "
            f"({pre_action_tokens} tokens counted) without executable tool invocation."
        )
        warnings.append(warning_msg)
        verdict = GuardrailVerdict.FAIL if strict else GuardrailVerdict.WARN
    elif pre_action_tokens > max_tokens and tool_call_count > 0:
        warning_msg = (
            f"High pre-action prose ({pre_action_tokens} tokens before first tool call). "
            f"Consider invoking inspection tools earlier."
        )
        warnings.append(warning_msg)
        verdict = GuardrailVerdict.WARN
    else:
        verdict = GuardrailVerdict.PASS

    return GuardrailReport(
        verdict=verdict,
        token_count=pre_action_tokens,
        token_threshold=max_tokens,
        tool_call_count=tool_call_count,
        warnings=warnings,
        protected_process_violations=process_violations,
    )
