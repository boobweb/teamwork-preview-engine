# Teamwork Preview Engine

High-speed closed-loop 5-stage Mega-Prompt protocol engine for AI coding agents.

## Overview
`teamwork-engine` implements the 5-stage closed-loop execution protocol:
1. **Clarify**: Transform raw prompts into unambiguous specifications.
2. **Preflight**: Verify live agent capability and quota availability.
3. **Adversarial Audit**: Evaluate task plans against a 100-point rubric.
4. **Surgical Correction**: Map identified defects to concrete fixes.
5. **Execution-First Guardrails**: Eliminate token waste and analysis paralysis.

## Quickstart
```bash
python -m teamwork_engine.cli --help
python -m teamwork_engine.cli preflight --dry-run
python -m teamwork_engine.cli rubric --task "My Task"
python -m teamwork_engine.cli clarify --task "My Task"
python -m teamwork_engine.cli guardrail --text "My Plan"
```
