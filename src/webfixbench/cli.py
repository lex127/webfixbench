"""Command-line interface.

    webfixbench list
    webfixbench show CASE_ID
    webfixbench validate
    webfixbench run --provider mock
    webfixbench evaluate results/run.json
    webfixbench report results/run.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import __version__
from .cases import list_suites, load_suite
from .config import DEFAULT_PROMPT, DEFAULT_SUITE, ConfigError, load_pricing, load_prompt
from .evaluator import EvaluationError, evaluate_document, is_evaluation_document, write_evaluation
from .experiment import dry_run_summary, load_experiment, preflight, run_experiment
from .matching import DEFAULT_MATCH_MODE, MATCH_MODES
from .providers import PROVIDERS, ProviderError, get_provider
from .providers.mock import MOCK_MODES
from .report import render_markdown
from .runner import RESULTS_FORMAT_VERSION, read_results, run_suite, write_results
from .schemas import ValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="webfixbench",
        description=(
            "WebFixBench — a reproducible benchmark for LLM-assisted code review "
            "on web-application changes."
        ),
    )
    parser.add_argument("--version", action="version", version=f"webfixbench {__version__}")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="benchmark data root (directory containing suites/); defaults to the checkout",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list cases in a suite")
    list_parser.add_argument("--suite", default=DEFAULT_SUITE)
    list_parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    list_parser.set_defaults(func=cmd_list)

    show_parser = subparsers.add_parser("show", help="show one case, including its diff")
    show_parser.add_argument("case_id")
    show_parser.add_argument("--suite", default=DEFAULT_SUITE)
    show_parser.add_argument("--json", action="store_true")
    show_parser.set_defaults(func=cmd_show)

    validate_parser = subparsers.add_parser("validate", help="validate every case in a suite")
    validate_parser.add_argument("--suite", default=DEFAULT_SUITE)
    validate_parser.set_defaults(func=cmd_validate)

    run_parser = subparsers.add_parser("run", help="run a suite (or single case) against a provider")
    run_parser.add_argument("--suite", default=DEFAULT_SUITE)
    run_parser.add_argument(
        "--case", action="append", dest="cases", default=None, help="run only this case (repeatable)"
    )
    run_parser.add_argument("--provider", default="mock", choices=PROVIDERS)
    run_parser.add_argument("--model", default=None, help="model id (required for paid providers)")
    run_parser.add_argument(
        "--api-type",
        default=None,
        choices=("responses", "chat.completions"),
        help="OpenAI API type (default: responses)",
    )
    run_parser.add_argument(
        "--output-constraint",
        default="json_schema",
        choices=("json_schema", "json_object", "prompt_only"),
        help="provider output constraint; support depends on the selected model",
    )
    run_parser.add_argument("--mock-mode", default="heuristic", choices=MOCK_MODES)
    run_parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    run_parser.add_argument("--temperature", type=float, default=None)
    run_parser.add_argument("--max-output-tokens", type=int, default=2048)
    run_parser.add_argument("--timeout", type=float, default=120.0)
    run_parser.add_argument("--reasoning-effort", default=None)
    run_parser.add_argument("--thinking-mode", choices=("disabled", "adaptive"), default=None)
    run_parser.add_argument("--limit", type=int, default=None, help="run at most N cases")
    run_parser.add_argument("--pricing", type=Path, default=None, help="pricing table JSON")
    run_parser.add_argument("--out", type=Path, default=None, help="write the result file here")
    run_parser.add_argument(
        "--no-raw", action="store_true", help="do not store raw provider text in the result file"
    )
    run_parser.add_argument(
        "--evaluate",
        action="store_true",
        help="score the run immediately and print a summary",
    )
    run_parser.add_argument("--match-mode", default=DEFAULT_MATCH_MODE, choices=MATCH_MODES)
    run_parser.add_argument("--quiet", action="store_true")
    run_parser.set_defaults(func=cmd_run)

    evaluate_parser = subparsers.add_parser("evaluate", help="score a result file")
    evaluate_parser.add_argument("results", type=Path)
    evaluate_parser.add_argument("--suite", default=None, help="override the suite recorded in the file")
    evaluate_parser.add_argument("--match-mode", default=DEFAULT_MATCH_MODE, choices=MATCH_MODES)
    evaluate_parser.add_argument("--out", type=Path, default=None, help="write the evaluation JSON here")
    evaluate_parser.add_argument("--json", action="store_true", help="print the evaluation JSON")
    evaluate_parser.set_defaults(func=cmd_evaluate)

    report_parser = subparsers.add_parser("report", help="render a Markdown report")
    report_parser.add_argument("results", type=Path, help="a result file or an evaluation file")
    report_parser.add_argument("--suite", default=None)
    report_parser.add_argument("--match-mode", default=DEFAULT_MATCH_MODE, choices=MATCH_MODES)
    report_parser.add_argument("--out", type=Path, default=None)
    report_parser.set_defaults(func=cmd_report)

    experiment_parser = subparsers.add_parser("experiment", help="run a validated JSON experiment")
    experiment_parser.add_argument("config", type=Path)
    experiment_parser.add_argument("--dry-run", action="store_true")
    experiment_parser.add_argument("--max-requests", type=int, required=True)
    experiment_parser.add_argument("--output-root", type=Path, default=Path("results/experiments"))
    experiment_parser.set_defaults(func=cmd_experiment)

    return parser


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite, root=args.root)
    if args.json:
        payload = {
            "suite": suite.id,
            "version": suite.version,
            "cases": [
                {
                    "id": c.id,
                    "ecosystem": c.ecosystem,
                    "category": c.category,
                    "difficulty": c.difficulty,
                    "is_clean": c.is_clean,
                    "label_status": c.label_status,
                    "label_source": c.label_source,
                    "title": c.title,
                }
                for c in suite.cases
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    frozen = sum(1 for c in suite.cases if c.labels_frozen)
    print(f"{suite.id} (version {suite.version}) — {len(suite)} cases")
    print(f"{len(suite.defect_cases)} with a labelled defect, {len(suite.clean_cases)} clean controls")
    print(f"{frozen} of {len(suite)} cases have frozen labels")
    print()
    width = max(len(c.id) for c in suite.cases)
    print(
        f"{'ID'.ljust(width)}  {'ECOSYSTEM'.ljust(9)}  {'CATEGORY'.ljust(22)}  "
        f"{'DIFF'.ljust(6)}  {'LABELS'.ljust(14)}  TITLE"
    )
    for case in suite.cases:
        print(
            f"{case.id.ljust(width)}  {case.ecosystem.ljust(9)}  {case.category.ljust(22)}  "
            f"{case.difficulty.ljust(6)}  {case.label_status.ljust(14)}  {case.title}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite, root=args.root)
    try:
        case = suite.get(args.case_id)
    except KeyError:
        print(f"error: case {args.case_id!r} is not in suite {suite.id!r}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(case.to_dict(), indent=2))
        return 0

    print(f"# {case.id} — {case.title}")
    print()
    print(f"ecosystem : {case.ecosystem}")
    print(f"category  : {case.category}")
    print(f"difficulty: {case.difficulty}")
    print(f"source    : {case.source_type}{' ' + case.source_url if case.source_url else ''}")
    print(f"clean     : {'yes' if case.is_clean else 'no'}")
    print(f"labels    : {case.label_status} (source: {case.label_source})")
    print(f"reviewed  : {', '.join(case.reviewed_by) if case.reviewed_by else 'not yet reviewed'}")
    if case.academic_review:
        print("academic  : separately reviewed by an academic collaborator")
    if case.tags:
        print(f"tags      : {', '.join(case.tags)}")
    print()
    print(case.description)
    if case.context:
        print()
        print("## Context")
        print(case.context)
    print()
    print("## Expected findings")
    if not case.expected_findings:
        print("(none — this is a clean control; any finding is a false positive)")
    for finding in case.expected_findings:
        location = f" [{finding.file}]" if finding.file else ""
        print(f"- {finding.category} ({finding.severity}){location}: {finding.description}")
    print()
    print("## Diff")
    print(case.diff)
    if case.notes:
        print("## Notes")
        print(case.notes)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite, root=args.root)
    print(f"{suite.id}: {len(suite)} cases validated against the v0.1 case schema")
    for case in suite.cases:
        print(f"  ok  {case.id.ljust(24)} labels: {case.label_status}")
    pending = [c.id for c in suite.cases if not c.labels_frozen]
    if pending:
        print()
        print(
            f"{len(pending)} of {len(suite)} cases are not frozen. Scoring a model against "
            "them produces provisional results; see docs/ANNOTATION.md."
        )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite, root=args.root)
    prompt = load_prompt(args.prompt, root=args.root)
    pricing = load_pricing(args.pricing)

    provider_kwargs = {
        "name": args.provider,
        "model": args.model,
        "mode": args.mock_mode,
        "temperature": args.temperature,
        "max_output_tokens": args.max_output_tokens,
        "timeout": args.timeout,
    }
    if args.provider == "openai":
        provider_kwargs["api_type"] = args.api_type or "responses"
        provider_kwargs["output_constraint"] = args.output_constraint
        provider_kwargs["reasoning_effort"] = args.reasoning_effort
    elif args.provider == "anthropic":
        if args.output_constraint == "json_object":
            raise ProviderError("Anthropic supports json_schema or prompt_only, not json_object")
        provider_kwargs["output_constraint"] = args.output_constraint
        provider_kwargs["thinking_mode"] = args.thinking_mode
        provider_kwargs["reasoning_effort"] = args.reasoning_effort
    elif args.provider == "gemini":
        provider_kwargs["output_constraint"] = args.output_constraint
        provider_kwargs["reasoning_effort"] = args.reasoning_effort
    elif args.provider == "xai":
        provider_kwargs["output_constraint"] = args.output_constraint
        provider_kwargs["reasoning_effort"] = args.reasoning_effort
    elif args.provider == "deepseek":
        if args.output_constraint == "json_schema":
            raise ProviderError("DeepSeek supports json_object or prompt_only, not json_schema")
        provider_kwargs["output_constraint"] = args.output_constraint
        provider_kwargs["reasoning_effort"] = args.reasoning_effort
    provider = get_provider(**provider_kwargs)

    pending = [c.id for c in suite.cases if not c.labels_frozen]
    if pending and not args.quiet:
        print(
            f"warning: {len(pending)} of {len(suite)} cases in {suite.id} have labels that a "
            "human has not yet frozen; any scores from this run are provisional",
            file=sys.stderr,
        )

    def progress(index: int, total: int, case: Any) -> None:
        if not args.quiet:
            print(f"[{index}/{total}] {case.id}", file=sys.stderr)

    document = run_suite(
        suite,
        provider,
        prompt,
        case_ids=args.cases,
        limit=args.limit,
        pricing=pricing,
        store_raw=not args.no_raw,
        progress=progress,
    )

    out_path: Optional[Path] = args.out
    if out_path is None:
        out_path = Path("results") / f"{suite.id}-{provider.name}-{document['run']['run_id']}.json"
    write_results(document, out_path)
    print(f"wrote {out_path}")

    if args.evaluate:
        evaluation = evaluate_document(
            document, suite, match_mode=args.match_mode, root=args.root
        )
        print()
        print(_summary_lines(evaluation))
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    document = read_results(args.results)
    suite = load_suite(args.suite, root=args.root) if args.suite else None
    evaluation = evaluate_document(document, suite, match_mode=args.match_mode, root=args.root)

    if args.out:
        write_evaluation(evaluation, args.out)
        print(f"wrote {args.out}")
    if args.json or not args.out:
        if args.json:
            print(json.dumps(evaluation, indent=2))
        else:
            print(_summary_lines(evaluation))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    document = json.loads(Path(args.results).read_text(encoding="utf-8"))
    if is_evaluation_document(document):
        evaluation = document
    else:
        if document.get("results_format_version") != RESULTS_FORMAT_VERSION:
            raise EvaluationError(
                f"{args.results}: unsupported results_format_version "
                f"{document.get('results_format_version')!r}"
            )
        suite = load_suite(args.suite, root=args.root) if args.suite else None
        evaluation = evaluate_document(document, suite, match_mode=args.match_mode, root=args.root)

    markdown = render_markdown(evaluation)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(markdown)
    return 0


def cmd_experiment(args: argparse.Namespace) -> int:
    experiment = load_experiment(args.config)
    suite, cases, missing = preflight(
        experiment, root=args.root, max_requests=args.max_requests, require_keys=not args.dry_run
    )
    if args.dry_run:
        print(dry_run_summary(experiment, suite, cases, missing, args.output_root, args.max_requests))
        return 0
    directory = run_experiment(experiment, root=args.root, output_root=args.output_root,
                               max_requests=args.max_requests)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    print(f"wrote {directory}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "completed" else 1


# --------------------------------------------------------------------------


def _summary_lines(evaluation: Dict[str, Any]) -> str:
    metrics = evaluation["metrics"]
    counts = metrics["counts"]
    findings = metrics["findings"]
    quality = metrics["quality"]
    false_alarms = metrics["false_alarms"]

    def show(value: Any) -> str:
        return "n/a" if value is None else (f"{value:.3f}" if isinstance(value, float) else str(value))

    lines: List[str] = [
        f"cases              : {counts['cases']} "
        f"({counts['defect_cases']} defect, {counts['clean_cases']} clean)",
        f"valid responses    : {counts['valid_responses']} "
        f"(malformed {counts['invalid_responses']}, provider errors {counts['provider_errors']})",
        f"TP / FP / FN       : {findings['true_positives']} / "
        f"{findings['false_positives']} / {findings['false_negatives']}",
        f"precision / recall : {show(quality['precision'])} / {show(quality['recall'])}",
        f"F1                 : {show(quality['f1'])}",
        f"clean false alarms : {show(false_alarms['clean_case_false_alarm_rate'])} "
        f"({false_alarms['clean_cases_with_findings']}/{counts['clean_cases']} clean cases)",
        f"match mode         : {evaluation['match_mode']}",
    ]
    ground_truth = metrics.get("ground_truth", {})
    if ground_truth:
        lines.append(
            f"frozen labels      : {ground_truth['frozen']}/{ground_truth['cases']} cases"
        )
        if not ground_truth.get("all_labels_frozen", True):
            lines.append("")
            lines.append(f"warning: {ground_truth['note']}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ConfigError, ProviderError, EvaluationError, ValidationError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
