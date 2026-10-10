"""Offline regressions for text-only experimental conditions."""
import json
import tempfile
import unittest
from pathlib import Path

from webfixbench.config import ConfigError, load_prompt
from webfixbench.conditions import materialize_conditions
from webfixbench.cases import load_suite
from webfixbench.runner import build_prompt_text
import hashlib
from unittest import mock
from webfixbench.providers.mock import MockProvider
from webfixbench.providers.base import ProviderResult
from webfixbench.experiment import load_experiment, preflight, run_experiment, retry_failed_experiment
from webfixbench.evaluator import evaluate_document


class ConditionsTest(unittest.TestCase):
    def load(self, conditions):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'experiment.json'
            path.write_text(json.dumps({
                'experiment_id': 'conditions-test',
                'providers': [{'provider': 'mock', 'model': 'mock-test'}],
                'conditions': conditions,
            }))
            return load_experiment(path)

    def test_baseline_is_an_explicit_condition(self):
        experiment = self.load([{'condition_id': 'baseline', 'kind': 'baseline'}])
        self.assertEqual(experiment.conditions[0]['condition_id'], 'baseline')

    def test_skill_text_is_literal_and_baseline_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        prompt = load_prompt(root=root)
        case = load_suite(root=root).cases[0]
        with tempfile.TemporaryDirectory(dir=root / "tasks") as directory:
            path = Path(directory) / "skill.txt"
            text = "Do not substitute {{DIFF}} or {{CONTEXT}} here."
            path.write_text(text)
            entries = [{"condition_id": "baseline", "kind": "baseline"},
                       {"condition_id": "skill", "kind": "single_skill",
                        "path": str(path.relative_to(root)),
                        "sha256": hashlib.sha256(text.encode()).hexdigest()}]
            loaded = materialize_conditions(entries, prompt, root)
            baseline = build_prompt_text(prompt, case)
            self.assertEqual(build_prompt_text(loaded[0]["prompt"], case), baseline)
            self.assertIn(text, build_prompt_text(loaded[1]["prompt"], case))
            self.assertIn(baseline, build_prompt_text(loaded[1]["prompt"], case))
            entries[1]["sha256"] = "0" * 64
            with self.assertRaises(ConfigError):
                materialize_conditions(entries, prompt, root)

    def test_condition_runs_have_isolated_inputs_and_replay(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / "tasks") as directory:
            temp = Path(directory)
            skill = temp / "skill.txt"
            skill.write_text("Inspect callers before reporting a defect.")
            config = temp / "config.json"
            config.write_text(json.dumps({
                "experiment_id": "isolated", "case_limit": 2, "repeat_count": 2,
                "providers": [{"provider": "mock", "model": "test"}],
                "conditions": [
                    {"condition_id": "baseline", "kind": "baseline"},
                    {"condition_id": "skill", "kind": "single_skill",
                     "path": str(skill.relative_to(root)),
                     "sha256": hashlib.sha256(skill.read_bytes()).hexdigest()},
                ],
            }))
            experiment = load_experiment(config)
            with self.assertRaisesRegex(ConfigError, "8 requests"):
                preflight(experiment, root=root, max_requests=7, require_keys=False)
            output = run_experiment(experiment, root=root, output_root=temp, max_requests=8)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["planned_requests"], 8)
            self.assertEqual(len(manifest["runs"]), 4)
            self.assertEqual(len({r["path"] for r in manifest["runs"]}), 4)
            self.assertEqual(manifest["status"], "completed")
            for run in manifest["runs"]:
                doc = json.loads((output / run["results"]).read_text())
                inputs = json.loads((output / run["path"] / "inputs.json").read_text())
                self.assertEqual(len(doc["responses"]), 2)
                self.assertEqual(doc["run"]["condition"]["condition_id"], run["condition_id"])
                for case_id, text in inputs.items():
                    self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),
                                     doc["run"]["input_fingerprints"][case_id])
                    self.assertEqual("Inspect callers" in text, run["condition_id"] == "skill")
                replay = evaluate_document(doc, root=root)
                original = json.loads((output / run["evaluation"]).read_text())
                self.assertEqual(replay["metrics"], original["metrics"])
            summary = (output / "summary.md").read_text()
            self.assertIn("| Condition |", summary)
            for block in summary.split("\n\n"):
                rows = [line for line in block.splitlines() if line.startswith("|")]
                if rows:
                    self.assertTrue(all(row.count("|") == rows[0].count("|") for row in rows))
            manifest["runs"][1]["status"] = "failed"
            (output / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ConfigError, "condition-aware retry"):
                retry_failed_experiment(output / "manifest.json", root=root,
                                        output_root=temp, max_requests=8)

    def test_baseline_rejects_instruction_text(self):
        with self.assertRaises(ConfigError):
            self.load([{'condition_id': 'baseline', 'kind': 'baseline', 'path': 'skill.txt'}])

    def test_pinned_mismatch_blocks_all_provider_construction(self):
        root = Path(__file__).resolve().parents[1]
        experiment = self.load([{"condition_id": "skill", "kind": "single_skill",
                                "path": "experiments/skills/review-demo-v1.txt", "sha256": "0" * 64}])
        with mock.patch("webfixbench.experiment._make_provider") as make:
            with self.assertRaisesRegex(ConfigError, "mismatch"):
                preflight(experiment, root=root, max_requests=100, require_keys=True)
            make.assert_not_called()

    def test_null_effect_and_false_alarm_increase_are_not_hidden(self):
        root = Path(__file__).resolve().parents[1]
        example = root / "experiments/mock-skill-conditions.json"
        experiment = load_experiment(example)
        # Deliberately adverse offline test double, not simulated research evidence.
        class AdverseReviewer(MockProvider):
            def review(self, prompt, *, case_id=None):
                self_calls.append((case_id, prompt))
                findings = []
                if "Trace changed values" in prompt:
                    findings = [{"category": "xss", "defect_type": "xss_unescaped_output",
                                 "severity": "low", "file": None, "line": None,
                                 "description": "Deliberate false alarm test fixture.", "confidence": 0.5}]
                return ProviderResult(json.dumps({"findings": findings, "overall_confidence": 0.5}),
                                      1.0, "adverse-offline-test")
        self_calls = []
        with tempfile.TemporaryDirectory(dir=root / "tasks") as directory:
            with mock.patch("webfixbench.experiment._make_provider", side_effect=lambda *args: AdverseReviewer()):
                output = run_experiment(experiment, root=root, output_root=Path(directory), max_requests=12)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(len(self_calls), 12)
            evaluated = {}
            for run in manifest["runs"]:
                metrics = json.loads((output / run["evaluation"]).read_text())["metrics"]
                evaluated.setdefault(run["condition_id"], []).append(metrics)
                inputs = json.loads((output / run["path"] / "inputs.json").read_text())
                for case_id, text in inputs.items():
                    self.assertIn((case_id, text), self_calls)
            self.assertEqual(evaluated["baseline"], evaluated["generic"])
            self.assertEqual(evaluated["baseline"][0]["false_alarms"]["clean_case_false_alarm_rate"], 0.0)
            self.assertEqual(evaluated["skill"][0]["false_alarms"]["clean_case_false_alarm_rate"], 1.0)
            self.assertGreater(evaluated["skill"][0]["findings"]["false_positives"],
                               evaluated["baseline"][0]["findings"]["false_positives"])

    def test_invalid_and_error_evidence_survive_each_condition(self):
        root = Path(__file__).resolve().parents[1]
        experiment = load_experiment(root / "experiments/mock-skill-conditions.json")
        class FailingReviewer(MockProvider):
            def review(self, prompt, *, case_id=None):
                if "Trace changed values" in prompt:
                    return ProviderResult(None, 1.0, "offline-test", error="offline test timeout")
                return ProviderResult("invalid JSON", 1.0, "offline-test")
        with tempfile.TemporaryDirectory(dir=root / "tasks") as directory:
            with mock.patch("webfixbench.experiment._make_provider", side_effect=lambda *args: FailingReviewer()):
                output = run_experiment(experiment, root=root, output_root=Path(directory), max_requests=12)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            for run in manifest["runs"]:
                doc = json.loads((output / run["results"]).read_text())
                if run["condition_id"] == "skill":
                    self.assertEqual(run["status"], "failed")
                    self.assertTrue(all(r["error"] for r in doc["responses"]))
                else:
                    self.assertEqual(run["status"], "completed_with_invalid_responses")
                    self.assertTrue(all(r["raw"] == "invalid JSON" for r in doc["responses"]))

    def test_invalid_text_configs_are_rejected(self):
        for changes in ({"path": "../outside.txt"}, {"path": "/outside.txt"},
                        {"sha256": "not-a-digest"}, {"delivery": "native"}):
            with self.subTest(changes=changes), self.assertRaises(ConfigError):
                self.load([{"condition_id": "skill", "kind": "single_skill",
                            "path": "skills/sample.txt", "sha256": "0" * 64, **changes}])
        for conditions in (None, [], {}, ["baseline"]):
            with self.subTest(conditions=conditions), self.assertRaises(ConfigError):
                self.load(conditions)

    def test_symlink_escape_is_rejected(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / "tasks") as directory:
            target = Path(directory) / "escape.txt"
            target.symlink_to(root.parent / "outside.txt")
            with self.assertRaisesRegex(ConfigError, "outside benchmark root"):
                materialize_conditions([{
                    "condition_id": "skill", "kind": "single_skill",
                    "path": str(target.relative_to(root)), "sha256": "0" * 64,
                }], load_prompt(root=root), root)

    def test_case_insensitive_collision_is_rejected(self):
        with self.assertRaises(ConfigError):
            self.load([{"condition_id": name, "kind": "baseline"}
                       for name in ("baseline", "BASELINE")])

    def test_duplicate_conditions_are_rejected(self):
        with self.assertRaises(ConfigError):
            self.load([{'condition_id': 'baseline', 'kind': 'baseline'}] * 2)
