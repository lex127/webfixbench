"""Experiment validation, safety gates, and incremental execution."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from webfixbench.config import ConfigError
from webfixbench.experiment import load_experiment, preflight, run_experiment

ROOT = Path(__file__).resolve().parents[1]


def config(**changes):
    doc = {"experiment_id": "test-exp", "suite_id": "php-web-v0.1",
           "prompt_id": "review_v3", "case_limit": 2,
           "providers": [{"provider": "mock", "model": "mock-heuristic-v1",
                          "output_constraint": "native_json"}],
           "repeat_count": 1, "timeout": 10, "max_output_tokens": 100, "mode": "reviewed"}
    doc.update(changes)
    return doc


class ExperimentTests(unittest.TestCase):
    def load(self, doc):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        try:
            json.dump(doc, tmp); tmp.close()
            return load_experiment(Path(tmp.name))
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_unknown_fields_and_unsafe_ids_are_rejected(self):
        with self.assertRaises(ConfigError):
            self.load(config(surprise=True))
        with self.assertRaises(ConfigError):
            self.load(config(experiment_id="../escape"))

    def test_invalid_vendor_settings_are_rejected_before_keys(self):
        paid = {"provider": "deepseek", "model": "m", "api_key_env": "DEEPSEEK_API_KEY",
                "output_constraint": "json_schema", "reasoning_effort": "high"}
        with self.assertRaisesRegex(ConfigError, "does not support"):
            self.load(config(providers=[paid], mode="smoke"))

    def test_gemini_settings_and_sonnet_sampling_are_validated(self):
        gemini = {"provider": "gemini", "model": "gemini-3.8-flash",
                  "api_key_env": "GEMINI_API_KEY", "output_constraint": "json_schema",
                  "reasoning_effort": "low", "model_id_stability": "stable_alias"}
        self.load(config(providers=[gemini], mode="smoke"))
        with self.assertRaisesRegex(ConfigError, "reasoning_effort"):
            self.load(config(providers=[{**gemini, "reasoning_effort": "minimal"}], mode="smoke"))
        anthropic = {"provider": "anthropic", "model": "claude-sonnet-5",
                     "api_key_env": "ANTHROPIC_API_KEY", "output_constraint": "json_schema",
                     "temperature": 0.0}
        with self.assertRaisesRegex(ConfigError, "temperature"):
            self.load(config(providers=[anthropic], mode="smoke"))

    def test_request_guard_is_checked(self):
        experiment = self.load(config(repeat_count=3))
        with self.assertRaisesRegex(ConfigError, "exceeding"):
            preflight(experiment, root=ROOT, max_requests=5, require_keys=False)

    def test_paid_pending_labels_require_limited_smoke(self):
        paid = {"provider": "xai", "model": "m", "api_key_env": "XAI_API_KEY",
                "output_constraint": "json_schema"}
        experiment = self.load(config(providers=[paid], case_limit=2))
        from webfixbench.cases import load_suite
        suite = load_suite("php-web-v0.1", root=ROOT)
        suite.cases[0] = replace(suite.cases[0], label_status="pending_review",
                                 label_source="agent_drafted", reviewed_by=[])
        with mock.patch("webfixbench.experiment.load_suite", return_value=suite):
            with self.assertRaisesRegex(ConfigError, "frozen labels"):
                preflight(experiment, root=ROOT, max_requests=10, require_keys=False)
        experiment = self.load(config(providers=[paid], case_limit=4, mode="smoke"))
        with self.assertRaisesRegex(ConfigError, "limited to 3"):
            preflight(experiment, root=ROOT, max_requests=10, require_keys=False)

    def test_missing_key_is_reported_without_request(self):
        paid = {"provider": "xai", "model": "m", "api_key_env": "XAI_API_KEY",
                "output_constraint": "json_schema"}
        experiment = self.load(config(providers=[paid], mode="smoke"))
        with mock.patch.dict(os.environ, {}, clear=True):
            _, _, missing = preflight(experiment, root=ROOT, max_requests=10, require_keys=False)
        self.assertEqual(missing, ["XAI_API_KEY"])

    def test_mock_multi_repeat_end_to_end_and_no_overwrite(self):
        experiment = self.load(config(repeat_count=2))
        with tempfile.TemporaryDirectory() as tmp:
            first = run_experiment(experiment, root=ROOT, output_root=Path(tmp), max_requests=10)
            second = run_experiment(experiment, root=ROOT, output_root=Path(tmp), max_requests=10)
            self.assertNotEqual(first, second)
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(len(manifest["runs"]), 2)
            self.assertEqual(len(manifest["repository"]["git_sha"]), 40)
            self.assertEqual(len(manifest["case_fingerprints"]), 2)
            self.assertEqual(len(manifest["input_fingerprints"]), 2)
            self.assertIn("configuration", manifest)
            for entry in manifest["runs"]:
                self.assertTrue((first / entry["results"]).is_file())
                self.assertTrue((first / entry["evaluation"]).is_file())
                self.assertTrue((first / entry["report"]).is_file())

    def test_later_failure_preserves_completed_run(self):
        experiment = self.load(config(providers=[
            {"provider": "mock", "model": "mock-heuristic-v1", "output_constraint": "native_json"},
            {"provider": "mock", "model": "mock-heuristic-v1", "output_constraint": "native_json"}]))
        from webfixbench.experiment import _make_provider as real_make
        calls = 0
        def make(entry, exp):
            nonlocal calls
            calls += 1
            # Two preflight constructions, then execution constructions.
            if calls == 4:
                raise RuntimeError("later failure")
            return real_make(entry, exp)
        with tempfile.TemporaryDirectory() as tmp, mock.patch("webfixbench.experiment._make_provider", side_effect=make):
            directory = run_experiment(experiment, root=ROOT, output_root=Path(tmp), max_requests=10)
            manifest = json.loads((directory / "manifest.json").read_text())
        self.assertEqual([x["status"] for x in manifest["runs"]], ["completed", "failed"])
        self.assertIsNotNone(manifest["runs"][0]["results"])


if __name__ == "__main__":
    unittest.main()
