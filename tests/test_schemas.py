"""Case and model-response validation."""

import copy
import unittest

from webfixbench.schemas import (
    UNKNOWN_CATEGORY,
    ValidationError,
    case_from_dict,
    model_response_from_dict,
    normalize_category,
    parse_model_response,
    validate_case_dict,
    validate_model_response_dict,
)

VALID_CASE = {
    "id": "example-authz-001",
    "title": "Example",
    "language": "php",
    "ecosystem": "laravel",
    "category": "authorization",
    "difficulty": "easy",
    "source_type": "synthetic",
    "source_url": None,
    "description": "An example case.",
    "diff": "--- a/x.php\n+++ b/x.php\n-    $this->authorize('update', $post);\n",
    "expected_findings": [
        {
            "id": "f1",
            "category": "authorization",
            "defect_type": "authorization_policy_removed",
            "severity": "high",
            "file": "x.php",
            "description": "Authorization check removed.",
        }
    ],
    "is_clean": False,
    "label_source": "agent_drafted",
    "label_status": "pending_review",
    "reviewed_by": [],
}


def case_without(**overrides):
    doc = copy.deepcopy(VALID_CASE)
    doc.update(overrides)
    return doc


class CaseValidationTests(unittest.TestCase):
    def test_valid_case_has_no_errors(self) -> None:
        self.assertEqual(validate_case_dict(VALID_CASE), [])
        self.assertEqual(case_from_dict(VALID_CASE).id, "example-authz-001")

    def test_missing_required_field_is_rejected(self) -> None:
        doc = copy.deepcopy(VALID_CASE)
        del doc["diff"]
        errors = validate_case_dict(doc)
        self.assertTrue(any("diff" in e for e in errors), errors)
        with self.assertRaises(ValidationError):
            case_from_dict(doc)

    def test_unknown_field_is_rejected(self) -> None:
        errors = validate_case_dict(case_without(severity="high"))
        self.assertTrue(any("unknown field" in e for e in errors), errors)

    def test_category_outside_the_taxonomy_is_rejected(self) -> None:
        errors = validate_case_dict(case_without(category="performance"))
        self.assertTrue(any("category" in e for e in errors), errors)

    def test_clean_case_with_expected_findings_is_rejected(self) -> None:
        doc = case_without(is_clean=True, category="clean_control")
        errors = validate_case_dict(doc)
        self.assertTrue(any("clean cases must have an empty" in e for e in errors), errors)

    def test_defect_case_without_findings_is_rejected(self) -> None:
        errors = validate_case_dict(case_without(expected_findings=[]))
        self.assertTrue(any("at least one expected finding" in e for e in errors), errors)

    def test_case_category_must_match_a_finding(self) -> None:
        errors = validate_case_dict(case_without(category="xss"))
        self.assertTrue(any("must match at least one expected finding" in e for e in errors), errors)

    def test_clean_control_category_requires_is_clean(self) -> None:
        errors = validate_case_dict(case_without(category="clean_control"))
        self.assertTrue(any("requires is_clean" in e for e in errors), errors)

    def test_expected_finding_cannot_use_clean_control_category(self) -> None:
        doc = copy.deepcopy(VALID_CASE)
        doc["expected_findings"][0]["category"] = "clean_control"
        errors = validate_case_dict(doc)
        self.assertTrue(any("expected_findings[0].category" in e for e in errors), errors)

    def test_bad_id_characters_are_rejected(self) -> None:
        errors = validate_case_dict(case_without(id="Example Case"))
        self.assertTrue(any("case.id" in e for e in errors), errors)

    def test_non_object_is_rejected(self) -> None:
        self.assertEqual(validate_case_dict(["not", "a", "case"]), ["case must be a JSON object"])


