"""Template management, loading, rendering, and zero-placeholder validation.

Part of the Teamwork Preview Protocol Engine (Milestone 2).
Provides agent-specific mega-prompt templates with strict zero-placeholder guarantees.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Canonical template identifiers mapped to their filename prefixes
CANONICAL_TEMPLATES = ["claude", "codex", "grok", "universal"]

# Regex for forbidden placeholder tokens (case-insensitive where appropriate)
FORBIDDEN_WORD_PATTERNS = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\bPLACEHOLDER\b", re.I),
    re.compile(r"\bINSERT_HERE\b", re.I),
    re.compile(r"<insert[^>]*>", re.I),
    re.compile(r"\[insert[^\]]*\]", re.I),
    re.compile(r"\bTBA\b"),
    re.compile(r"\bXXX\b"),
]


class TemplateValidationError(ValueError):
    """Raised when a template fails validation checks."""

    def __init__(self, message: str, errors: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.errors = errors or []


def get_templates_dir() -> Path:
    """Resolve the directory containing mega-prompt templates.

    Checks:
    1. TEAMWORK_TEMPLATES_DIR environment variable
    2. Repository root templates/ directory (relative to this module)
    3. Package-internal templates/ directory
    4. Current working directory templates/
    """
    env_dir = os.environ.get("TEAMWORK_TEMPLATES_DIR")
    if env_dir:
        candidate = Path(env_dir)
        if candidate.is_dir():
            return candidate

    # Relative to package directory: ../templates (repo root layout)
    repo_templates = Path(__file__).resolve().parent.parent / "templates"
    if repo_templates.is_dir():
        return repo_templates

    # Package-internal templates
    pkg_templates = Path(__file__).resolve().parent / "templates"
    if pkg_templates.is_dir():
        return pkg_templates

    # Working directory fallback
    cwd_templates = Path.cwd() / "templates"
    if cwd_templates.is_dir():
        return cwd_templates

    # Return repo_templates as default expectation
    return repo_templates


def _resolve_template_path(name: str, templates_dir: Optional[Path] = None) -> Path:
    """Resolve a template name or path to a concrete Path object."""
    # Check if direct file path exists
    direct_path = Path(name)
    if direct_path.is_file():
        return direct_path

    base_dir = templates_dir or get_templates_dir()

    # Potential filename variants
    clean_name = name.strip()
    if clean_name.endswith(".md"):
        candidates = [
            base_dir / clean_name,
            base_dir / f"mega-prompt-{clean_name}",
        ]
    else:
        candidates = [
            base_dir / f"mega-prompt-{clean_name}.md",
            base_dir / f"{clean_name}.md",
            base_dir / clean_name,
        ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Template '{name}' not found in directory: {base_dir}. "
        f"Available templates: {', '.join(list_templates(base_dir))}"
    )


def list_templates(templates_dir: Optional[Path] = None) -> List[str]:
    """Return a sorted list of available template identifiers.

    Standard templates return short identifiers: 'claude', 'codex', 'grok', 'universal'.
    Custom templates return their base stem.
    """
    base_dir = templates_dir or get_templates_dir()
    if not base_dir.is_dir():
        return []

    templates: List[str] = []
    for entry in sorted(base_dir.glob("*.md")):
        stem = entry.stem
        if stem.startswith("mega-prompt-"):
            clean_id = stem[len("mega-prompt-") :]
        else:
            clean_id = stem
        if clean_id not in templates:
            templates.append(clean_id)

    return sorted(templates)


def load_template(name: str, templates_dir: Optional[Path] = None) -> str:
    """Load template content by name, identifier, or path.

    Args:
        name: Template identifier (e.g. 'claude', 'mega-prompt-claude', or file path).
        templates_dir: Optional custom directory containing templates.

    Returns:
        The raw template content string.

    Raises:
        FileNotFoundError: If the template cannot be located.
    """
    path = _resolve_template_path(name, templates_dir)
    return path.read_text(encoding="utf-8", errors="replace")


def render_template(
    name: str,
    variables: Optional[Dict[str, str]] = None,
    templates_dir: Optional[Path] = None,
) -> str:
    """Load and render a template with variable substitutions.

    Variables are substituted via `{VARIABLE_NAME}` markers. Unescaped JSON
    or markdown brackets are safely preserved without raising KeyError.

    Args:
        name: Template identifier or file path.
        variables: Dictionary mapping variable names to replacement values.
        templates_dir: Optional custom directory containing templates.

    Returns:
        Rendered template string with substitutions applied.
    """
    content = load_template(name, templates_dir)
    if not variables:
        return content

    rendered = content
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        rendered = rendered.replace(placeholder, str(value))

    return rendered


def validate_template(content_or_path: str) -> Tuple[bool, List[str]]:
    """Validate a template content string or file path for forbidden placeholder tokens.

    Ensures zero instances of TODO, TBD, FIXME, PLACEHOLDER, INSERT_HERE, etc.

    Args:
        content_or_path: Raw template text or a valid file path.

    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    # If it points to an existing file, read it
    path_candidate = Path(content_or_path)
    if path_candidate.is_file():
        text = path_candidate.read_text(encoding="utf-8", errors="replace")
        source_label = str(path_candidate)
    else:
        text = content_or_path
        source_label = "content"

    errors: List[str] = []
    lines = text.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        for pattern in FORBIDDEN_WORD_PATTERNS:
            match = pattern.search(line)
            if match:
                matched_token = match.group(0)
                errors.append(
                    f"Line {line_idx}: Forbidden placeholder token '{matched_token}' detected in {source_label}: {line.strip()}"
                )

    is_valid = len(errors) == 0
    return is_valid, errors
