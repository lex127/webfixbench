"""Scoring a result file against the ground truth of a suite.

Evaluation is a separate step from running: result files hold raw model output,
so the same run can be re-scored under a different matching mode without
re-querying any model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .cases import Suite, load_suite
from .matching import DEFAULT_MATCH_MODE, MATCH_MODES, CaseMatch, match_case
from .metrics import compute_metrics
from .schemas import ModelResponse, PredictedFinding, model_response_from_dict

EVALUATION_FORMAT_VERSION = 1


class EvaluationError(RuntimeError):
    """Raised when a result file cannot be scored against a suite."""


def _predictions(parsed: Optional[Dict[str, Any]]) -> List[PredictedFinding]:
    if not parsed:
        return []
    response: ModelResponse = model_response_from_dict(parsed)
    return list(response.findings)


def evaluate_document(
    document: Dict[str, Any],
    suite: Optional[Suite] = None,
    *,
    match_mode: str = DEFAULT_MATCH_MODE,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Score a result document, returning an evaluation document."""
    if match_mode not in MATCH_MODES:
        raise EvaluationError(
            f"unknown match mode {match_mode!r}; expected one of {list(MATCH_MODES)}"
        )

    if suite is None:
        suite_id = (document.get("run", {}).get("suite") or {}).get("id")
        if not suite_id:
            raise EvaluationError(
                "result file does not record a suite id; pass the suite explicitly"
            )
        suite = load_suite(suite_id, root=root)

    responses = document.get("responses")
    if not isinstance(responses, list) or not responses:
        raise EvaluationError("result file contains no responses")

    matches: List[CaseMatch] = []
    predictions: Dict[str, List[PredictedFinding]] = {}
    case_meta: Dict[str, Dict[str, Any]] = {}
    per_case: List[Dict[str, Any]] = []
    latencies: List[float] = []
    usages: List[Optional[Dict[str, Any]]] = []
    costs: List[Optional[float]] = []
    overall_confidences: List[Optional[float]] = []
    provider_errors = 0

    for response in responses:
        case_id = response.get("case_id")
        try:
            case = suite.get(case_id)
        except KeyError:
            raise EvaluationError(
                f"result file references case {case_id!r}, which is not in suite {suite.id!r}"
            )

        valid = bool(response.get("valid"))
        predicted = _predictions(response.get("parsed")) if valid else []
        predictions[case.id] = predicted
        case_meta[case.id] = {
            "category": case.category,
            "ecosystem": case.ecosystem,
            "is_clean": case.is_clean,
            "expected_categories": case.expected_categories,
            "label_status": case.label_status,
        }

        match = match_case(case, predicted, valid_response=valid, mode=match_mode)
        matches.append(match)

        if response.get("error"):
            provider_errors += 1
        latency = response.get("latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))
        usages.append(response.get("usage"))
        costs.append(response.get("cost_usd"))
        overall_confidences.append((response.get("parsed") or {}).get("overall_confidence"))

        per_case.append(
            {
                "case_id": case.id,
                "ecosystem": case.ecosystem,
                "category": case.category,
                "difficulty": case.difficulty,
                "is_clean": case.is_clean,
                "label_status": case.label_status,
                "label_source": case.label_source,
                "valid_response": valid,
                "error": response.get("error"),
                "validation_errors": response.get("validation_errors") or [],
                "expected": match.n_expected,
                "predicted": match.n_predicted,
                "true_positives": match.true_positives,
                "false_positives": match.false_positives,
                "false_negatives": match.false_negatives,
                "detected": match.detected,
                "predicted_categories": [p.normalized_category for p in predicted],
                "latency_ms": latency,
                "cost_usd": response.get("cost_usd"),
                "overall_confidence": (response.get("parsed") or {}).get("overall_confidence"),
            }
        )

    metrics = compute_metrics(
        matches,
        predictions=predictions,
        case_meta=case_meta,
        latencies_ms=latencies,
        usages=usages,
        costs=costs,
        overall_confidences=overall_confidences,
        provider_errors=provider_errors,
    )
    metrics["ground_truth"] = _ground_truth_summary(case_meta)

    return {
        "webfixbench_version": __version__,
        "evaluation_format_version": EVALUATION_FORMAT_VERSION,
        "match_mode": match_mode,
        "run": document.get("run", {}),
        "source_results_version": document.get("results_format_version"),
        "metrics": metrics,
        "cases": per_case,
    }


def _ground_truth_summary(case_meta: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Report how much of the scored ground truth is actually final.

    Labels that a human has not yet reviewed and frozen make an evaluation
    provisional, and that fact travels with the numbers rather than living only
    in the case files.
    """
    statuses = [meta.get("label_status", "draft") for meta in case_meta.values()]
    counts = {status: statuses.count(status) for status in sorted(set(statuses))}
    frozen = counts.get("frozen", 0)
    all_frozen = bool(statuses) and frozen == len(statuses)
    return {
        "cases": len(statuses),
        "frozen": frozen,
        "by_status": counts,
        "all_labels_frozen": all_frozen,
        "note": (
            "All labels are frozen; this evaluation scores final ground truth."
            if all_frozen
            else (
                f"{len(statuses) - frozen} of {len(statuses)} cases have labels that a human "
                "has not yet reviewed and frozen. These results are provisional and must not "
                "be published as a model evaluation. See docs/ANNOTATION.md."
            )
        ),
    }


def write_evaluation(document: Dict[str, Any], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def is_evaluation_document(document: Dict[str, Any]) -> bool:
    return "evaluation_format_version" in document
