"""Metric computation.

Every rate returned here is either a number or ``None``. ``None`` means "not
computable from this run" (empty denominator, or data the provider did not
report) and is never silently rendered as zero.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .matching import CaseMatch
from .schemas import DEFECT_CATEGORIES, PredictedFinding

#: Placeholder kept so that result files already carry the calibration slot the
#: roadmap fills in. See ``docs/METHODOLOGY.md``.
CALIBRATION_NOTE = (
    "Confidence values are recorded but not turned into a calibration score in "
    "v0.1: a single self-reported confidence does not have well-defined event "
    "semantics for Brier/ECE. Not yet measured."
)


def _ratio(numerator: float, denominator: float) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def precision(true_positives: int, false_positives: int) -> Optional[float]:
    return _ratio(true_positives, true_positives + false_positives)


def recall(true_positives: int, false_negatives: int) -> Optional[float]:
    return _ratio(true_positives, true_positives + false_negatives)


def f1_score(precision_value: Optional[float], recall_value: Optional[float]) -> Optional[float]:
    if precision_value is None or recall_value is None:
        return None
    if precision_value + recall_value == 0:
        return 0.0
    return round(2 * precision_value * recall_value / (precision_value + recall_value), 4)


def _summary(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "min": None, "max": None, "p95": None}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p95": round(ordered[p95_index], 4),
    }


def _mean_or_none(values: Sequence[float]) -> Optional[float]:
    return round(statistics.fmean(values), 4) if values else None


def compute_metrics(
    matches: Sequence[CaseMatch],
    *,
    predictions: Dict[str, List[PredictedFinding]],
    case_meta: Dict[str, Dict[str, Any]],
    latencies_ms: Sequence[float] = (),
    usages: Sequence[Optional[Dict[str, Any]]] = (),
    costs: Sequence[Optional[float]] = (),
    overall_confidences: Sequence[Optional[float]] = (),
    provider_errors: int = 0,
) -> Dict[str, Any]:
    """Aggregate per-case matching outcomes into the run's metrics.

    ``predictions`` maps case id to the predicted findings of that case;
    ``case_meta`` maps case id to ``{"category": ..., "ecosystem": ...,
    "is_clean": ...}``.
    """
    true_positives = sum(m.true_positives for m in matches)
    false_positives = sum(m.false_positives for m in matches)
    false_negatives = sum(m.false_negatives for m in matches)

    valid = [m for m in matches if m.valid_response]
    invalid = [m for m in matches if not m.valid_response]
    clean = [m for m in matches if m.is_clean]
    defect = [m for m in matches if not m.is_clean]
    clean_valid = [m for m in clean if m.valid_response]
    defect_valid = [m for m in defect if m.valid_response]

    precision_value = precision(true_positives, false_positives)
    recall_value = recall(true_positives, false_negatives)

    clean_with_findings = [m for m in clean_valid if m.n_predicted > 0]

    metrics: Dict[str, Any] = {
        "counts": {
            "cases": len(matches),
            "defect_cases": len(defect),
            "clean_cases": len(clean),
            "valid_responses": len(valid),
            "invalid_responses": len(invalid),
            "provider_errors": provider_errors,
        },
        "findings": {
            "expected": sum(m.n_expected for m in matches),
            "predicted": sum(m.n_predicted for m in matches),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        },
        "quality": {
            "precision": precision_value,
            "recall": recall_value,
            "f1": f1_score(precision_value, recall_value),
        },
        "false_alarms": {
            # Primary false-positive figure for v0.1: the share of clean
            # control cases on which the reviewer reported anything at all.
            "clean_case_false_alarm_rate": _ratio(len(clean_with_findings), len(clean_valid)),
            "clean_cases_with_findings": len(clean_with_findings),
            "clean_case_findings_total": sum(m.n_predicted for m in clean_valid),
            "mean_findings_per_clean_case": _mean_or_none(
                [float(m.n_predicted) for m in clean_valid]
            ),
            "mean_false_positives_per_defect_case": _mean_or_none(
                [float(m.false_positives) for m in defect_valid]
            ),
        },
        "detection": {
            # Case-level view: did the reviewer find *anything* real, and did
            # it find everything, on cases that do contain a defect?
            "case_detection_rate": _ratio(
                sum(1 for m in defect_valid if m.detected), len(defect_valid)
            ),
            "case_full_detection_rate": _ratio(
                sum(1 for m in defect_valid if m.false_negatives == 0), len(defect_valid)
            ),
        },
        "by_category": _by_category(matches, predictions, case_meta),
        "by_ecosystem": _by_ecosystem(matches, case_meta),
        "latency_ms": _summary([float(v) for v in latencies_ms]),
        "tokens": _token_summary(usages),
        "cost_usd": _cost_summary(costs),
        "confidence": _confidence_summary(matches, predictions, overall_confidences),
        "calibration": {"brier_score": None, "ece": None, "note": CALIBRATION_NOTE},
    }
    return metrics


def _by_category(
    matches: Sequence[CaseMatch],
    predictions: Dict[str, List[PredictedFinding]],
    case_meta: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {
        category: {"expected": 0, "true_positives": 0, "false_negatives": 0, "false_positives": 0}
        for category in DEFECT_CATEGORIES
    }

    for match in matches:
        meta = case_meta.get(match.case_id, {})
        expected_categories: List[str] = list(meta.get("expected_categories", []))
        for index, category in enumerate(expected_categories):
            entry = stats.setdefault(
                category,
                {"expected": 0, "true_positives": 0, "false_negatives": 0, "false_positives": 0},
            )
            entry["expected"] += 1
            if index in match.false_negative_indices:
                entry["false_negatives"] += 1
            elif any(p.expected_index == index for p in match.matched):
                entry["true_positives"] += 1

        predicted = predictions.get(match.case_id, [])
        for index in match.false_positive_indices:
            if index >= len(predicted):
                continue
            category = predicted[index].normalized_category
            entry = stats.setdefault(
                category,
                {"expected": 0, "true_positives": 0, "false_negatives": 0, "false_positives": 0},
            )
            entry["false_positives"] += 1

    for entry in stats.values():
        entry["recall"] = recall(entry["true_positives"], entry["false_negatives"])
        entry["precision"] = precision(entry["true_positives"], entry["false_positives"])
    return stats


def _by_ecosystem(
    matches: Sequence[CaseMatch], case_meta: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for match in matches:
        ecosystem = case_meta.get(match.case_id, {}).get("ecosystem", "unknown")
        entry = stats.setdefault(
            ecosystem,
            {
                "cases": 0,
                "clean_cases": 0,
                "true_positives": 0,
                "false_positives": 0,
                "false_negatives": 0,
                "invalid_responses": 0,
            },
        )
        entry["cases"] += 1
        if match.is_clean:
            entry["clean_cases"] += 1
        if not match.valid_response:
            entry["invalid_responses"] += 1
        entry["true_positives"] += match.true_positives
        entry["false_positives"] += match.false_positives
        entry["false_negatives"] += match.false_negatives

    for entry in stats.values():
        entry["precision"] = precision(entry["true_positives"], entry["false_positives"])
        entry["recall"] = recall(entry["true_positives"], entry["false_negatives"])
    return stats


def _token_summary(usages: Iterable[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    reported = [u for u in usages if isinstance(u, dict)]
    totals: Dict[str, Optional[int]] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        values = [u.get(key) for u in reported if isinstance(u.get(key), int)]
        totals[key] = sum(values) if values else None

    estimated_flags = {bool(u.get("estimated")) for u in reported}
    if not estimated_flags:
        estimated: Any = None
    elif len(estimated_flags) == 1:
        estimated = estimated_flags.pop()
    else:
        estimated = "mixed"

    return {
        "responses_with_usage": len(reported),
        "estimated": estimated,
        **totals,
    }


def _cost_summary(costs: Iterable[Optional[float]]) -> Dict[str, Any]:
    reported = [c for c in costs if isinstance(c, (int, float))]
    return {
        "responses_with_cost": len(reported),
        "total": round(sum(reported), 6) if reported else None,
        "note": (
            "Cost is only computed when a pricing table is supplied "
            "(--pricing / $WEBFIXBENCH_PRICING); the benchmark ships no vendor prices."
        ),
    }


def _confidence_summary(
    matches: Sequence[CaseMatch],
    predictions: Dict[str, List[PredictedFinding]],
    overall_confidences: Sequence[Optional[float]],
) -> Dict[str, Any]:
    all_values: List[float] = []
    tp_values: List[float] = []
    fp_values: List[float] = []
    missing = 0

    for match in matches:
        predicted = predictions.get(match.case_id, [])
        matched_indices = {p.predicted_index for p in match.matched}
        for index, finding in enumerate(predicted):
            if finding.confidence is None:
                missing += 1
                continue
            value = float(finding.confidence)
            all_values.append(value)
            if index in matched_indices:
                tp_values.append(value)
            else:
                fp_values.append(value)

    overall = [float(c) for c in overall_confidences if isinstance(c, (int, float))]
    summary: Dict[str, Any] = {
        "findings": _summary(all_values),
        "findings_without_confidence": missing,
        "mean_true_positive_confidence": _mean_or_none(tp_values),
        "mean_false_positive_confidence": _mean_or_none(fp_values),
        "overall_confidence": _summary(overall),
    }
    tp_mean = summary["mean_true_positive_confidence"]
    fp_mean = summary["mean_false_positive_confidence"]
    summary["confidence_gap_tp_minus_fp"] = (
        round(tp_mean - fp_mean, 4) if tp_mean is not None and fp_mean is not None else None
    )
    return summary


def counts_from_matches(matches: Sequence[CaseMatch]) -> Tuple[int, int, int]:
    """Convenience accessor used by tests and reports."""
    return (
        sum(m.true_positives for m in matches),
        sum(m.false_positives for m in matches),
        sum(m.false_negatives for m in matches),
    )
