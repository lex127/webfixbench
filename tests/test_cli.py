"""CLI smoke tests. Every command runs offline against the mock provider."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from webfixbench.cli import main

ROOT = Path(__file__).resolve().parents[1]
ROOT_ARGS = ["--root", str(ROOT)]


def run_cli(*args):
    """Run the CLI, returning ``(exit_code, stdout, stderr)``."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(ROOT_ARGS + list(args))
    return code, out.getvalue(), err.getvalue()


class ListAndShowTests(unittest.TestCase):
    def test_list(self) -> None:
        code, out, _ = run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("php-web-v0.1", out)
        self.assertIn("laravel-authz-001", out)
        self.assertIn("15 cases", out)

    def test_list_json(self) -> None:
        code, out, _ = run_cli("list", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(len(payload["cases"]), 15)

    def test_show(self) -> None:
        code, out, _ = run_cli("show", "laravel-authz-001")
        self.assertEqual(code, 0)
        self.assertIn("Policy check removed", out)
        self.assertIn("## Diff", out)
        self.assertIn("authorize", out)

    def test_show_clean_control_explains_the_empty_ground_truth(self) -> None:
        code, out, _ = run_cli("show", "php-clean-001")
        self.assertEqual(code, 0)
        self.assertIn("clean control", out)

    def test_show_unknown_case_exits_non_zero(self) -> None:
        code, _, err = run_cli("show", "nope")
        self.assertEqual(code, 2)
        self.assertIn("nope", err)

    def test_validate(self) -> None:
        code, out, _ = run_cli("validate")
        self.assertEqual(code, 0)
        self.assertIn("15 cases validated", out)
        self.assertIn("labels:", out)

    def test_list_reports_label_status(self) -> None:
        code, out, _ = run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("frozen labels", out.replace("have frozen labels", "frozen labels"))

    def test_show_reports_label_provenance(self) -> None:
        code, out, _ = run_cli("show", "laravel-authz-001")
        self.assertEqual(code, 0)
        self.assertIn("labels    :", out)
        self.assertIn("reviewed  :", out)

    def test_unknown_suite_exits_non_zero(self) -> None:
        code, _, err = run_cli("list", "--suite", "python-web-v9")
        self.assertEqual(code, 2)
        self.assertIn("unknown suite", err)


class RunEvaluateReportTests(unittest.TestCase):
    def test_full_offline_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "run.json"
            evaluation = Path(tmp) / "eval.json"
            report = Path(tmp) / "report.md"

            code, out, _ = run_cli(
                "run", "--provider", "mock", "--out", str(results), "--quiet", "--evaluate"
            )
            self.assertEqual(code, 0)
            self.assertIn("cases", out)
            document = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual(len(document["responses"]), 15)

            code, out, _ = run_cli("evaluate", str(results), "--out", str(evaluation))
            self.assertEqual(code, 0)
            scored = json.loads(evaluation.read_text(encoding="utf-8"))
            self.assertEqual(scored["match_mode"], "defect_type")
            self.assertEqual(len(scored["cases"]), 15)

            code, _, _ = run_cli("report", str(results), "--out", str(report))
            self.assertEqual(code, 0)
            self.assertIn("# WebFixBench run report", report.read_text(encoding="utf-8"))

            # A report can also be rendered from an already-scored evaluation.
            code, out, _ = run_cli("report", str(evaluation))
            self.assertEqual(code, 0)
            self.assertIn("WebFixBench run report", out)

    def test_run_single_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "one.json"
            code, _, _ = run_cli(
                "run", "--case", "wp-deser-001", "--out", str(results), "--quiet"
            )
            self.assertEqual(code, 0)
            document = json.loads(results.read_text(encoding="utf-8"))
            self.assertEqual([r["case_id"] for r in document["responses"]], ["wp-deser-001"])

    def test_evaluate_prints_a_summary_without_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "run.json"
            run_cli("run", "--out", str(results), "--quiet")
            code, out, _ = run_cli("evaluate", str(results))
            self.assertEqual(code, 0)
            self.assertIn("precision / recall", out)
            self.assertIn("clean false alarms", out)
            self.assertIn("frozen labels", out)

    def test_paid_provider_without_key_exits_non_zero_and_makes_no_call(self) -> None:
        import os
        from unittest import mock as umock

        with umock.patch.dict(os.environ, {}, clear=True):
            code, _, err = run_cli("run", "--provider", "openai", "--model", "some-model")
        self.assertEqual(code, 2)
        self.assertIn("OPENAI_API_KEY", err)

    def test_mock_modes_are_selectable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "run.json"
            code, _, _ = run_cli(
                "run", "--mock-mode", "malformed", "--out", str(results), "--quiet"
            )
            self.assertEqual(code, 0)
            document = json.loads(results.read_text(encoding="utf-8"))
            self.assertTrue(all(not r["valid"] for r in document["responses"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
