"""100-Point Rubric generation and adversarial self-audit evaluation engine.

Implements the 5-category evaluation framework (25/20/20/15/20) with strict
mathematical validation, grading (A+ through F), and audit table rendering.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RubricCategory:
    """Single evaluation category in a 100-point rubric."""

    id: str
    name: str
    max_points: int
    description: str
    evaluation_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert category to dictionary."""
        return asdict(self)


@dataclass
class Rubric:
    """100-point rubric definition for assessing plans and implementations."""

    task_name: str
    categories: List[RubricCategory]
    total_points: int = 100

    def __post_init__(self) -> None:
        """Validate that categories sum to exactly total_points."""
        actual_sum = sum(c.max_points for c in self.categories)
        if actual_sum != self.total_points:
            raise ValueError(
                f"Rubric category weights must sum to exactly {self.total_points} (got {actual_sum})"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert rubric to dictionary."""
        return {
            "task_name": self.task_name,
            "total_points": self.total_points,
            "categories": [c.to_dict() for c in self.categories],
        }

    def to_markdown(self) -> str:
        """Render rubric criteria as structured Markdown."""
        lines = [
            f"# Evaluation Rubric: {self.task_name}",
            f"**Total Points**: {self.total_points}",
            "",
            "| Category | Weight (Pts) | Description |",
            "| :--- | :---: | :--- |",
        ]
        for c in self.categories:
            lines.append(f"| **{c.name}** | {c.max_points} | {c.description} |")
        lines.append("")

        for c in self.categories:
            lines.append(f"### {c.name} ({c.max_points} pts)")
            lines.append(c.description)
            if c.evaluation_criteria:
                lines.append("")
                lines.append("**Key Evaluation Criteria:**")
                for crit in c.evaluation_criteria:
                    lines.append(f"- {crit}")
            lines.append("")

        return "\n".join(lines)


@dataclass
class AuditScore:
    """Audited score for an individual rubric category."""

    category_id: str
    score: float
    deductions: List[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditResult:
    """Aggregated adversarial audit result."""

    rubric: Rubric
    scores: List[AuditScore]
    total_score: float
    percentage: float
    letter_grade: str
    verdict: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.rubric.task_name,
            "total_score": self.total_score,
            "max_score": self.rubric.total_points,
            "percentage": self.percentage,
            "letter_grade": self.letter_grade,
            "verdict": self.verdict,
            "scores": [s.to_dict() for s in self.scores],
        }

    def to_markdown_table(self) -> str:
        """Render standard 6-column audit markdown table."""
        cat_map = {c.id: c for c in self.rubric.categories}
        lines = [
            f"# Adversarial Audit Report: {self.rubric.task_name}",
            "",
            f"**Overall Score**: {self.total_score:.1f} / {self.rubric.total_points} ({self.percentage:.1f}%)",
            f"**Letter Grade**: {self.letter_grade} | **Verdict**: {self.verdict}",
            "",
            "| Category | Weight | Deductions / Gaps | Points Earned | Letter Grade |",
            "| :--- | :---: | :--- | :---: | :---: |",
        ]

        for s in self.scores:
            cat = cat_map.get(s.category_id)
            name = cat.name if cat else s.category_id
            weight = cat.max_points if cat else 0
            cat_pct = (s.score / weight * 100.0) if weight > 0 else 0.0
            cat_grade = calculate_letter_grade(cat_pct)
            deductions_str = "; ".join(s.deductions) if s.deductions else "None (Full compliance)"
            lines.append(
                f"| {name} | {weight} | {deductions_str} | {s.score:.1f} | {cat_grade} |"
            )

        lines.append(
            f"| **Total / Overall** | **{self.rubric.total_points}** | — | **{self.total_score:.1f}** | **{self.letter_grade}** |"
        )
        return "\n".join(lines)


def calculate_letter_grade(percentage: float) -> str:
    """Calculate letter grade based on strict protocol thresholds."""
    if percentage >= 100.0:
        return "A+"
    elif percentage >= 90.0:
        return "A"
    elif percentage >= 80.0:
        return "B"
    elif percentage >= 70.0:
        return "C"
    elif percentage >= 60.0:
        return "D"
    else:
        return "F"


def create_default_rubric(
    task_name: str,
    weights: Optional[Dict[str, int]] = None,
) -> Rubric:
    """Construct the canonical 100-point 5-category rubric.

    Default weights:
    - fidelity: 25
    - feasibility: 20
    - safety: 20
    - resources: 15
    - verification: 20
    """
    w = weights or {
        "fidelity": 25,
        "feasibility": 20,
        "safety": 20,
        "resources": 15,
        "verification": 20,
    }

    # Verify input sum
    actual_sum = sum(w.values())
    if actual_sum != 100:
        raise ValueError(
            f"Rubric category weights must sum to exactly 100 (got {actual_sum})"
        )

    categories = [
        RubricCategory(
            id="fidelity",
            name="1. Fidelity to Intent & Scope",
            max_points=w.get("fidelity", 25),
            description="Complete alignment with user core requirements, numbers, and zero dropped constraints.",
            evaluation_criteria=[
                "Explicit goal and requested deliverables preserved without omission",
                "All negative constraints identified and prioritized",
                "Numerical performance thresholds and acceptance criteria retained",
                "Zero unrequested scope creep or premature refactoring",
            ],
        ),
        RubricCategory(
            id="feasibility",
            name="2. Hardware & Architectural Feasibility",
            max_points=w.get("feasibility", 20),
            description="Compatibility with host platform, GPUs, libraries, file formats, and network ports.",
            evaluation_criteria=[
                "Proper shell and runtime conventions (Windows pwsh / POSIX bash)",
                "Hardware awareness (GPU, VRAM limits, port availability)",
                "Dependencies correctly specified without version conflicts",
                "Clean modular architecture with explicit contracts",
            ],
        ),
        RubricCategory(
            id="safety",
            name="3. Safety, Isolation & Non-Destruction",
            max_points=w.get("safety", 20),
            description="Respect for untouchable processes, non-destructive file handling, and isolation.",
            evaluation_criteria=[
                "Protected user processes never terminated without explicit confirmation",
                "Strict file storage compliance (e.g. zero unauthorized writes to C:)",
                "Non-destructive modifications with rollback and version history preserved",
                "Child repo and submodule isolation maintained",
            ],
        ),
        RubricCategory(
            id="resources",
            name="4. Resource Management & Memory Recovery",
            max_points=w.get("resources", 15),
            description="VRAM/RAM cleanup, process lifecycle management, and token efficiency.",
            evaluation_criteria=[
                "Model memory and cache purging between intensive stages",
                "Batched execution utilized to maximize hardware throughput",
                "Tokens and execution context preserved by avoiding verbose essays",
                "Clean child process teardown on exit",
            ],
        ),
        RubricCategory(
            id="verification",
            name="5. Empirical Verification Rigor",
            max_points=w.get("verification", 20),
            description="Falsifiable tests, dual-gate acceptance, and objective metrics.",
            evaluation_criteria=[
                "Automated unit & integration test coverage (target >= 90%)",
                "Independent non-circular verification methods",
                "Empirical benchmark deltas measured against ground truth",
                "Commands execute with verified exit code 0",
            ],
        ),
    ]

    return Rubric(task_name=task_name, categories=categories, total_points=100)


def evaluate_audit(
    rubric: Rubric,
    score_inputs: Dict[str, float],
    deductions: Optional[Dict[str, List[str]]] = None,
) -> AuditResult:
    """Evaluate audit scores against the rubric and compute letter grades and verdicts."""
    deductions_map = deductions or {}
    cat_map = {c.id: c for c in rubric.categories}

    scores: List[AuditScore] = []
    total_score = 0.0

    for cat in rubric.categories:
        score_val = score_inputs.get(cat.id, float(cat.max_points))
        if score_val < 0.0:
            raise ValueError(f"Score for {cat.id} cannot be negative (got {score_val})")
        if score_val > cat.max_points:
            raise ValueError(
                f"Score for {cat.id} ({score_val}) exceeds maximum weight ({cat.max_points})"
            )

        cat_deductions = deductions_map.get(cat.id, [])
        scores.append(
            AuditScore(
                category_id=cat.id,
                score=score_val,
                deductions=cat_deductions,
                rationale=f"Scored {score_val:.1f}/{cat.max_points}",
            )
        )
        total_score += score_val

    percentage = (total_score / rubric.total_points) * 100.0
    letter_grade = calculate_letter_grade(percentage)

    if percentage >= 90.0:
        verdict = "PASS"
    elif percentage >= 70.0:
        verdict = "REVISE"
    else:
        verdict = "FAIL"

    return AuditResult(
        rubric=rubric,
        scores=scores,
        total_score=total_score,
        percentage=percentage,
        letter_grade=letter_grade,
        verdict=verdict,
    )
