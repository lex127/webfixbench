"""Deterministic matching of predicted findings to ground truth.

v0.1 deliberately uses transparent, deterministic rules rather than an
LLM judge: every true positive can be re-derived by hand from a result file.
The cost of that choice is documented in ``docs/METHODOLOGY.md`` — a prediction
with the right category but an unrelated explanation still counts as a match.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .schemas import Case, ExpectedFinding, PredictedFinding, normalize_category

#: ``category``       — a prediction matches when its normalized category
#:                      equals the expected category.
#: ``category_file``  — as above, and the predicted file must additionally
#:                      identify the same file as the expected finding.
MATCH_MODES = ("category", "category_file")
DEFAULT_MATCH_MODE = "category"


def _same_file(expected: Optional[str], predicted: Optional[str]) -> bool:
    """Compare two file references leniently but deterministically.

    Models report paths with varying prefixes (``a/src/X.php``, ``src/X.php``,
    ``X.php``). Two references are considered equal when one path is a
    trailing-segment suffix of the other.
    """
    if not expected or not predicted:
        return False
    exp = expected.strip().lstrip("./").split("/")
    pred = predicted.strip().lstrip("./").split("/")
    # Strip the a/ b/ prefixes used by unified diffs.
    if len(pred) > 1 and pred[0] in ("a", "b"):
        pred = pred[1:]
    if len(exp) > 1 and exp[0] in ("a", "b"):
        exp = exp[1:]
    if not exp or not pred:
        return False
    shortest = min(len(exp), len(pred))
    return exp[-shortest:] == pred[-shortest:]


@dataclass(frozen=True)
class MatchedPair:
    expected_index: int
    predicted_index: int
    category: str
    file_matched: bool
    confidence: Optional[float]


@dataclass(frozen=True)
class CaseMatch:
    """The outcome of matching one model response against one case."""

    case_id: str
    is_clean: bool
    valid_response: bool
    matched: List[MatchedPair] = field(default_factory=list)
    false_positive_indices: List[int] = field(default_factory=list)
    false_negative_indices: List[int] = field(default_factory=list)
    n_expected: int = 0
    n_predicted: int = 0

    @property
    def true_positives(self) -> int:
        return len(self.matched)

    @property
    def false_positives(self) -> int:
        return len(self.false_positive_indices)

    @property
    def false_negatives(self) -> int:
        return len(self.false_negative_indices)

    @property
    def detected(self) -> bool:
        """True when at least one expected finding was matched."""
        return bool(self.matched)


def match_findings(
    expected: Sequence[ExpectedFinding],
    predicted: Sequence[PredictedFinding],
    *,
    mode: str = DEFAULT_MATCH_MODE,
) -> Tuple[List[MatchedPair], List[int], List[int]]:
    """Greedily assign predictions to expected findings (one-to-one).

    Returns ``(matched_pairs, unmatched_predicted_indices,
    unmatched_expected_indices)``.
    """
    if mode not in MATCH_MODES:
        raise ValueError(f"unknown match mode {mode!r}; expected one of {list(MATCH_MODES)}")

    used_predictions: set = set()
    matched: List[MatchedPair] = []
    unmatched_expected: List[int] = []

    for e_index, exp in enumerate(expected):
        candidates: List[int] = []
        for p_index, pred in enumerate(predicted):
            if p_index in used_predictions:
                continue
            if pred.normalized_category != exp.category:
                continue
            if mode == "category_file" and not _same_file(exp.file, pred.file):
                continue
            candidates.append(p_index)

        if not candidates:
            unmatched_expected.append(e_index)
            continue

        # Among equally valid candidates prefer the one pointing at the right
        # file, then the earliest reported one, so assignment is deterministic.
        chosen = min(
            candidates,
            key=lambda i: (0 if _same_file(exp.file, predicted[i].file) else 1, i),
        )
        used_predictions.add(chosen)
        matched.append(
            MatchedPair(
                expected_index=e_index,
                predicted_index=chosen,
                category=exp.category,
                file_matched=_same_file(exp.file, predicted[chosen].file),
                confidence=predicted[chosen].confidence,
            )
        )

    unmatched_predicted = [i for i in range(len(predicted)) if i not in used_predictions]
    return matched, unmatched_predicted, unmatched_expected


def match_case(
    case: Case,
    predicted: Optional[Sequence[PredictedFinding]],
    *,
    valid_response: bool = True,
    mode: str = DEFAULT_MATCH_MODE,
) -> CaseMatch:
    """Match one response against one case.

    A malformed response (``valid_response=False``) yields no true positives
    and no false positives; every expected finding is counted as a false
    negative and the response is reported separately as invalid. Malformed
    output is never silently scored as a correct "no findings" answer.
    """
    if not valid_response:
        return CaseMatch(
            case_id=case.id,
            is_clean=case.is_clean,
            valid_response=False,
            matched=[],
            false_positive_indices=[],
            false_negative_indices=list(range(len(case.expected_findings))),
            n_expected=len(case.expected_findings),
            n_predicted=0,
        )

    predicted = list(predicted or [])
    matched, fp_indices, fn_indices = match_findings(
        case.expected_findings, predicted, mode=mode
    )
    return CaseMatch(
        case_id=case.id,
        is_clean=case.is_clean,
        valid_response=True,
        matched=matched,
        false_positive_indices=fp_indices,
        false_negative_indices=fn_indices,
        n_expected=len(case.expected_findings),
        n_predicted=len(predicted),
    )


def normalized_categories(predicted: Sequence[PredictedFinding]) -> List[str]:
    return [normalize_category(p.category) for p in predicted]
