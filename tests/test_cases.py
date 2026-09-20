"""Loading and integrity of the shipped suite."""

import unittest
from pathlib import Path

from webfixbench.cases import list_suites, load_case_file, load_suite
from webfixbench.config import find_root
from webfixbench.schemas import (
    CATEGORIES,
    DEFECT_CATEGORIES,
    LABEL_SOURCES,
    LABEL_STATUSES,
)

ROOT = Path(__file__).resolve().parents[1]


class SuiteLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = load_suite("php-web-v0.1", root=ROOT)

    def test_root_discovery_finds_the_checkout(self) -> None:
        self.assertEqual(find_root(ROOT), ROOT)

    def test_only_the_php_suite_ships_in_v01(self) -> None:
        self.assertEqual(list_suites(ROOT), ["php-web-v0.1"])

    def test_case_count_is_within_the_declared_range(self) -> None:
        self.assertEqual(len(self.suite), 15)
        self.assertEqual(len(self.suite), self.suite.metadata["case_count"])

    def test_cases_are_unique_and_sorted(self) -> None:
        ids = [c.id for c in self.suite.cases]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_suite_has_clean_controls_and_defect_cases(self) -> None:
        self.assertEqual(len(self.suite.clean_cases), 4)
        self.assertEqual(len(self.suite.defect_cases), 11)

    def test_every_ecosystem_is_represented(self) -> None:
        ecosystems = {c.ecosystem for c in self.suite.cases}
        self.assertEqual(ecosystems, {"php", "laravel", "wordpress"})

    def test_clean_controls_have_no_expected_findings(self) -> None:
        for case in self.suite.clean_cases:
            self.assertEqual(case.expected_findings, [], case.id)
            self.assertEqual(case.category, "clean_control", case.id)

    def test_defect_cases_carry_labelled_findings(self) -> None:
        for case in self.suite.defect_cases:
            self.assertTrue(case.expected_findings, case.id)
            for finding in case.expected_findings:
                self.assertIn(finding.category, DEFECT_CATEGORIES, case.id)
                self.assertTrue(finding.description.strip(), case.id)

    def test_categories_stay_inside_the_v01_taxonomy(self) -> None:
        for case in self.suite.cases:
            self.assertIn(case.category, CATEGORIES, case.id)

    def test_sources_match_the_manifest(self) -> None:
        self.assertEqual(
            set(self.suite.metadata["source_types"]),
            {c.source_type for c in self.suite.cases},
        )
        originals = [c for c in self.suite.cases if c.source_type == "synthetic"]
        self.assertEqual(len(originals), 12)
        for case in originals:
            self.assertIsNone(case.source_url, case.id)

    def test_diffs_look_like_unified_diffs(self) -> None:
        for case in self.suite.cases:
            self.assertIn("+++ ", case.diff, case.id)
            self.assertTrue(
                any(line.startswith("+") and not line.startswith("+++") for line in case.diff.splitlines())
                or any(
                    line.startswith("-") and not line.startswith("---")
                    for line in case.diff.splitlines()
                ),
                case.id,
            )

    def test_expected_finding_files_appear_in_the_diff(self) -> None:
        for case in self.suite.defect_cases:
            for finding in case.expected_findings:
                if finding.file:
                    self.assertIn(finding.file, case.diff, case.id)

    def test_every_case_records_label_provenance(self) -> None:
        for case in self.suite.cases:
            self.assertIn(case.label_source, LABEL_SOURCES, case.id)
            self.assertIn(case.label_status, LABEL_STATUSES, case.id)

    def test_v01_ground_truth_is_maintainer_frozen_without_academic_claims(self) -> None:
        for case in self.suite.cases:
            self.assertTrue(case.labels_frozen, case.id)
            self.assertEqual(case.reviewed_by, ["Oleksii Siniaiev"], case.id)
            expected_source = ("public_advisory_plus_human_review"
                               if case.source_type == "public_advisory" else "human_reviewed")
            self.assertEqual(case.label_source, expected_source, case.id)
            self.assertFalse(case.academic_review, case.id)

    def test_no_case_claims_frozen_labels_without_a_reviewer(self) -> None:
        # The schema enforces this; the suite is checked directly so that a
        # future case cannot quietly assert final ground truth.
        for case in self.suite.cases:
            if case.labels_frozen:
                self.assertTrue(case.reviewed_by, case.id)
                self.assertNotEqual(case.label_source, "agent_drafted", case.id)

    def test_academic_review_is_not_claimed_for_unreviewed_cases(self) -> None:
        for case in self.suite.cases:
            if case.academic_review:
                self.assertTrue(case.reviewed_by, case.id)

    def test_get_raises_for_unknown_case(self) -> None:
        with self.assertRaises(KeyError):
            self.suite.get("does-not-exist")

    def test_load_case_file_round_trips(self) -> None:
        path = ROOT / "suites" / "php-web-v0.1" / "cases" / "laravel-authz-001.json"
        case = load_case_file(path)
        self.assertEqual(case.id, "laravel-authz-001")
        self.assertEqual(case.path, path)
        self.assertEqual(case.to_dict()["id"], "laravel-authz-001")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
