"""Task clarification and specification rewriting engine.

Transforms raw, conversational user prompts into unambiguous, self-contained
specifications without altering intent or omitting negative constraints.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ClarifiedTask:
    """Standardized representation of a clarified task brief."""

    goal: str
    environment_context: Dict[str, str] = field(default_factory=dict)
    inputs_and_existing_work: List[str] = field(default_factory=list)
    required_work: List[str] = field(default_factory=list)
    constraints_and_invariants: List[str] = field(default_factory=list)
    deliverables_and_acceptance_numbers: List[Dict[str, Any]] = field(default_factory=list)
    material_assumptions: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the clarified task as a structured Markdown document."""
        lines: List[str] = ["# Clarified Task Specification", ""]

        lines.extend(["## Goal", self.goal.strip(), ""])

        lines.append("## Environment Context")
        if self.environment_context:
            for k, v in self.environment_context.items():
                lines.append(f"- **{k}**: {v}")
        else:
            lines.append("- (Standard host environment)")
        lines.append("")

        lines.append("## Inputs & Existing Work")
        if self.inputs_and_existing_work:
            for item in self.inputs_and_existing_work:
                lines.append(f"- {item}")
        else:
            lines.append("- None specified")
        lines.append("")

        lines.append("## Required Work")
        if self.required_work:
            for idx, item in enumerate(self.required_work, start=1):
                lines.append(f"{idx}. {item}")
        else:
            lines.append("1. Execute stated goal")
        lines.append("")

        lines.append("## Constraints & Protected Invariants")
        if self.constraints_and_invariants:
            for item in self.constraints_and_invariants:
                lines.append(f"- {item}")
        else:
            lines.append("- Standard non-destructive modifications; no arbitrary deletions")
        lines.append("")

        lines.append("## Deliverables & Acceptance Numbers")
        if self.deliverables_and_acceptance_numbers:
            for item in self.deliverables_and_acceptance_numbers:
                metric = item.get("metric", "Deliverable")
                target = item.get("target", "Completed")
                desc = item.get("description", "")
                if desc:
                    lines.append(f"- **{metric}**: {target} ({desc})")
                else:
                    lines.append(f"- **{metric}**: {target}")
        else:
            lines.append("- **Verification**: Exit code 0 on test execution")
        lines.append("")

        lines.append("## Material Assumptions")
        if self.material_assumptions:
            for item in self.material_assumptions:
                lines.append(f"- {item}")
        else:
            lines.append("- No unverified assumptions made")
        lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard dictionary."""
        return asdict(self)

    def validate_against_raw(self, raw_task: str) -> List[str]:
        """Verify that negative constraints and paths from raw_task were preserved.

        Returns a list of warning or defect strings. Empty list indicates full compliance.
        """
        defects: List[str] = []

        # 1. Negative constraints check
        negative_patterns = [
            r"\bnever\s+[^.,;\n]+",
            r"\bdo\s+not\s+[^.,;\n]+",
            r"\bdon't\s+[^.,;\n]+",
            r"\bzero\s+[^.,;\n]+",
            r"\bmust\s+not\s+[^.,;\n]+",
            r"\bprohibited\b[^.,;\n]+",
            r"\bno\s+(?:deletions?|saving|writes?|killing)\b[^.,;\n]*",
        ]
        raw_negatives: List[str] = []
        for pat in negative_patterns:
            matches = re.findall(pat, raw_task, re.IGNORECASE)
            raw_negatives.extend([m.strip() for m in matches])

        combined_constraints = " ".join(self.constraints_and_invariants).lower()
        for neg in raw_negatives:
            # Check key terms from the raw negative clause
            keywords = [w.lower() for w in re.findall(r"\b[A-Za-z0-9_-]{3,}\b", neg) if w.lower() not in {"never", "not", "must", "the", "and", "for"}]
            if keywords and not any(kw in combined_constraints for kw in keywords):
                defects.append(f"Potentially omitted negative constraint: '{neg}'")

        # 2. File / Directory paths check
        path_pattern = r"(?:[A-Za-z]:[\\/][\w\s.\\/-]+|/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+)"
        raw_paths = set(re.findall(path_pattern, raw_task))
        all_text = (
            self.goal
            + " "
            + " ".join(self.inputs_and_existing_work)
            + " "
            + " ".join(self.required_work)
            + " "
            + " ".join(self.constraints_and_invariants)
            + " "
            + str(self.environment_context)
            + " "
            + str(self.deliverables_and_acceptance_numbers)
        )
        for path in raw_paths:
            normalized_path = path.replace("\\", "/")
            if normalized_path not in all_text.replace("\\", "/"):
                defects.append(f"Referenced path '{path}' not found in clarified specification")

        return defects


def clarify_task(raw_task: str, context: Optional[str] = None) -> ClarifiedTask:
    """Parse and transform a raw task prompt into a structured ClarifiedTask.

    Extracts goal, environment, inputs, required work, constraints, and metrics.
    Raises ValueError if raw_task is empty or only whitespace.
    """
    if not raw_task or not raw_task.strip():
        raise ValueError("Task description cannot be empty")

    cleaned_raw = raw_task.strip()
    full_text = f"{cleaned_raw}\n\nContext:\n{context.strip()}" if context and context.strip() else cleaned_raw

    # Extract goal: first sentence or line before blank
    paragraphs = [p.strip() for p in cleaned_raw.split("\n\n") if p.strip()]
    first_block = paragraphs[0] if paragraphs else cleaned_raw
    goal_match = re.search(r"^(?:Goal|Objective|Task):\s*(.+)$", first_block, re.MULTILINE | re.IGNORECASE)
    if goal_match:
        goal = goal_match.group(1).strip()
    else:
        # First sentence or first line
        first_line = first_block.splitlines()[0].strip()
        first_line = re.sub(r"^(?:Please\s+|Could\s+you\s+|I\s+need\s+you\s+to\s+)", "", first_line, flags=re.IGNORECASE)
        goal = first_line

    # Extract Environment Context
    env_context: Dict[str, str] = {}
    if re.search(r"\bwindows\b", full_text, re.IGNORECASE):
        env_context["OS"] = "Windows"
    elif re.search(r"\blinux\b", full_text, re.IGNORECASE):
        env_context["OS"] = "Linux"
    elif re.search(r"\bmacos|darwin\b", full_text, re.IGNORECASE):
        env_context["OS"] = "macOS"

    if re.search(r"\bpwsh|powershell\b", full_text, re.IGNORECASE):
        env_context["Shell"] = "PowerShell (pwsh)"
    elif re.search(r"\bbash\b", full_text, re.IGNORECASE):
        env_context["Shell"] = "Bash"

    gpu_match = re.search(r"\b(RTX\s*\d{4}(?:\s*Ti)?|NVIDIA\s+[\w\s]+|CUDA)\b", full_text, re.IGNORECASE)
    if gpu_match:
        env_context["GPU / Accelerator"] = gpu_match.group(1).strip()

    port_matches = re.findall(r":(\d{4,5})\b", full_text)
    if port_matches:
        env_context["Ports / Endpoints"] = ", ".join(f":{p}" for p in sorted(set(port_matches)))

    # Working directory detection
    workdir_match = re.search(r"(?:Working directory|Target repo(?:sitory)?|Target dir(?:ectory)?):\s*([^\n\r]+)", full_text, re.IGNORECASE)
    if workdir_match:
        env_context["Working Directory"] = workdir_match.group(1).strip()
    else:
        path_match = re.search(r"\b(?:in|at|under|into)\s+([A-Za-z]:[\\/][^\n\r,;()]+)", full_text, re.IGNORECASE)
        if path_match:
            env_context["Working Directory"] = path_match.group(1).strip()

    # Extract Inputs and Existing Work
    inputs: List[str] = []
    handoff_matches = re.findall(r"[\w\\/.-]*handoff[\w\\/.-]*", full_text, re.IGNORECASE)
    inputs.extend(sorted(set(handoff_matches)))
    branch_match = re.search(r"\bbranch\s+([a-zA-Z0-9_.-]+)", full_text, re.IGNORECASE)
    if branch_match:
        inputs.append(f"Git branch: {branch_match.group(1)}")
    ref_matches = re.findall(r"(?:Reference|Survey|Prior work):\s*([^\n\r]+)", full_text, re.IGNORECASE)
    for ref in ref_matches:
        inputs.append(ref.strip())

    # Extract Constraints and Protected Invariants
    constraints: List[str] = []
    constraint_patterns = [
        r"(?:^|\n)[ \t]*[-*]\s*(?:never|do not|don't|zero|must not|prohibited|no)\s+([^\n]+)",
        r"(?:never|do not|don't|must not)\s+([^\n.,;]+)",
        r"(?:preserve|protect|retain)\s+([^\n.,;]+)",
    ]
    for pat in constraint_patterns:
        for match in re.findall(pat, full_text, re.IGNORECASE):
            text_val = match.strip()
            if text_val and text_val not in constraints:
                constraints.append(text_val)

    # Hard-coded check for common fleet invariants
    if re.search(r"zero\s+saves?\s+on\s+C:", full_text, re.IGNORECASE):
        if not any("c:" in c.lower() for c in constraints):
            constraints.append("Zero writes to drive C: (code on S:, media on E:)")
    if re.search(r"never\s+kill\s+user\s+processes?", full_text, re.IGNORECASE):
        if not any("kill" in c.lower() for c in constraints):
            constraints.append("Never terminate protected user processes (chrome, discord, relays)")

    # Extract Required Work
    required_work: List[str] = []
    numbered_steps = re.findall(r"^\s*\d+[\).]\s+(.+)$", cleaned_raw, re.MULTILINE)
    if numbered_steps:
        required_work.extend([s.strip() for s in numbered_steps])
    else:
        bullet_steps = re.findall(r"^\s*[-*]\s+(.+)$", cleaned_raw, re.MULTILINE)
        action_bullets = [b.strip() for b in bullet_steps if not re.match(r"^(?:never|do not|don't|must not|zero)\b", b, re.IGNORECASE)]
        if action_bullets:
            required_work.extend(action_bullets)
        else:
            required_work.append(goal)

    # Extract Deliverables and Acceptance Numbers
    deliverables: List[Dict[str, Any]] = []
    # Check for test criteria
    if re.search(r"pytest|unittest|test suite", full_text, re.IGNORECASE):
        deliverables.append({"metric": "Test Suite Pass Rate", "target": "100%", "description": "All unit & integration tests pass cleanly"})
    coverage_match = re.search(r"(?:coverage|code coverage)\s*[>=:]*\s*(\d+)%", full_text, re.IGNORECASE)
    if coverage_match:
        deliverables.append({"metric": "Code Coverage", "target": f">={coverage_match.group(1)}%", "description": "Statement and branch test coverage"})
    speedup_match = re.search(r"(\d+(?:\.\d+)?x)\s+(?:speedup|faster|acceleration)", full_text, re.IGNORECASE)
    if speedup_match:
        deliverables.append({"metric": "Performance Acceleration", "target": speedup_match.group(1), "description": "Speedup vs baseline"})
    exit_match = re.search(r"exits?\s*(?:code\s*)?0\b", full_text, re.IGNORECASE)
    if exit_match:
        deliverables.append({"metric": "CLI Exit Code", "target": "0", "description": "Commands execute and exit 0"})

    # Material Assumptions
    material_assumptions: List[str] = []
    if not deliverables:
        deliverables.append({"metric": "Execution Status", "target": "Exit 0", "description": "Clean termination with verified behavior"})
        material_assumptions.append("Assumed standard exit code 0 required for all CLI operations")
    if "OS" not in env_context:
        material_assumptions.append("Environment OS not explicitly specified; assumed cross-platform compatibility")

    return ClarifiedTask(
        goal=goal,
        environment_context=env_context,
        inputs_and_existing_work=inputs,
        required_work=required_work,
        constraints_and_invariants=constraints,
        deliverables_and_acceptance_numbers=deliverables,
        material_assumptions=material_assumptions,
    )