class LabelProvenanceTests(unittest.TestCase):
    """Ground truth may not be frozen by an agent, or frozen anonymously."""

    def test_label_fields_are_required(self) -> None:
        doc = copy.deepcopy(VALID_CASE)
        del doc["label_status"]
        errors = validate_case_dict(doc)
        self.assertTrue(any("label_status" in e for e in errors), errors)

    def test_unknown_label_status_is_rejected(self) -> None:
        errors = validate_case_dict(case_without(label_status="probably-fine"))
        self.assertTrue(any("label_status" in e for e in errors), errors)

    def test_agent_drafted_case_cannot_be_frozen(self) -> None:
        errors = validate_case_dict(
            case_without(label_status="frozen", label_source="agent_drafted", reviewed_by=["someone"])
        )
        self.assertTrue(any("agent-drafted" in e for e in errors), errors)

    def test_frozen_case_requires_a_named_reviewer(self) -> None:
        errors = validate_case_dict(
            case_without(label_status="frozen", label_source="human_reviewed", reviewed_by=[])
        )
        self.assertTrue(any("reviewed_by" in e for e in errors), errors)

    def test_properly_frozen_case_is_accepted(self) -> None:
        doc = case_without(
            label_status="frozen", label_source="human_reviewed", reviewed_by=["a-human"]
        )
        self.assertEqual(validate_case_dict(doc), [])
        self.assertTrue(case_from_dict(doc).labels_frozen)

    def test_pending_case_is_not_frozen(self) -> None:
        self.assertFalse(case_from_dict(VALID_CASE).labels_frozen)

    def test_academic_review_defaults_to_false_and_must_be_boolean(self) -> None:
        self.assertFalse(case_from_dict(VALID_CASE).academic_review)
        errors = validate_case_dict(case_without(academic_review="yes"))
        self.assertTrue(any("academic_review" in e for e in errors), errors)


class CategoryNormalizationTests(unittest.TestCase):
    def test_canonical_categories_pass_through(self) -> None:
        self.assertEqual(normalize_category("authorization"), "authorization")

    def test_aliases_are_mapped(self) -> None:
        self.assertEqual(normalize_category("SQL Injection"), "injection")
        self.assertEqual(normalize_category("cross-site-scripting"), "xss")
        self.assertEqual(normalize_category("Insecure Deserialization"), "unsafe_deserialization")
        self.assertEqual(normalize_category("hardcoded_credentials"), "secrets")
        self.assertEqual(normalize_category("broken access control"), "authorization")

    def test_unknown_categories_become_other_rather_than_being_dropped(self) -> None:
        self.assertEqual(normalize_category("code smell"), UNKNOWN_CATEGORY)
        self.assertEqual(normalize_category(None), UNKNOWN_CATEGORY)
        self.assertEqual(normalize_category(42), UNKNOWN_CATEGORY)

    def test_csrf_and_nonce_are_not_authorization_aliases(self) -> None:
        self.assertEqual(normalize_category("csrf"), UNKNOWN_CATEGORY)
        self.assertEqual(normalize_category("missing_nonce_verification"), UNKNOWN_CATEGORY)


class ModelResponseValidationTests(unittest.TestCase):
    def test_empty_findings_list_is_valid(self) -> None:
        self.assertEqual(validate_model_response_dict({"findings": []}), [])
        self.assertEqual(model_response_from_dict({"findings": []}).findings, [])

    def test_missing_findings_key_is_invalid(self) -> None:
        errors = validate_model_response_dict({"overall_confidence": 0.5})
        self.assertTrue(any("findings" in e for e in errors), errors)

    def test_confidence_out_of_range_is_invalid(self) -> None:
        doc = {
            "findings": [
                {
                    "category": "xss",
                    "defect_type": "xss_unescaped_output",
                    "severity": "high",
                    "description": "x",
                    "confidence": 1.4,
                }
            ]
        }
        errors = validate_model_response_dict(doc)
        self.assertTrue(any("confidence" in e for e in errors), errors)

    def test_bad_severity_is_invalid(self) -> None:
        doc = {
            "findings": [
                {
                    "category": "xss",
                    "defect_type": "xss_unescaped_output",
                    "severity": "catastrophic",
                    "description": "x",
                }
            ]
        }
        errors = validate_model_response_dict(doc)
        self.assertTrue(any("severity" in e for e in errors), errors)

    def test_parse_accepts_a_fenced_json_block(self) -> None:
        text = '```json\n{"findings": [], "overall_confidence": 0.4}\n```'
        response = parse_model_response(text)
        self.assertEqual(response.findings, [])
        self.assertEqual(response.overall_confidence, 0.4)

    def test_parse_extracts_json_surrounded_by_prose(self) -> None:
        text = 'Here is my review:\n{"findings": []}\nHope that helps.'
        self.assertEqual(parse_model_response(text).findings, [])

    def test_parse_rejects_prose_only_output(self) -> None:
        with self.assertRaises(ValidationError):
            parse_model_response("Looks fine to me.")

    def test_parse_rejects_empty_output(self) -> None:
        with self.assertRaises(ValidationError):
            parse_model_response("   ")

    def test_parse_rejects_valid_json_with_wrong_shape(self) -> None:
        with self.assertRaises(ValidationError):
            parse_model_response('{"result": "ok"}')


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
