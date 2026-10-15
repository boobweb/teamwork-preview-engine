"""Command Line Interface for the Teamwork Preview Engine.

Provides subcommands for the 5-stage Mega-Prompt protocol:
- clarify: Stage 0 task brief refinement and specification rewriting.
- preflight: Stage 1 live capability, quota, and process liveness checking.
- rubric: Stage 1 & 2 100-point rubric generation and adversarial self-auditing.
- guardrail: Stage 4 execution-first validator and token efficiency enforcer.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from . import __version__
from .clarify import clarify_task
from .guardrail import GuardrailVerdict, check_guardrail
from .preflight import (
    AgentStatus,
    AgentTarget,
    check_preflight,
    get_fallback_recommendations,
)
from .rubric import create_default_rubric, evaluate_audit
from .templates import (
    list_templates,
    load_template,
    render_template,
    validate_template,
)



def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="teamwork-engine",
        description="High-speed closed-loop 5-stage Mega-Prompt protocol engine for AI coding agents.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Subcommand: clarify
    clarify_parser = subparsers.add_parser(
        "clarify",
        help="Clarify and rewrite raw task prompt into unambiguous specification",
    )
    clarify_parser.add_argument(
        "--task",
        "-t",
        type=str,
        default=None,
        help="Raw task description string",
    )
    clarify_parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="Path to file containing raw task description",
    )
    clarify_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    clarify_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional file path to write results",
    )

    # Subcommand: preflight
    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Check agent availability, live quotas, and fallback routes",
    )
    preflight_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run simulated preflight check without network or disk dependencies",
    )
    preflight_parser.add_argument(
        "--provider",
        "-p",
        choices=["claude", "codex", "grok", "gemini", "squire", "copilot", "all"],
        default="all",
        help="Filter check to specific provider (default: all)",
    )
    preflight_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )
    preflight_parser.add_argument(
        "--workspace",
        "-w",
        type=str,
        default=None,
        help="Custom workspace root directory containing shared/",
    )

    # Subcommand: rubric
    rubric_parser = subparsers.add_parser(
        "rubric",
        help="Generate 100-point rubric or audit execution plan",
    )
    rubric_parser.add_argument(
        "--task",
        "-t",
        type=str,
        required=True,
        help="Task description or goal name for the rubric",
    )
    rubric_parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="JSON string with custom category weights summing to 100",
    )
    rubric_parser.add_argument(
        "--audit",
        type=str,
        default=None,
        help="Optional path to execution plan file to audit against rubric",
    )
    rubric_parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    rubric_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional file path to write results",
    )

    # Subcommand: guardrail
    guardrail_parser = subparsers.add_parser(
        "guardrail",
        help="Validate text against execution-first guardrails (500 token limit, process safety)",
    )
    guardrail_parser.add_argument(
        "--text",
        "-t",
        type=str,
        default=None,
        help="Text string to evaluate",
    )
    guardrail_parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="Path to text or response file to evaluate",
    )
    guardrail_parser.add_argument(
        "--max-tokens",
        type=int,
        default=500,
        help="Maximum theoretical planning tokens permitted before first tool call (default: 500)",
    )
    guardrail_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with exit code 1 if guardrail threshold or process rule is violated",
    )
    guardrail_parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    # Subcommand: template
    template_parser = subparsers.add_parser(
        "template",
        help="Inspect, validate, and render agent-specific mega-prompt templates",
    )
    template_parser.add_argument(
        "--list",
        action="store_true",
        help="List all available templates",
    )
    template_parser.add_argument(
        "--show",
        "-s",
        type=str,
        default=None,
        help="Display the raw content of a specific template by name or path",
    )
    template_parser.add_argument(
        "--validate",
        type=str,
        default=None,
        help="Validate a template content or file path for forbidden placeholder tokens",
    )
    template_parser.add_argument(
        "--render",
        "-r",
        type=str,
        default=None,
        help="Render a template by name with variable substitutions",
    )
    template_parser.add_argument(
        "--var",
        "-v",
        action="append",
        default=[],
        help="Variable substitution in KEY=VAL format (can be specified multiple times)",
    )
    template_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional file path to write rendered or shown output",
    )
    template_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format for list or validation (default: text)",
    )

    return parser



def handle_clarify(args: argparse.Namespace) -> int:
    """Handle clarify subcommand."""
    raw_content = args.task
    if raw_content is None and args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"Error: File not found: {args.file}\n")
            return 2
        raw_content = file_path.read_text(encoding="utf-8", errors="replace")

    if raw_content is None:
        sys.stderr.write("Error: Must provide either --task or --file\n")
        return 2

    if not raw_content.strip():
        sys.stderr.write("Error: Task description cannot be empty\n")
        return 2

    try:
        clarified = clarify_task(raw_content)
    except ValueError as ve:
        sys.stderr.write(f"Error: {ve}\n")
        return 2

    if args.format == "json":
        output_text = json.dumps(clarified.to_dict(), indent=2)
    else:
        output_text = clarified.to_markdown()

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
    else:
        print(output_text)

    return 0


def handle_preflight(args: argparse.Namespace) -> int:
    """Handle preflight subcommand."""
    target_enum = AgentTarget(args.provider)
    workspace = Path(args.workspace) if args.workspace else None

    reports = check_preflight(target=target_enum, dry_run=args.dry_run, workspace_root=workspace)
    fallbacks = get_fallback_recommendations(reports)

    if args.format == "json":
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "dry_run" if args.dry_run else "live",
            "agents": {
                r.provider: {
                    "name": r.provider,
                    "status": r.status.value,
                    "is_available": r.status == AgentStatus.OK,
                    "reset_time": r.retry_at.isoformat() if r.retry_at else None,
                    "details": r.details,
                    "source": r.source,
                }
                for r in reports
            },
            "routing_recommendation": {
                "fallbacks": fallbacks,
            },
        }
        print(json.dumps(data, indent=2))
    else:
        # Table format
        mode_str = "DRY-RUN SIMULATION" if args.dry_run else "LIVE TELEMETRY"
        print(f"=== Teamwork Preflight Check ({mode_str}) ===")
        print(f"{'Provider':<12} | {'Status':<18} | {'Retry At':<20} | {'Details'}")
        print("-" * 80)
        for r in reports:
            retry_str = r.retry_at.strftime("%Y-%m-%d %H:%M") if r.retry_at else "-"
            print(f"{r.provider:<12} | {r.status.value:<18} | {retry_str:<20} | {r.details}")
        print("-" * 80)
        if fallbacks:
            print("Routing Fallback Recommendations:")
            for blocked, replacement in fallbacks.items():
                print(f"  - {blocked} -> {replacement}")

    return 0


def handle_rubric(args: argparse.Namespace) -> int:
    """Handle rubric subcommand."""
    weights_dict = None
    if args.weights:
        try:
            weights_dict = json.loads(args.weights)
        except json.JSONDecodeError as jde:
            sys.stderr.write(f"Error: Invalid JSON for --weights: {jde}\n")
            return 2

    try:
        rubric = create_default_rubric(task_name=args.task, weights=weights_dict)
    except ValueError as ve:
        sys.stderr.write(f"Error: {ve}\n")
        return 2

    if args.audit:
        plan_path = Path(args.audit)
        if not plan_path.exists():
            sys.stderr.write(f"Error: Audit plan file not found: {args.audit}\n")
            return 2
        plan_text = plan_path.read_text(encoding="utf-8", errors="replace")

        # Evaluate plan with genuine heuristics
        token_count = len(plan_text.split())
        score_inputs: dict[str, float] = {}
        deductions_map: dict[str, list[str]] = {}

        for c in rubric.categories:
            score_inputs[c.id] = float(c.max_points)
            deductions_map[c.id] = []

        # Check for scope/fidelity
        if "TODO" in plan_text or "TBD" in plan_text:
            score_inputs["fidelity"] = max(0.0, score_inputs["fidelity"] - 5.0)
            deductions_map["fidelity"].append("Plan contains incomplete markers (TODO/TBD)")

        # Check for safety
        if "rm -rf" in plan_text or "taskkill" in plan_text:
            score_inputs["safety"] = max(0.0, score_inputs["safety"] - 5.0)
            deductions_map["safety"].append("Plan contains potentially hazardous deletion or process kill commands")

        # Check for token efficiency
        if token_count > 1500:
            score_inputs["resources"] = max(0.0, score_inputs["resources"] - 4.0)
            deductions_map["resources"].append(f"Plan is verbose ({token_count} words); risks context overflow")

        audit_result = evaluate_audit(rubric, score_inputs, deductions_map)
        if args.format == "markdown":
            output_text = audit_result.to_markdown_table()
        else:
            output_text = json.dumps(audit_result.to_dict(), indent=2)
    else:
        if args.format == "markdown":
            output_text = rubric.to_markdown()
        else:
            output_text = json.dumps(rubric.to_dict(), indent=2)

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
    else:
        print(output_text)

    return 0


def handle_guardrail(args: argparse.Namespace) -> int:
    """Handle guardrail subcommand."""
    text_content = args.text
    if text_content is None and args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            sys.stderr.write(f"Error: File not found: {args.file}\n")
            return 2
        text_content = file_path.read_text(encoding="utf-8", errors="replace")

    if text_content is None:
        sys.stderr.write("Error: Must provide either --text or --file\n")
        return 2

    report = check_guardrail(
        text=text_content,
        max_tokens=args.max_tokens,
        strict=args.strict,
    )

    if args.output == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"=== Execution-First Guardrail Report ===")
        print(f"Verdict: {report.verdict.value}")
        print(f"Pre-Action Tokens: {report.token_count} (Limit: {report.token_threshold})")
        print(f"Tool Invocations Detected: {report.tool_call_count}")
        if report.protected_process_violations:
            print("\nPROTECTED PROCESS VIOLATIONS:")
            for v in report.protected_process_violations:
                print(f"  [CRITICAL] {v}")
        if report.warnings:
            print("\nWarnings:")
            for w in report.warnings:
                print(f"  [WARN] {w}")

    if args.strict and report.verdict == GuardrailVerdict.FAIL:
        return 1

    return 0


def handle_template(args: argparse.Namespace) -> int:
    """Handle template subcommand."""
    # 1. If --list:
    if args.list:
        templates = list_templates()
        if args.format == "json":
            print(json.dumps({"templates": templates}, indent=2))
        else:
            print("Available Mega-Prompt Templates:")
            for t in templates:
                print(f"  - {t}")
        return 0

    # 2. If --show:
    if args.show:
        try:
            content = load_template(args.show)
        except FileNotFoundError as fnf:
            sys.stderr.write(f"Error: {fnf}\n")
            return 2
        if args.output:
            Path(args.output).write_text(content, encoding="utf-8")
        else:
            print(content)
        return 0

    # 3. If --validate:
    if args.validate:
        target = args.validate
        try:
            if Path(target).is_file():
                is_valid, errors = validate_template(target)
            else:
                try:
                    content = load_template(target)
                    is_valid, errors = validate_template(content)
                except FileNotFoundError:
                    is_valid, errors = validate_template(target)
        except Exception as e:
            sys.stderr.write(f"Error during validation: {e}\n")
            return 2

        if args.format == "json":
            data = {
                "target": target,
                "valid": is_valid,
                "errors": errors,
            }
            print(json.dumps(data, indent=2))
        else:
            if is_valid:
                print(f"PASS: Template '{target}' contains ZERO placeholders.")
            else:
                print(f"FAIL: Template '{target}' failed validation with {len(errors)} error(s):")
                for err in errors:
                    print(f"  - {err}")

        return 0 if is_valid else 1

    # 4. If --render:
    if args.render:
        variables: dict[str, str] = {}
        for var_entry in args.var or []:
            if "=" not in var_entry:
                sys.stderr.write(f"Error: Invalid variable format '{var_entry}'. Expected KEY=VAL\n")
                return 2
            k, v = var_entry.split("=", 1)
            variables[k.strip()] = v.strip()

        try:
            rendered = render_template(args.render, variables=variables)
        except FileNotFoundError as fnf:
            sys.stderr.write(f"Error: {fnf}\n")
            return 2

        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            print(rendered)
        return 0

    sys.stderr.write("Error: Must specify one of --list, --show, --validate, or --render\n")
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    """CLI main entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = build_parser()
    args = parser.parse_args(argv)


    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "clarify":
        return handle_clarify(args)
    elif args.subcommand == "preflight":
        return handle_preflight(args)
    elif args.subcommand == "rubric":
        return handle_rubric(args)
    elif args.subcommand == "guardrail":
        return handle_guardrail(args)
    elif args.subcommand == "template":
        return handle_template(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

