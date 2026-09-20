"""Advisory provenance, precise scoring, and small reconstruction integrity."""

import copy
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from webfixbench.cases import load_suite
from webfixbench.config import DEFAULT_PROMPT, load_prompt
from webfixbench.matching import match_case
from webfixbench.runner import build_prompt_text
from webfixbench.schemas import (
    ADVISORY_PROVENANCE_FIELDS,
    DEFECT_TYPES,
    RECONSTRUCTION_TYPES,
    PredictedFinding,
    case_from_dict,
    validate_case_dict,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_SCHEMA = json.loads((ROOT / "schema/case.schema.json").read_text())


def fixture_sides(case):
    """These new fixtures intentionally show one entire file in one hunk."""
    lines = case.diff.splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines) if line.startswith("@@ ")]
    if len(headers) != 1:
        raise AssertionError("expected one self-contained hunk")
    header = headers[0]
    if not re.match(r"@@ -1,\d+ \+1,\d+ @@", lines[header]):
        raise AssertionError("expected complete file from line 1")
    body = lines[header + 1:]
    before = "".join(line[1:] for line in body if line.startswith((" ", "-")))
    after = "".join(line[1:] for line in body if line.startswith((" ", "+")))
    return before, after


class AdvisoryCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = load_suite("php-web-v0.1", root=ROOT)
        cls.cases = [c for c in cls.suite.cases if c.source_type == "public_advisory"]

    def test_human_reviewed_reconstructions_have_traceable_sources(self):
        self.assertEqual(len(self.cases), 3)
        self.assertEqual(len({c.advisory_id for c in self.cases}), 2)
        self.assertEqual(sum(c.is_clean for c in self.cases), 1)
        for case in self.cases:
            with self.subTest(case=case.id):
                self.assertEqual(case.label_status, "frozen")
                self.assertEqual(case.label_source, "public_advisory_plus_human_review")
                self.assertEqual(case.reviewed_by, ["Oleksii Siniaiev"])
                self.assertFalse(case.academic_review)
                self.assertEqual(case.reconstruction_type, "synthetic_reconstruction")
                self.assertEqual(len(case.expected_findings), 0 if case.is_clean else 1)
                self.assertIn(case.advisory_id, case.source_url)
                self.assertTrue(any("/commit/" in ref for ref in case.references))
                self.assertTrue(any("/LICENSE" in ref for ref in case.references))
                raw = json.loads(case.path.read_text())
                self.assertEqual(case.to_dict(), raw)
                self.assertEqual(case_from_dict(case.to_dict()).to_dict(), raw)

    def test_provenance_cannot_be_missing_empty_or_wrongly_typed(self):
        original = self.cases[0].to_dict()
        for field in (*ADVISORY_PROVENANCE_FIELDS, "source_url"):
            for invalid in (None, "", " \n", 17, [], {}):
                with self.subTest(field=field, value=invalid):
                    doc = copy.deepcopy(original)
                    doc[field] = invalid
                    self.assertTrue(validate_case_dict(doc))
            doc = copy.deepcopy(original)
            del doc[field]
            self.assertTrue(validate_case_dict(doc), field)
        doc = dict(original, reconstruction_type="excerpt")
        self.assertTrue(validate_case_dict(doc))
        # Having an advisory never makes an agent's label frozen ground truth.
        self.assertTrue(validate_case_dict(dict(original, label_source="agent_drafted")))

    def test_json_schema_enforces_the_same_provenance_requirements(self):
        rule = next(r for r in CASE_SCHEMA["allOf"]
                    if "source_type" in r["if"]["properties"])
        self.assertEqual(set(rule["then"]["required"]), set(ADVISORY_PROVENANCE_FIELDS))
        self.assertEqual(CASE_SCHEMA["properties"]["reconstruction_type"]["enum"],
                         list(RECONSTRUCTION_TYPES))
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable; Python validation covered separately")
        for field in (*ADVISORY_PROVENANCE_FIELDS, "source_url"):
            for invalid in (None, "", " \n", 17, [], {}):
                with self.subTest(field=field, value=invalid):
                    doc = self.cases[0].to_dict()
                    doc[field] = invalid
                    self.assertFalse(jsonschema.Draft202012Validator(CASE_SCHEMA).is_valid(doc))
            doc = self.cases[0].to_dict()
            del doc[field]
            self.assertFalse(jsonschema.Draft202012Validator(CASE_SCHEMA).is_valid(doc))

    def test_provenance_and_labels_do_not_leak_into_reviewer_prompt(self):
        doc = self.cases[0].to_dict()
        for field in ADVISORY_PROVENANCE_FIELDS:
            if field != "reconstruction_type":
                doc[field] = "PRIVATE_METADATA_SENTINEL"
        doc.update(source_url="PRIVATE_METADATA_SENTINEL", notes="PRIVATE_METADATA_SENTINEL",
                   tags=["PRIVATE_METADATA_SENTINEL"], references=["PRIVATE_METADATA_SENTINEL"])
        doc["expected_findings"][0]["description"] = "PRIVATE_METADATA_SENTINEL"
        prompt = build_prompt_text(load_prompt(root=ROOT), case_from_dict(doc))
        self.assertNotIn("PRIVATE_METADATA_SENTINEL", prompt)
        for field in ("description", "context", "diff"):
            self.assertIn(doc[field], prompt)

    def test_current_prompt_and_suite_advertise_every_supported_type(self):
        self.assertEqual(self.suite.metadata["prompt"], DEFAULT_PROMPT)
        text = load_prompt(root=ROOT).text
        for defect_type in DEFECT_TYPES:
            self.assertIn(defect_type, text)

    def test_configuration_injection_is_not_matched_as_sql_injection(self):
        case = self.suite.get("laravel-ghsa-env-001")
        file = case.expected_findings[0].file
        for mode in ("defect_type", "defect_type_file"):
            wrong = PredictedFinding(category="injection", defect_type="sql_injection",
                                     severity="high", description="Wrong mechanism", file=file)
            result = match_case(case, [wrong], mode=mode)
            self.assertEqual((result.true_positives, result.false_positives,
                              result.false_negatives), (0, 1, 1))
            right = PredictedFinding(category="injection",
                                     defect_type="environment_override_from_web_argv",
                                     severity="high", description="Web argv override", file=file)
            result = match_case(case, [right], mode=mode)
            self.assertEqual((result.true_positives, result.false_positives,
                              result.false_negatives), (1, 0, 0))
            control = match_case(self.suite.get("laravel-ghsa-env-clean-001"), [right], mode=mode)
            self.assertEqual((control.true_positives, control.false_positives), (0, 1))

    def test_new_diffs_apply_and_reverse_as_complete_small_files(self):
        for case in self.cases:
            with self.subTest(case=case.id), tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(case.diff.count("diff --git "), 1)
                self.assertLess(len(case.diff.splitlines()), 40)
                before, after = fixture_sides(case)
                path = next(line[6:] for line in case.diff.splitlines()
                            if line.startswith("+++ b/"))
                target = Path(tmp) / path
                target.parent.mkdir(parents=True)
                target.write_text(before)
                for reverse, expected in ((False, after), (True, before)):
                    args = ["git", "apply"]
                    if reverse:
                        args.append("--reverse")
                    subprocess.run(args, input=case.diff, text=True, cwd=tmp,
                                   check=True, capture_output=True)
                    self.assertEqual(target.read_text(), expected)

    @unittest.skipUnless(shutil.which("php"), "PHP CLI unavailable; no PHP runtime dependency")
    def test_environment_pair_with_inert_arguments(self):
        # No HTTP requests, exploit payloads, files or framework execution.
        # Check the actual reconstructed PHP helpers, not a Python translation.
        vectors = [
            ("cgi-fcgi", [], "production"),
            ("cgi-fcgi", ["--env=staging"], "production"),
            ("cli", [], "production"),
            ("cli", ["--env=staging", "--env=testing"], "staging"),
            ("cli", ["--env="], ""),
        ]
        for case_id in ("laravel-ghsa-env-001", "laravel-ghsa-env-clean-001"):
            case = self.suite.get(case_id)
            before, after = fixture_sides(case)
            for side, code in (("before", before), ("after", after)):
                for sapi, args, safe_expected in vectors:
                    vector = json.dumps([sapi, args, "production"])
                    # json_decode input is JSON embedded as a PHP single-quoted literal.
                    literal = vector.replace("\\", "\\\\").replace("'", "\\'")
                    script = code + "\necho json_encode(selectRuntimeEnvironment(...json_decode('" + literal + "', true)));\n"
                    result = subprocess.run(["php"], input=script, text=True,
                                            check=True, capture_output=True)
                    expected = safe_expected
                    if not case.is_clean and side == "after" and sapi == "cgi-fcgi" and args:
                        expected = "staging"
                    self.assertEqual(json.loads(result.stdout), expected, (case_id, side, sapi, args))


if __name__ == "__main__":
    unittest.main()
