# Teamwork Preview Engine (`teamwork-engine`)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Coverage: 93%+](https://img.shields.io/badge/coverage-93%25-brightgreen.svg)](tests/)
[![Code Style: Clean](https://img.shields.io/badge/code%20style-clean-black.svg)](CONTRIBUTING.md)

High-speed closed-loop 5-stage Mega-Prompt protocol engine and agent governors for autonomous AI coding agents (Claude Code, Codex, Grok Build, Gemini, and universal harnesses).

---

## 1. The Core Thesis: Closed-Loop Feedback vs. Single-Shot Reasoning

Modern frontier language models excel at parametric reasoning but fail catastrophically when forced to execute complex, multi-step systems engineering tasks in an open-loop manner:

1. **The Analysis Paralysis Tax**: Frontier models frequently emit 2,000–4,000 tokens of theoretical architectural essays, speculative plans, lock registries, lease files, and repeated SHA-256 file hashing loops before executing a single inspection tool call. This burns through context windows and rate limits while leaving hardware idle.
2. **Runtime Feedback Dominates Parametric Deliberation**: In real-world systems engineering (operating system APIs, CUDA/ONNX acceleration, process management, dynamic typings), compilers and test runners provide infinitely more ground-truth information than theoretical deliberation. An agent generating tool calls at 150+ tokens/sec that catches compiler feedback and fixes errors in 3 seconds will complete a 20-step task in 2 minutes. A slow model taking 40 seconds per turn generating deep theoretical essays takes 20+ minutes for the same task.
3. **The Core Rule**: **Never substitute theoretical planning for running tests.**

### Empirical Comparison Matrix

| Dimension | Traditional Single-Shot Deliberation | Teamwork-Preview Closed-Loop Protocol |
| :--- | :--- | :--- |
| **Pre-Execution Planning** | 2,000 – 4,000 tokens of theoretical prose | $\le$ 500 tokens strict budget before tool invocation |
| **Error Recovery** | Hallucinates post-hoc rationalizations | Captures compiler line/column and patches in < 3s |
| **Administrative Bloat** | Generates lock files, lease docs, takeover files | **Zero bureaucracy**: direct file actions and test suites |
| **Verification Gate** | "Looks finished" textual assertion | **Dual-Gate**: Unit tests exit 0 + empirical metrics |
| **Token Efficiency** | High token waste (frequent context overflow) | Maximum tool-to-thought ratio (> 80% tool velocity) |

---

## 2. The 5-Stage Mega-Prompt Lifecycle

The Teamwork-Preview Engine formalizes the engineering lifecycle into five discrete, falsifiable stages:

```
  ┌────────────────────────────────────────────────────────┐
  │ Stage 0: Clarify & Specification Rewrite               │
  │   - Distill raw task into 6 unambiguous sections       │
  │   - Pinpoint environment context, inputs, & invariants │
  └─────────────────────────┬──────────────────────────────┘
                            │
  ┌─────────────────────────▼──────────────────────────────┐
  │ Stage 1: Capability Preflight & Dynamic Rubric         │
  │   - Verify live quotas, keys, and endpoint health      │
  │   - Construct 100-point rubric across 5 core dimensions│
  └─────────────────────────┬──────────────────────────────┘
                            │
  ┌─────────────────────────▼──────────────────────────────┐
  │ Stage 2: Adversarial Audit                             │
  │   - Skeptical reviewer critique before heavy edits     │
  │   - Identify unhandled edge cases & point deductions   │
  └─────────────────────────┬──────────────────────────────┘
                            │
  ┌─────────────────────────▼──────────────────────────────┐
  │ Stage 3: Surgical Correction                           │
  │   - Map each gap: Defect -> Correction -> Validation   │
  │   - Update plan to reach 100/100 readiness             │
  └─────────────────────────┬──────────────────────────────┘
                            │
  ┌─────────────────────────▼──────────────────────────────┐
  │ Stage 4 & 5: Closed-Loop Execution & Dual-Gate Verify   │
  │   - Immediate tool invocation (<500 planning tokens)   │
  │   - Functional Gate: pytest / unittest pass 100%       │
  │   - Fidelity Gate: Empirical performance thresholds    │
  └────────────────────────────────────────────────────────┘
```

1. **Stage 0: Clarify & Specification Rewrite (`teamwork_engine.clarify`)**:
   Transforms unstructured or conversational prompts into standardized 6-section specifications: Goal, Environment Context, Inputs & Existing Work, Required Work, Constraints & Protected Invariants, and Deliverables & Acceptance Numbers.
2. **Stage 1: Capability Preflight & 100-Point Dynamic Rubric (`teamwork_engine.preflight`, `teamwork_engine.rubric`)**:
   Verifies live agent availability, detects HTTP 429 quota limits or HTTP 402 billing blocks with wall-clock retry parsing, and generates a task-specific 100-point rubric across 5 balanced dimensions:
   - *Fidelity to Intent & Scope* (25 pts)
   - *Hardware & Architectural Feasibility* (20 pts)
   - *Safety, Isolation & Non-Destruction* (20 pts)
   - *Resource Management & Memory Recovery* (15 pts)
   - *Empirical Verification Rigor* (20 pts)
3. **Stage 2: Adversarial Audit (`teamwork_engine.rubric`)**:
   Critiques the proposed approach from an independent, skeptical auditor's perspective, scoring each dimension with itemized deductions.
4. **Stage 3: Surgical Correction**:
   Maps every identified gap directly into a concrete code-level fix (`Defect -> Correction -> Validation Method`).
5. **Stage 4 & 5: Immediate Execution & Dual-Gate Verification (`teamwork_engine.guardrail`)**:
   Executes changes with an enforced 500-token planning limit before first tool invocation. Acceptance requires passing both the **Functional Gate** (tests exit code 0) and the **Fidelity Gate** (empirical quantitative metrics).

---

## 3. Architecture & Package Structure

```text
teamwork-preview-engine/
├── pyproject.toml              # PEP 621 packaging metadata & zero-dependency core
├── README.md                   # Core thesis, architecture, and documentation
├── CONTRIBUTING.md             # Development, testing, and contribution standards
├── templates/                  # Production agent mega-prompt templates (0 placeholders)
│   ├── mega-prompt-claude.md   # Curbs verbosity, lease files, redundant hashing
│   ├── mega-prompt-codex.md    # Autonomous script execution & self-verification
│   ├── mega-prompt-grok.md     # Rapid command dispatch & compiler diagnostic triage
│   └── mega-prompt-universal.md# Platform-agnostic system prompt for any agent harness
├── teamwork_engine/            # Pure Python 3.10+ package (Zero external runtime dependencies)
│   ├── __init__.py             # Public API exports and versioning
│   ├── __main__.py            # Module entrypoint: python -m teamwork_engine
│   ├── cli.py                 # Multi-command CLI (clarify, preflight, rubric, guardrail, template)
│   ├── clarify.py             # Stage 0: Prompt distillation & markdown/JSON specification generator
│   ├── preflight.py           # Stage 1: Capability checker, quota parser, provider fallback matrix
│   ├── rubric.py              # Stage 1 & 2: 100-point dynamic rubric engine & audit evaluator
│   ├── guardrail.py           # Stage 4: Execution-first validator (>500 token detector, safety rules)
│   └── templates.py           # Template loader, renderer, and zero-placeholder validator
├── docs/                       # Case studies and technical specifications
│   └── case_study_rtx5070ti.md # Authoritative RTX 5070 Ti 3.01x / 12.95x optimization case study
└── tests/                      # Comprehensive test suite (>= 90% coverage enforced)
    ├── __init__.py
    ├── test_clarify.py         # Specification extraction tests
    ├── test_cli.py             # CLI parser and subcommand routing tests
    ├── test_guardrail.py       # Execution-first guardrail tests
    ├── test_preflight.py       # Live & dry-run quota verification tests
    ├── test_rubric.py          # 100-point rubric math and grading tests
    ├── test_templates.py       # Template loading, rendering, and validation tests
    └── test_adversarial_stress.py # Stress and boundary condition verification
```

---

## 4. Agent Governor Profiles

Each major AI coding agent exhibits distinct cognitive failure modes. `teamwork-engine` provides battle-tested templates tuned to govern each agent's behavior:

### Claude Code (Piper) — `mega-prompt-claude.md`
- **Failure Mode Solved**: Token verbosity, multi-page theoretical essays, redundant SHA-256 file hashing loops, and creation of administrative lease/lock files (`LOCKS.md`, `LEASES.md`).
- **Governor Mechanism**: Enforces a strict 500-token planning budget before tool invocation, bans lease/lock file creation, throttles hashing to start/finish only, and enforces clean copyable payloads without conversational meta-notes inside code fences.

### OpenAI / Codex (Ava) — `mega-prompt-codex.md`
- **Failure Mode Solved**: Permission-seeking conversational chatter ("Would you like me to proceed with step 2?"), UNIX bashisms on Windows, and untested file modifications.
- **Governor Mechanism**: Authorizes end-to-end execution, eliminates interactive pauses, enforces PowerShell execution discipline, and requires immediate subprocess self-testing.

### Grok Build (Roxy) — `mega-prompt-grok.md`
- **Failure Mode Solved**: Unfocused scope drift and parsing churn on compiler logs.
- **Governor Mechanism**: Directs immediate command dispatch, extracts exact line/column diagnostics (`file:line:col`), and enforces a 2-step syntax/build healing loop.

### Universal Harness — `mega-prompt-universal.md`
- **Failure Mode Solved**: Vendor API lock-in and hallucinated platform tools.
- **Governor Mechanism**: Standardized 5-stage closed-loop execution protocol applicable to any local or cloud LLM harness (Ollama, vLLM, DeepSeek, Qwen, or OpenAI-compatible endpoints).

---

## 5. Empirical Benchmark: Live RTX 5070 Ti Optimization

The effectiveness of the closed-loop execution protocol is proven through real-world deployment on workstation creative pipelines (`motion_kneel_sit` seed 101, 81 frames, 1024x1024 $\to$ 2048x2048 Lanczos upscale):

| Metric | Baseline (Pre-Optimization) | Optimized (GPU-First) | Empirical Speedup |
| :--- | :--- | :--- | :--- |
| **End-to-End Clip Production** | 13.2 minutes (792 s) | 4.38 minutes (262.8 s) | **3.01x faster** (66.8% runtime reduction) |
| **Video Swap Stage Duration** | 518 seconds (8.63 min) | 40 seconds (0.67 min) | **12.95x faster** (92.3% runtime reduction) |
| **GPU Utilization (Face Swap)** | 8% – 10% (CPU bottleneck) | 99% peak (CUDA/TensorRT) | **+89% peak utilization** |
| **System RAM Usage** | 31.3 GB (97% ceiling) | 15.1 GB (post-purge) | **16.2+ GB RAM reclaimed** |
| **VRAM Usage** | ~10.4 GB cached idle | Purged between jobs | **8.7+ GB VRAM reclaimed** |
| **Face Embedding Cosine Difference** | Baseline CPU Embedding | CUDA InsightFace Embedding | **0.00471** (well within $\le 0.01$ fidelity gate) |

For complete root-cause analysis, hardware telemetry, and architectural findings, see [docs/case_study_rtx5070ti.md](docs/case_study_rtx5070ti.md).

---

## 6. Quickstart & Installation

### Installation

```bash
# Clone the repository
git clone https://github.com/teamwork-preview/teamwork-preview-engine.git
cd teamwork-preview-engine

# Editable install with dev dependencies
pip install -e .[test]
```

`teamwork-engine` core has **zero external runtime dependencies** and runs on any standard Python 3.10+ installation.

### CLI Usage

The CLI is executable via `teamwork`, `teamwork-engine`, or `python -m teamwork_engine.cli`:

```bash
# 1. Clarify a raw task description into a structured specification
teamwork clarify --task "Add a caching layer to our SQLite database with TTL expiration"

# 2. Check live quota availability across agent providers
teamwork preflight --dry-run

# 3. Generate a 100-point dynamic rubric for a task
teamwork rubric --task "Implement Live2D Rig Truth Harness"

# 4. Audit an execution plan against the rubric
teamwork rubric --task "Implement Live2D Rig Truth Harness" --audit plan.md

# 5. Check response text against execution-first guardrails (500 token planning limit)
teamwork guardrail --text "Here is a brief 20-word plan..." --strict

# 6. List, view, validate, and render agent mega-prompt templates
teamwork template --list
teamwork template --show claude
teamwork template --validate templates/mega-prompt-universal.md
teamwork template --render codex --var TASK_DESCRIPTION="Implement auth module" --var WORKING_DIR="./src"
```

### Python API

```python
from teamwork_engine import (
    clarify_task,
    check_preflight,
    create_default_rubric,
    check_guardrail,
    load_template,
    render_template,
    validate_template,
)

# Clarify task
task_spec = clarify_task("Refactor authentication module to support JWT tokens")
print(task_spec.to_markdown())

# Render and validate template
rendered_prompt = render_template(
    "claude",
    variables={
        "TASK_DESCRIPTION": "Refactor auth module",
        "WORKING_DIR": "/workspace",
        "VERIFICATION_COMMAND": "pytest tests/test_auth.py",
    },
)
is_valid, errors = validate_template(rendered_prompt)
assert is_valid, f"Template had validation errors: {errors}"
```

---

## 7. Testing & Verification

The test suite validates 100% of statements and branches across all modules without external network dependencies:

```bash
# Run pytest with strict coverage enforcement (>= 90%)
uv run pytest

# Alternatively, run using Python standard library unittest runner
python -m unittest discover tests
```

---

## 8. License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
