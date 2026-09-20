"""Metric computation, including the "not computable" cases."""

import unittest

from webfixbench.matching import match_case
from webfixbench.metrics import compute_metrics, f1_score, precision, recall
from webfixbench.schemas import Case, ExpectedFinding, PredictedFinding


def make_case(case_id: str, *, is_clean: bool, categories=()) -> Case:
    findings = [
        ExpectedFinding(category=c, severity="high", description="gt", file="app/X.php")
        for c in categories
    ]
    return Case(
        id=case_id,
        title="t",
        language="php",
        ecosystem="laravel",
        category="clean_control" if is_clean else categories[0],
        difficulty="easy",
        source_type="synthetic",
        source_url=None,
        description="d",
        diff="diff",
        expected_findings=findings,
        is_clean=is_clean,
    )


def predicted(category: str, confidence=None) -> PredictedFinding:
    return PredictedFinding(
        category=category, severity="high", description="p", file="app/X.php", confidence=confidence
    )


def build(cases_and_predictions):
    matches = []
    predictions = {}
    case_meta = {}
    for case, preds, valid in cases_and_predictions:
        matches.append(match_case(case, preds, valid_response=valid))
        predictions[case.id] = list(preds or [])
        case_meta[case.id] = {
            "category": case.category,
            "ecosystem": case.ecosystem,
            "is_clean": case.is_clean,
            "expected_categories": case.expected_categories,
        }
    return matches, predictions, case_meta


class ScalarMetricTests(unittest.TestCase):
    def test_precision_recall_f1(self) -> None:
        self.assertEqual(precision(3, 1), 0.75)
        self.assertEqual(recall(3, 1), 0.75)
        self.assertEqual(f1_score(0.75, 0.75), 0.75)
        self.assertEqual(f1_score(0.0, 0.0), 0.0)

    def test_empty_denominators_return_none_not_zero(self) -> None:
        self.assertIsNone(precision(0, 0))
        self.assertIsNone(recall(0, 0))
        self.assertIsNone(f1_score(None, 1.0))


class AggregateMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        hit = make_case("hit", is_clean=False, categories=("authorization",))
        miss = make_case("miss", is_clean=False, categories=("injection",))
        clean_ok = make_case("clean-ok", is_clean=True)
        clean_noisy = make_case("clean-noisy", is_clean=True)
        self.matches, self.predictions, self.case_meta = build(
            [
                (hit, [predicted("authorization", 0.9)], True),
                (miss, [predicted("xss", 0.4)], True),
                (clean_ok, [], True),
                (clean_noisy, [predicted("xss", 0.2)], True),
            ]
        )
        self.metrics = compute_metrics(
            self.matches,
            predictions=self.predictions,
            case_meta=self.case_meta,
            latencies_ms=[10.0, 20.0, 30.0, 40.0],
            usages=[{"input_tokens": 100, "output_tokens": 10, "estimated": True}] * 4,
            costs=[None, None, None, None],
            overall_confidences=[0.9, 0.4, 0.8, 0.2],
        )

    def test_finding_counts(self) -> None:
        findings = self.metrics["findings"]
        self.assertEqual(findings["true_positives"], 1)
        self.assertEqual(findings["false_positives"], 2)
        self.assertEqual(findings["false_negatives"], 1)

    def test_quality_metrics(self) -> None:
        quality = self.metrics["quality"]
        self.assertAlmostEqual(quality["precision"], 1 / 3, places=3)
        self.assertEqual(quality["recall"], 0.5)

    def test_clean_control_false_alarm_rate(self) -> None:
        false_alarms = self.metrics["false_alarms"]
        self.assertEqual(false_alarms["clean_case_false_alarm_rate"], 0.5)
        self.assertEqual(false_alarms["clean_cases_with_findings"], 1)
        self.assertEqual(false_alarms["clean_case_findings_total"], 1)

    def test_case_level_detection(self) -> None:
        self.assertEqual(self.metrics["detection"]["case_detection_rate"], 0.5)

    def test_per_category_breakdown(self) -> None:
        by_category = self.metrics["by_category"]
        self.assertEqual(by_category["authorization"]["true_positives"], 1)
        self.assertEqual(by_category["injection"]["false_negatives"], 1)
        self.assertEqual(by_category["xss"]["false_positives"], 2)

    def test_confidence_summary_separates_true_and_false_positives(self) -> None:
        confidence = self.metrics["confidence"]
        self.assertEqual(confidence["mean_true_positive_confidence"], 0.9)
        self.assertAlmostEqual(confidence["mean_false_positive_confidence"], 0.3, places=6)
        self.assertAlmostEqual(confidence["confidence_gap_tp_minus_fp"], 0.6, places=6)

    def test_latency_summary(self) -> None:
        self.assertEqual(self.metrics["latency_ms"]["mean"], 25.0)
        self.assertEqual(self.metrics["latency_ms"]["n"], 4)

    def test_token_usage_is_flagged_as_estimated(self) -> None:
        tokens = self.metrics["tokens"]
        self.assertEqual(tokens["input_tokens"], 400)
        self.assertTrue(tokens["estimated"])

    def test_cost_is_null_without_a_pricing_table(self) -> None:
        self.assertIsNone(self.metrics["cost_usd"]["total"])

    def test_calibration_is_reported_as_not_yet_measured(self) -> None:
        calibration = self.metrics["calibration"]
        self.assertIsNone(calibration["brier_score"])
        self.assertIn("Not yet measured", calibration["note"])


class InvalidResponseMetricTests(unittest.TestCase):
    def test_malformed_responses_are_counted_separately(self) -> None:
        case = make_case("broken", is_clean=False, categories=("xss",))
        matches, predictions, case_meta = build([(case, [], False)])
        metrics = compute_metrics(matches, predictions=predictions, case_meta=case_meta)
        self.assertEqual(metrics["counts"]["invalid_responses"], 1)
        self.assertEqual(metrics["counts"]["valid_responses"], 0)
        self.assertEqual(metrics["findings"]["true_positives"], 0)
        self.assertEqual(metrics["findings"]["false_negatives"], 1)
        # No valid clean responses: the rate is unknown, not 0.0.
        self.assertIsNone(metrics["false_alarms"]["clean_case_false_alarm_rate"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
