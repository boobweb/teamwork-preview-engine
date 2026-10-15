"""Teamwork Preview Protocol Engine.

High-speed closed-loop 5-stage Mega-Prompt protocol engine for AI coding agents.
"""

from .clarify import ClarifiedTask, clarify_task
from .guardrail import (
    GuardrailReport,
    GuardrailVerdict,
    check_guardrail,
    estimate_tokens,
)
from .preflight import (
    AgentStatus,
    AgentTarget,
    QuotaReport,
    check_preflight,
    get_fallback_recommendations,
)
from .rubric import (
    AuditResult,
    AuditScore,
    Rubric,
    RubricCategory,
    calculate_letter_grade,
    create_default_rubric,
    evaluate_audit,
)

__version__ = "0.1.0"

__all__ = [
    "ClarifiedTask",
    "clarify_task",
    "AgentTarget",
    "AgentStatus",
    "QuotaReport",
    "check_preflight",
    "get_fallback_recommendations",
    "RubricCategory",
    "Rubric",
    "AuditScore",
    "AuditResult",
    "calculate_letter_grade",
    "create_default_rubric",
    "evaluate_audit",
    "GuardrailVerdict",
    "GuardrailReport",
    "estimate_tokens",
    "check_guardrail",
    "__version__",
]
