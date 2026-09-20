"""The published JSON Schemas must agree with the Python validator.

The engine validates in Python (no dependencies); ``schema/*.json`` exists for
external tooling. These tests stop the two descriptions from drifting apart,
and additionally validate every shipped case with ``jsonschema`` when that
library happens to be installed.
"""

import json
import unittest
from pathlib import Path

from webfixbench.cases import load_suite
from webfixbench.schemas import (
    CATEGORIES,
    DEFECT_CATEGORIES,
    DIFFICULTIES,
    ECOSYSTEMS,
    LABEL_SOURCES,
    LABEL_STATUSES,
    SEVERITIES,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_SCHEMA = json.loads((ROOT / "schema" / "case.schema.json").read_text(encoding="utf-8"))
RESPONSE_SCHEMA = json.loads(
    (ROOT / "schema" / "model_response.schema.json").read_text(encoding="utf-8")
)


class SchemaDocumentTests(unittest.TestCase):
    def test_case_schema_enums_match_python(self) -> None:
        properties = CASE_SCHEMA["properties"]
        self.assertEqual(properties["category"]["enum"], list(CATEGORIES))
        self.assertEqual(properties["ecosystem"]["enum"], list(ECOSYSTEMS))
        self.assertEqual(properties["difficulty"]["enum"], list(DIFFICULTIES))
        self.assertEqual(properties["label_source"]["enum"], list(LABEL_SOURCES))
        self.assertEqual(properties["label_status"]["enum"], list(LABEL_STATUSES))
        finding = CASE_SCHEMA["$defs"]["expectedFinding"]["properties"]
        self.assertEqual(finding["category"]["enum"], list(DEFECT_CATEGORIES))
        self.assertEqual(finding["severity"]["enum"], list(SEVERITIES))

    def test_case_schema_requires_label_provenance(self) -> None:
        for field in ("label_source", "label_status", "reviewed_by"):
            self.assertIn(field, CASE_SCHEMA["required"])

    def test_response_schema_severity_matches_python(self) -> None:
        finding = RESPONSE_SCHEMA["$defs"]["finding"]["properties"]
        self.assertEqual(finding["severity"]["enum"], list(SEVERITIES))
        self.assertEqual(RESPONSE_SCHEMA["required"], ["findings"])

    def test_shipped_cases_validate_against_the_json_schema_when_available(self) -> None:
        try:
            import jsonschema  # noqa: WPS433 (optional dependency)
        except ImportError:
            self.skipTest("jsonschema is not installed; Python validation already covers this")
        suite = load_suite("php-web-v0.1", root=ROOT)
        for case in suite.cases:
            with self.subTest(case=case.id):
                jsonschema.validate(
                    json.loads(Path(case.path).read_text(encoding="utf-8")), CASE_SCHEMA
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
