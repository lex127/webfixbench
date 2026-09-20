"""Rendering an evaluation document as Markdown."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

DISCLAIMER = (
    "Numbers describe this single run of a small synthetic suite. They are not a "
    "general statement about the reviewer's security capability."
)


def _fmt(value: Any, *, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_markdown(evaluation: Dict[str, Any], *, include_cases: bool = True) -> str:
    metrics = evaluation.get("metrics", {})
    run = evaluation.get("run", {})
    provider = run.get("provider", {})
    suite = run.get("suite", {})
    prompt = run.get("prompt", {})
    counts = metrics.get("counts", {})
    findings = metrics.get("findings", {})
    quality = metrics.get("quality", {})
    false_alarms = metrics.get("false_alarms", {})
    detection = metrics.get("detection", {})
    confidence = metrics.get("confidence", {})
    latency = metrics.get("latency_ms", {})
    tokens = metrics.get("tokens", {})
    cost = metrics.get("cost_usd", {})

    lines: List[str] = []
    lines.append("# WebFixBench run report")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Suite | `{suite.get('id')}` (version {suite.get('version')}) |")
    lines.append(f"| Provider | `{provider.get('provider')}` |")
    lines.append(f"| Model | `{provider.get('model')}` |")
    lines.append(f"| Temperature | {_fmt(provider.get('temperature'), digits=2)} |")
    lines.append(f"| Prompt | `{prompt.get('id')}` (sha256 `{str(prompt.get('sha256'))[:12]}…`) |")
    lines.append(f"| Match mode | `{evaluation.get('match_mode')}` |")
    lines.append(f"| Run id | `{run.get('run_id')}` |")
    lines.append(f"| Run at (UTC) | {run.get('created_at')} |")
    lines.append(f"| WebFixBench | {evaluation.get('webfixbench_version')} |")
    if provider.get("mock_mode"):
        lines.append(f"| Mock mode | `{provider.get('mock_mode')}` |")
    lines.append("")

    ground_truth = metrics.get("ground_truth", {})
    if ground_truth and not ground_truth.get("all_labels_frozen", True):
        lines.append(f"> **Provisional.** {ground_truth.get('note')}")
        lines.append("")

    if provider.get("provider") == "mock":
        lines.append(
            "> The `mock` provider is a deterministic rule-based stub, not a language "
            "model. This report exercises the pipeline; it says nothing about any "
            "model's review quality."
        )
        lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append(
        f"- Cases scored: **{counts.get('cases')}** "
        f"({counts.get('defect_cases')} with a defect, {counts.get('clean_cases')} clean controls)"
    )
    lines.append(
        f"- Valid structured responses: **{counts.get('valid_responses')}**, "
        f"malformed: **{counts.get('invalid_responses')}**, "
        f"provider errors: **{counts.get('provider_errors')}**"
    )
    if ground_truth:
        lines.append(
            f"- Cases with frozen labels: **{ground_truth.get('frozen')}** of "
            f"**{ground_truth.get('cases')}**"
        )
    lines.append("")

    lines.append("## Finding-level results")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Expected findings | {findings.get('expected')} |")
    lines.append(f"| Predicted findings | {findings.get('predicted')} |")
    lines.append(f"| True positives | {findings.get('true_positives')} |")
    lines.append(f"| False positives | {findings.get('false_positives')} |")
    lines.append(f"| False negatives | {findings.get('false_negatives')} |")
    lines.append(f"| Precision | {_fmt(quality.get('precision'))} |")
    lines.append(f"| Recall | {_fmt(quality.get('recall'))} |")
    lines.append(f"| F1 | {_fmt(quality.get('f1'))} |")
    lines.append("")

    lines.append("## False alarms and detection")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(
        "| Clean-control false-alarm rate | "
        f"{_pct(false_alarms.get('clean_case_false_alarm_rate'))} "
        f"({false_alarms.get('clean_cases_with_findings')} of "
        f"{counts.get('clean_cases')} clean cases) |"
    )
    lines.append(
        f"| Findings on clean controls | {false_alarms.get('clean_case_findings_total')} |"
    )
    lines.append(
        "| Mean false positives per defect case | "
        f"{_fmt(false_alarms.get('mean_false_positives_per_defect_case'))} |"
    )
    lines.append(
        f"| Defect cases with ≥1 correct finding | {_pct(detection.get('case_detection_rate'))} |"
    )
    lines.append(
        "| Defect cases with all findings found | "
        f"{_pct(detection.get('case_full_detection_rate'))} |"
    )
    lines.append("")

    by_ecosystem = metrics.get("by_ecosystem", {})
    if by_ecosystem:
        lines.append("## By ecosystem")
        lines.append("")
        lines.append("| Ecosystem | Cases | TP | FP | FN | Precision | Recall |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for name in sorted(by_ecosystem):
            entry = by_ecosystem[name]
            lines.append(
                f"| {name} | {entry.get('cases')} | {entry.get('true_positives')} | "
                f"{entry.get('false_positives')} | {entry.get('false_negatives')} | "
                f"{_fmt(entry.get('precision'))} | {_fmt(entry.get('recall'))} |"
            )
        lines.append("")

    by_category = metrics.get("by_category", {})
    if by_category:
        lines.append("## By category")
        lines.append("")
        lines.append("| Category | Expected | TP | FN | FP | Recall | Precision |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for name in sorted(by_category):
            entry = by_category[name]
            lines.append(
                f"| {name} | {entry.get('expected')} | {entry.get('true_positives')} | "
                f"{entry.get('false_negatives')} | {entry.get('false_positives')} | "
                f"{_fmt(entry.get('recall'))} | {_fmt(entry.get('precision'))} |"
            )
        lines.append("")

    lines.append("## Confidence")
    lines.append("")
    finding_conf = confidence.get("findings", {})
    overall_conf = confidence.get("overall_confidence", {})
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Findings with confidence | {finding_conf.get('n')} |")
    lines.append(f"| Mean finding confidence | {_fmt(finding_conf.get('mean'))} |")
    lines.append(
        f"| Mean confidence, true positives | {_fmt(confidence.get('mean_true_positive_confidence'))} |"
    )
    lines.append(
        f"| Mean confidence, false positives | {_fmt(confidence.get('mean_false_positive_confidence'))} |"
    )
    lines.append(
        f"| Confidence gap (TP − FP) | {_fmt(confidence.get('confidence_gap_tp_minus_fp'))} |"
    )
    lines.append(f"| Mean overall_confidence | {_fmt(overall_conf.get('mean'))} |")
    lines.append("")
    lines.append(f"Calibration: {metrics.get('calibration', {}).get('note', 'not yet measured')}")
    lines.append("")

    lines.append("## Cost and latency")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Mean latency (ms) | {_fmt(latency.get('mean'), digits=2)} |")
    lines.append(f"| Median latency (ms) | {_fmt(latency.get('median'), digits=2)} |")
    lines.append(f"| p95 latency (ms) | {_fmt(latency.get('p95'), digits=2)} |")
    lines.append(f"| Input tokens | {_fmt(tokens.get('input_tokens'))} |")
    lines.append(f"| Output tokens | {_fmt(tokens.get('output_tokens'))} |")
    lines.append(f"| Token counts estimated | {_fmt(tokens.get('estimated'))} |")
    lines.append(f"| Total cost (USD) | {_fmt(cost.get('total'), digits=4)} |")
    lines.append("")

    if include_cases and evaluation.get("cases"):
        lines.append("## Per-case results")
        lines.append("")
        lines.append("| Case | Ecosystem | Clean | Valid | Expected | Predicted | TP | FP | FN |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for case in evaluation["cases"]:
            lines.append(
                f"| `{case['case_id']}` | {case['ecosystem']} | "
                f"{'yes' if case['is_clean'] else 'no'} | "
                f"{'yes' if case['valid_response'] else 'no'} | "
                f"{case['expected']} | {case['predicted']} | {case['true_positives']} | "
                f"{case['false_positives']} | {case['false_negatives']} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    return "\n".join(lines)
