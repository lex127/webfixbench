"""Deterministic matching of predictions to ground truth."""

import unittest

from webfixbench.matching import _same_file, match_case, match_findings
from webfixbench.schemas import Case, ExpectedFinding, PredictedFinding


TYPE_FOR = {
    "authorization": "authorization_policy_removed",
    "injection": "sql_injection",
    "xss": "xss_unescaped_output",
    "secrets": "hardcoded_secret",
    "unsafe_deserialization": "unsafe_deserialization",
}


def expected(category: str, file: str = "app/X.php", defect_type=None) -> ExpectedFinding:
    return ExpectedFinding(
        category=category,
        defect_type=defect_type or TYPE_FOR[category],
        severity="high",
        description="gt",
        file=file,
    )


def predicted(category: str, file=None, confidence=None, defect_type=None) -> PredictedFinding:
    return PredictedFinding(
        category=category,
        defect_type=defect_type or TYPE_FOR.get(category, "unknown_type"),
        severity="high",
        description="pred",
        file=file,
        confidence=confidence,
    )


def make_case(*, is_clean: bool, findings) -> Case:
    return Case(
        id="c1",
        title="t",
        language="php",
        ecosystem="laravel",
        category="clean_control" if is_clean else findings[0].category,
        difficulty="easy",
        source_type="synthetic",
        source_url=None,
        description="d",
        diff="diff",
        expected_findings=list(findings),
        is_clean=is_clean,
    )


class MatchFindingsTests(unittest.TestCase):
    def test_exact_defect_type_match(self) -> None:
        matched, fps, fns = match_findings([expected("xss")], [predicted("xss")])
        self.assertEqual(len(matched), 1)
        self.assertEqual((fps, fns), ([], []))

    def test_category_alias_does_not_affect_defect_type_match(self) -> None:
        matched, _, _ = match_findings(
            [expected("injection")],
            [predicted("SQL Injection", defect_type="sql_injection")],
        )
        self.assertEqual(len(matched), 1)

    def test_wrong_category_is_a_false_positive_and_a_false_negative(self) -> None:
        matched, fps, fns = match_findings([expected("authorization")], [predicted("xss")])
        self.assertEqual(matched, [])
        self.assertEqual(fps, [0])
        self.assertEqual(fns, [0])

    def test_same_category_wrong_mechanism_does_not_match(self) -> None:
        matched, fps, fns = match_findings(
            [expected("authorization", defect_type="authorization_policy_removed")],
            [predicted("authorization", defect_type="authorization_capability_missing")],
        )
        self.assertEqual((matched, fps, fns), ([], [0], [0]))

    def test_unknown_defect_type_is_a_false_positive(self) -> None:
        matched, fps, fns = match_findings(
            [expected("xss")], [predicted("xss", defect_type="made_up_type")]
        )
        self.assertEqual((matched, fps, fns), ([], [0], [0]))

    def test_each_prediction_matches_at_most_one_expected_finding(self) -> None:
        matched, fps, fns = match_findings(
            [expected("xss"), expected("xss")], [predicted("xss")]
        )
        self.assertEqual(len(matched), 1)
        self.assertEqual(fps, [])
        self.assertEqual(fns, [1])

    def test_duplicate_predictions_become_false_positives(self) -> None:
        matched, fps, _ = match_findings([expected("xss")], [predicted("xss"), predicted("xss")])
        self.assertEqual(len(matched), 1)
        self.assertEqual(fps, [1])

    def test_file_aware_candidate_is_preferred(self) -> None:
        matched, fps, _ = match_findings(
            [expected("xss", file="app/View.php")],
            [predicted("xss", file="other/File.php"), predicted("xss", file="app/View.php")],
        )
        self.assertEqual(matched[0].predicted_index, 1)
        self.assertTrue(matched[0].file_matched)
        self.assertEqual(fps, [0])

    def test_defect_type_file_mode_requires_the_right_file(self) -> None:
        matched, fps, fns = match_findings(
            [expected("xss", file="app/View.php")],
            [predicted("xss", file="other/File.php")],
            mode="defect_type_file",
        )
        self.assertEqual(matched, [])
        self.assertEqual((fps, fns), ([0], [0]))

    def test_defect_type_file_mode_accepts_diff_prefixed_paths(self) -> None:
        matched, _, _ = match_findings(
            [expected("xss", file="app/View.php")],
            [predicted("xss", file="b/app/View.php")],
            mode="defect_type_file",
        )
        self.assertEqual(len(matched), 1)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            match_findings([], [], mode="vibes")


class SameFileTests(unittest.TestCase):
    def test_suffix_paths_are_equal(self) -> None:
        self.assertTrue(_same_file("app/Http/X.php", "X.php"))
        self.assertTrue(_same_file("app/Http/X.php", "./app/Http/X.php"))

    def test_different_files_are_not_equal(self) -> None:
        self.assertFalse(_same_file("app/Http/X.php", "app/Http/Y.php"))
        self.assertFalse(_same_file("app/X.php", None))
        self.assertFalse(_same_file(None, "app/X.php"))


class MatchCaseTests(unittest.TestCase):
    def test_clean_control_findings_are_false_positives(self) -> None:
        case = make_case(is_clean=True, findings=[])
        match = match_case(case, [predicted("xss")])
        self.assertEqual(match.true_positives, 0)
        self.assertEqual(match.false_positives, 1)
        self.assertEqual(match.false_negatives, 0)

    def test_clean_control_with_no_findings_is_scored_as_correct(self) -> None:
        match = match_case(make_case(is_clean=True, findings=[]), [])
        self.assertEqual((match.true_positives, match.false_positives, match.false_negatives), (0, 0, 0))

    def test_malformed_response_is_never_a_true_positive(self) -> None:
        case = make_case(is_clean=False, findings=[expected("authorization")])
        match = match_case(case, [predicted("authorization")], valid_response=False)
        self.assertFalse(match.valid_response)
        self.assertEqual(match.true_positives, 0)
        self.assertEqual(match.false_negatives, 1)
        self.assertEqual(match.n_predicted, 0)

    def test_malformed_response_on_a_clean_case_is_not_scored_as_correct(self) -> None:
        match = match_case(make_case(is_clean=True, findings=[]), None, valid_response=False)
        self.assertFalse(match.valid_response)

    def test_detected_flag(self) -> None:
        case = make_case(is_clean=False, findings=[expected("xss"), expected("authorization")])
        match = match_case(case, [predicted("xss")])
        self.assertTrue(match.detected)
        self.assertEqual(match.false_negatives, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
