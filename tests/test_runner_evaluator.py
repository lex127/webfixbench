"""End-to-end suite execution and scoring, offline."""

import json
import tempfile
import unittest
from pathlib import Path

from webfixbench.cases import load_suite
from webfixbench.config import load_prompt
from webfixbench.evaluator import EvaluationError, evaluate_document
from webfixbench.providers.mock import MockProvider
from webfixbench.report import render_markdown
from webfixbench.runner import RESULTS_FORMAT_VERSION, read_results, run_suite, write_results

ROOT = Path(__file__).resolve().parents[1]


class SuiteRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = load_suite("php-web-v0.1", root=ROOT)
        cls.prompt = load_prompt("review_v2", root=ROOT)
        cls.document = run_suite(cls.suite, MockProvider(), cls.prompt)
        cls.evaluation = evaluate_document(cls.document, cls.suite, root=ROOT)

    def test_every_case_is_run(self) -> None:
        self.assertEqual(len(self.document["responses"]), len(self.suite))

    def test_run_metadata_pins_prompt_and_provider(self) -> None:
        run = self.document["run"]
        self.assertEqual(run["prompt"]["id"], "review_v2")
        self.assertEqual(len(run["prompt"]["sha256"]), 64)
        self.assertEqual(run["provider"]["provider"], "mock")
        self.assertEqual(run["suite"]["id"], "php-web-v0.1")
        self.assertEqual(self.document["results_format_version"], RESULTS_FORMAT_VERSION)

    def test_all_mock_responses_parse(self) -> None:
        self.assertTrue(all(r["valid"] for r in self.document["responses"]))
        self.assertEqual(self.evaluation["metrics"]["counts"]["invalid_responses"], 0)

    def test_run_is_reproducible(self) -> None:
        again = run_suite(self.suite, MockProvider(), self.prompt)
        self.assertEqual(
            [r["parsed"] for r in self.document["responses"]],
            [r["parsed"] for r in again["responses"]],
        )

    def test_scores_are_neither_perfect_nor_empty(self) -> None:
        # The stub is deliberately fallible; a perfect score would mean the
        # metrics are not being exercised.
        findings = self.evaluation["metrics"]["findings"]
        self.assertGreater(findings["true_positives"], 0)
        self.assertGreater(findings["false_positives"], 0)
        self.assertGreater(findings["false_negatives"], 0)

    def test_cost_is_null_without_a_pricing_table(self) -> None:
        self.assertTrue(all(r["cost_usd"] is None for r in self.document["responses"]))
        self.assertIsNone(self.document["run"]["pricing"])

    def test_case_selection_and_limit(self) -> None:
        one = run_suite(
            self.suite, MockProvider(), self.prompt, case_ids=["laravel-xss-001"]
        )
        self.assertEqual([r["case_id"] for r in one["responses"]], ["laravel-xss-001"])
        limited = run_suite(self.suite, MockProvider(), self.prompt, limit=3)
        self.assertEqual(len(limited["responses"]), 3)

    def test_unknown_case_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            run_suite(self.suite, MockProvider(), self.prompt, case_ids=["nope"])

    def test_results_round_trip_through_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_results(self.document, Path(tmp) / "run.json")
            reloaded = read_results(path)
            self.assertEqual(reloaded["run"]["run_id"], self.document["run"]["run_id"])

    def test_unsupported_results_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text(json.dumps({"results_format_version": 99}), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_results(path)

    def test_no_api_key_material_is_written_to_results(self) -> None:
        serialized = json.dumps(self.document)
        self.assertNotIn("api_key", serialized.lower().replace("wfb_live_example", ""))


class CleanControlTests(unittest.TestCase):
    """Clean controls are the false-positive measurement, so they get their own test."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = load_suite("php-web-v0.1", root=ROOT)
        cls.prompt = load_prompt("review_v2", root=ROOT)

    def test_a_reviewer_that_reports_nothing_has_no_false_positives(self) -> None:
        document = run_suite(self.suite, MockProvider(mode="empty"), self.prompt)
        evaluation = evaluate_document(document, self.suite, root=ROOT)
        false_alarms = evaluation["metrics"]["false_alarms"]
        self.assertEqual(false_alarms["clean_case_false_alarm_rate"], 0.0)
        self.assertEqual(evaluation["metrics"]["findings"]["false_positives"], 0)
        # ... and correspondingly finds nothing.
        self.assertEqual(evaluation["metrics"]["findings"]["true_positives"], 0)

    def test_clean_cases_are_scored_per_case(self) -> None:
        document = run_suite(self.suite, MockProvider(), self.prompt)
        evaluation = evaluate_document(document, self.suite, root=ROOT)
        clean = [c for c in evaluation["cases"] if c["is_clean"]]
        self.assertEqual(len(clean), 3)
        for entry in clean:
            self.assertEqual(entry["expected"], 0)
            self.assertEqual(entry["true_positives"], 0)
            self.assertEqual(entry["false_positives"], entry["predicted"])


class MalformedResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = load_suite("php-web-v0.1", root=ROOT)
        cls.prompt = load_prompt("review_v2", root=ROOT)
        cls.document = run_suite(cls.suite, MockProvider(mode="malformed"), cls.prompt)
        cls.evaluation = evaluate_document(cls.document, cls.suite, root=ROOT)

    def test_malformed_output_is_recorded_with_its_errors(self) -> None:
        for response in self.document["responses"]:
            self.assertFalse(response["valid"])
            self.assertTrue(response["validation_errors"])
            self.assertIsNone(response["parsed"])

    def test_malformed_output_scores_zero_rather_than_passing_clean_controls(self) -> None:
        metrics = self.evaluation["metrics"]
        self.assertEqual(metrics["counts"]["invalid_responses"], len(self.suite))
        self.assertEqual(metrics["findings"]["true_positives"], 0)
        self.assertEqual(metrics["findings"]["false_positives"], 0)
        self.assertEqual(metrics["findings"]["false_negatives"], 9)
        self.assertIsNone(metrics["false_alarms"]["clean_case_false_alarm_rate"])


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = load_suite("php-web-v0.1", root=ROOT)
        cls.prompt = load_prompt("review_v2", root=ROOT)
        cls.document = run_suite(cls.suite, MockProvider(), cls.prompt)

    def test_match_mode_is_recorded_and_changes_scoring(self) -> None:
        lenient = evaluate_document(self.document, self.suite, match_mode="defect_type", root=ROOT)
        strict = evaluate_document(
            self.document, self.suite, match_mode="defect_type_file", root=ROOT
        )
        self.assertEqual(lenient["match_mode"], "defect_type")
        self.assertEqual(strict["match_mode"], "defect_type_file")
        self.assertGreaterEqual(
            lenient["metrics"]["findings"]["true_positives"],
            strict["metrics"]["findings"]["true_positives"],
        )

    def test_unknown_match_mode_is_rejected(self) -> None:
        with self.assertRaises(EvaluationError):
            evaluate_document(self.document, self.suite, match_mode="vibes", root=ROOT)

    def test_results_for_an_unknown_case_are_rejected(self) -> None:
        document = json.loads(json.dumps(self.document))
        document["responses"][0]["case_id"] = "not-a-case"
        with self.assertRaises(EvaluationError):
            evaluate_document(document, self.suite, root=ROOT)

    def test_empty_result_file_is_rejected(self) -> None:
        with self.assertRaises(EvaluationError):
            evaluate_document({"run": {}, "responses": []}, self.suite, root=ROOT)

    def test_evaluation_reports_ground_truth_status(self) -> None:
        evaluation = evaluate_document(self.document, self.suite, root=ROOT)
        ground_truth = evaluation["metrics"]["ground_truth"]
        self.assertEqual(ground_truth["cases"], len(self.suite))
        frozen = sum(1 for c in self.suite.cases if c.labels_frozen)
        self.assertEqual(ground_truth["frozen"], frozen)
        self.assertEqual(ground_truth["all_labels_frozen"], frozen == len(self.suite))

    def test_provisional_results_are_flagged_in_the_report(self) -> None:
        evaluation = evaluate_document(self.document, self.suite, root=ROOT)
        markdown = render_markdown(evaluation)
        if evaluation["metrics"]["ground_truth"]["all_labels_frozen"]:
            self.skipTest("all labels are frozen; nothing to flag")
        self.assertIn("Provisional", markdown)

    def test_report_renders_markdown(self) -> None:
        evaluation = evaluate_document(self.document, self.suite, root=ROOT)
        markdown = render_markdown(evaluation)
        self.assertIn("# WebFixBench run report", markdown)
        self.assertIn("php-web-v0.1", markdown)
        self.assertIn("Clean-control false-alarm rate", markdown)
        self.assertIn("deterministic rule-based stub", markdown)
        for case in self.suite.cases:
            self.assertIn(case.id, markdown)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
