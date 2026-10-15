# Contributing to Teamwork Preview Engine

Thank you for your interest in contributing to the **Teamwork Preview Engine** (`teamwork-engine`). This document provides guidelines for contributing code, prompt templates, documentation, and bug fixes to the repository.

---

## 1. Core Engineering Philosophy

Before contributing, please review our core architectural principles:

1. **Closed-Loop Feedback over Single-Shot Reasoning**: We prioritize fast tool execution, rapid test iteration, and empirical compiler/runtime feedback over prolonged theoretical deliberation.
2. **Zero-Dependency Runtime Core**: The core package (`teamwork_engine`) must strictly rely only on the Python Standard Library (`dataclasses`, `argparse`, `json`, `pathlib`, `re`, `typing`, `sys`, `datetime`). External packages (`pytest`, `pytest-cov`) are permitted strictly as development and testing dependencies.
3. **Integrity Mandate**: All implementations must be genuine. We strictly prohibit dummy/facade implementations, hardcoded test strings, or shortcuts that mimic behavior without maintaining real state.
4. **Zero-Placeholder Invariant**: Prompt templates and production files must contain ZERO occurrences of incomplete markers (`TODO`, `TBD`, `FIXME`, `PLACEHOLDER`, `<insert...`).

---

## 2. Development Setup

### Prerequisites
- Python 3.10 or higher (tested on 3.10, 3.11, and 3.12).
- Git.
- Optional: `uv` (recommended for blazing-fast virtual environment management).

### Initializing the Workspace

```bash
# 1. Clone the repository
git clone https://github.com/teamwork-preview/teamwork-preview-engine.git
cd teamwork-preview-engine

# 2. Create and activate a virtual environment
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate

# 3. Install in editable mode with development/test dependencies
pip install -e .[test]
```

Or using `uv`:
```bash
uv venv
uv pip install -e .[test]
```

---

## 3. Code Style & Standards

### Type Annotations
- Use modern Python 3.10+ type syntax (`from __future__ import annotations`).
- Explicitly type all public function parameters and return values.
- Prefer built-in collections (`list[str]`, `dict[str, Any]`, `tuple[bool, list[str]]`) or `typing` generics.

### Error Handling & CLI Output
- Do not let unhandled tracebacks leak to the user for predictable validation or argument errors. Catch known exceptions, print informative messages to `sys.stderr`, and return standard POSIX exit codes:
  - `0`: Success.
  - `1`: Failure / threshold breach (e.g. `--strict` guardrail violation or validation failure).
  - `2`: Invalid argument or missing required parameter.
- On Windows, ensure stdout and stderr handle UTF-8 / Unicode characters gracefully without throwing `UnicodeEncodeError`.

---

## 4. Prompt Template Contribution Guidelines

All prompt templates reside in `templates/` (and are mirrored in `teamwork_engine/templates/`). If you are adding or modifying a template:

1. **Naming Convention**: Use kebab-case prefixed with `mega-prompt-` (e.g., `mega-prompt-myagent.md`).
2. **Zero Placeholders**: Templates must pass `validate_template()` with 0 errors. Never use `TODO`, `TBD`, `FIXME`, or `<insert...>`.
3. **Formal Interpolation Variables**: Use clean uppercase variable interpolation markers:
   - `{TASK_DESCRIPTION}`: Raw or clarified task goal.
   - `{WORKING_DIR}`: Target workspace directory path.
   - `{VERIFICATION_COMMAND}`: Automated test command to execute.
   - `{TARGET_FILES}`: Explicit file paths.
4. **Clean Code Fences**: Any snippet or code block intended for user copy/paste must contain 100% pure payload with zero conversational instructions inside the code fence. All instructions belong strictly outside and underneath the block.
5. **Operating Guards**:
   - Limit pre-action planning to $\le 500$ tokens.
   - Ban bureaucratic lease files (`LOCKS.md`, `LEASES.md`, `TAKEOVER.md`).
   - Restrict cryptographic hashing to initial preflight and final delivery only.

---

## 5. Testing & Quality Requirements

Every pull request or code change must maintain our rigorous quality gates:

### Running Tests

```bash
# Run pytest with branch coverage enforcement (>= 90%)
uv run pytest

# Alternatively, run using standard library unittest
python -m unittest discover tests
```

### Coverage Invariant
- Statement and branch coverage across `teamwork_engine` must remain **$\ge 90\%$**.
- If adding a new feature or CLI subcommand, add corresponding test cases in `tests/`.

### Validating Templates

Before submitting, verify that all templates pass zero-placeholder validation:

```bash
python -m teamwork_engine.cli template --validate templates/mega-prompt-claude.md
python -m teamwork_engine.cli template --validate templates/mega-prompt-codex.md
python -m teamwork_engine.cli template --validate templates/mega-prompt-grok.md
python -m teamwork_engine.cli template --validate templates/mega-prompt-universal.md
```

---

## 6. Commit & Pull Request Workflow

1. Create a feature branch:
   ```bash
   git checkout -b feat/my-new-feature
   ```
2. Follow Conventional Commits format:
   - `feat(...)`: New capability or feature.
   - `fix(...)`: Bug fix or defect resolution.
   - `docs(...)`: Documentation updates.
   - `test(...)`: Test additions or improvements.
   - `refactor(...)`: Code refactoring without behavior change.
3. Ensure git working tree is clean and all tests pass.
4. Submit pull request with a clear description of changes, rationale, and verification output.
