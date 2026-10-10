"""Recovery and research-protocol regressions, strictly offline."""
import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from webfixbench.cases import load_suite
from webfixbench.config import ConfigError, load_prompt
from webfixbench.evaluator import EvaluationError, evaluate_document
from webfixbench.experiment import load_experiment, run_experiment, _case_hash
from webfixbench.providers.mock import MockProvider
from webfixbench.runner import run_suite

ROOT = Path(__file__).resolve().parents[1]


class RecoveryTest(unittest.TestCase):
    def test_cli_resume_exposes_explicit_directory(self):
        from webfixbench.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(['experiment', 'example.json', '--resume-dir', 'saved', '--max-requests', '12'])
        self.assertEqual(args.resume_dir, Path('saved'))

    def test_comparison_is_generated_for_a_real_mock_invocation(self):
        experiment = load_experiment(ROOT / 'experiments/mock-skill-conditions.json')
        with tempfile.TemporaryDirectory(dir=ROOT / 'tasks') as directory:
            output = run_experiment(experiment, root=ROOT, output_root=Path(directory), max_requests=12)
            self.assertTrue((output / 'comparison.json').is_file(), 'missing paired artifact')
            self.assertTrue((output / 'configuration.json').is_file(), 'missing recoverable config snapshot')
            snapshot = json.loads((output / 'configuration.json').read_text())
            self.assertNotIn('case_limit', snapshot, 'config snapshot must omit unused selectors, not serialize null')
            self.assertEqual(load_experiment(output / 'configuration.json'), experiment)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertFalse(manifest['comparative_ranking_permitted'], 'mock must not authorize model rankings')
            report = json.loads((output / 'comparison.json').read_text())
            self.assertEqual(len(report['conditions']), 3)
            self.assertEqual(len(report['pairs']), 2)
            self.assertTrue(all(p['delta_detection_rate'] == 0 for p in report['pairs']))
            self.assertTrue(all(p['confidence_interval_95'] is None for p in report['pairs']))
            self.assertIn('Unknown cost fraction', (output / 'summary.md').read_text())

    def test_condition_retry_preserves_exact_failed_pairs_only(self):
        from webfixbench.experiment import retry_failed_experiment
        from webfixbench.providers.base import ProviderResult
        experiment = load_experiment(ROOT / 'experiments/mock-skill-conditions.json')
        class PartialFailure(MockProvider):
            def review(self, prompt, *, case_id=None):
                if 'Trace changed values' in prompt and case_id == experiment.case_ids[0]:
                    return ProviderResult(None, 1.0, 'mock-test', error='offline transport failure')
                return super().review(prompt, case_id=case_id)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tasks') as directory:
            temp = Path(directory)
            with mock.patch('webfixbench.experiment._make_provider', side_effect=lambda *a: PartialFailure()):
                output = run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12)
            original = (output / 'manifest.json').read_bytes()
            calls = []
            class Recovery(MockProvider):
                def review(self, prompt, *, case_id=None):
                    calls.append((case_id, prompt))
                    return super().review(prompt, case_id=case_id)
            with mock.patch('webfixbench.experiment._make_provider', side_effect=lambda *a: Recovery()):
                retry = retry_failed_experiment(output / 'manifest.json', root=ROOT, output_root=temp, max_requests=2)
            manifest = json.loads((retry / 'manifest.json').read_text())
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(cid == experiment.case_ids[0] and 'Trace changed values' in text for cid, text in calls))
            self.assertEqual([r['original_repetition'] for r in manifest['runs']], [1, 2])
            self.assertTrue(all(r['condition_id'] == 'skill' for r in manifest['runs']))
            self.assertEqual((output / 'manifest.json').read_bytes(), original)

    def test_experiment_resume_after_interrupt_is_exact_and_completed_resume_is_free(self):
        import inspect
        self.assertIn('resume_dir', inspect.signature(run_experiment).parameters, 'missing explicit resume')
        experiment = load_experiment(ROOT / 'experiments/mock-skill-conditions.json')
        calls = []
        class Interrupted(MockProvider):
            def review(self, prompt, *, case_id=None):
                calls.append(case_id)
                if len(calls) == 2:
                    raise KeyboardInterrupt('offline interruption')
                return super().review(prompt, case_id=case_id)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tasks') as directory:
            temp = Path(directory)
            with mock.patch('webfixbench.experiment._make_provider', side_effect=lambda *a: Interrupted()):
                with self.assertRaises(KeyboardInterrupt):
                    run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12)
            output = next((temp / experiment.experiment_id).iterdir())
            source = json.loads((output / 'manifest.json').read_text())
            checkpoint = json.loads((output / source['runs'][0]['results']).read_text())
            self.assertEqual(len(checkpoint['responses']), 1)
            resumed_calls = []
            class Resumed(MockProvider):
                def review(self, prompt, *, case_id=None):
                    resumed_calls.append(case_id)
                    return super().review(prompt, case_id=case_id)
            with mock.patch('webfixbench.experiment._make_provider', side_effect=lambda *a: Resumed()):
                result = run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12, resume_dir=output)
            self.assertEqual(result, output)
            self.assertEqual(len(resumed_calls), 11)
            (output / '.active').write_text('test lock')
            with mock.patch('webfixbench.experiment._make_provider', side_effect=AssertionError('no provider needed')):
                with self.assertRaisesRegex(ConfigError, 'already active'):
                    run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12, resume_dir=output)
            (output / '.active').unlink()
            with mock.patch('webfixbench.experiment._make_provider', side_effect=AssertionError('no provider needed')):
                run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12, resume_dir=output)
                with self.assertRaisesRegex(ConfigError, 'configuration'):
                    run_experiment(replace(experiment, timeout=999), root=ROOT, output_root=temp,
                                   max_requests=12, resume_dir=output)
            self.assertEqual(json.loads((output / source['runs'][0]['results']).read_text())['responses'][0],
                             checkpoint['responses'][0])
            import webfixbench.experiment as engine
            self.assertTrue(hasattr(engine, '_engine_fingerprint'), 'missing harness pin')
            with mock.patch('webfixbench.experiment._engine_fingerprint', return_value='changed-code'):
                with mock.patch('webfixbench.experiment._make_provider', side_effect=AssertionError('no provider needed')):
                    with self.assertRaisesRegex(ConfigError, 'engine_fingerprint'):
                        run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12, resume_dir=output)
            manifest_path = output / 'manifest.json'
            complete = json.loads(manifest_path.read_text())
            corrupt = copy.deepcopy(complete)
            corrupt['runs'].append(copy.deepcopy(corrupt['runs'][0]))
            manifest_path.write_text(json.dumps(corrupt))
            with mock.patch('webfixbench.experiment._make_provider', side_effect=AssertionError('no provider needed')):
                with self.assertRaises(ConfigError):
                    run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12, resume_dir=output)
            manifest_path.write_text(json.dumps(complete))
            with mock.patch('webfixbench.experiment._git_state', return_value={'git_sha': 'different', 'dirty': True}):
                with mock.patch('webfixbench.experiment._make_provider', side_effect=AssertionError('no provider needed')):
                    with self.assertRaisesRegex(ConfigError, 'HEAD'):
                        run_experiment(experiment, root=ROOT, output_root=temp, max_requests=12, resume_dir=output)

    def test_checkpoint_saves_prefix_and_resume_skips_it(self):
        import inspect
        self.assertIn('checkpoint', inspect.signature(run_suite).parameters, 'missing atomic checkpoint callback')
        suite = load_suite(root=ROOT)
        case_ids = [case.id for case in suite.cases[:3]]
        saved = []
        calls = []
        class Interrupted(MockProvider):
            def review(self, prompt, *, case_id=None):
                calls.append(case_id)
                if len(calls) == 2:
                    raise KeyboardInterrupt('offline interruption')
                return super().review(prompt, case_id=case_id)
        with self.assertRaises(KeyboardInterrupt):
            run_suite(suite, Interrupted(), load_prompt(root=ROOT), case_ids=case_ids,
                      checkpoint=lambda doc: saved.append(copy.deepcopy(doc)))
        self.assertEqual([r['case_id'] for r in saved[-1]['responses']], case_ids[:1])
        resumed_calls = []
        class Resumed(MockProvider):
            def review(self, prompt, *, case_id=None):
                resumed_calls.append(case_id)
                return super().review(prompt, case_id=case_id)
        doc = run_suite(suite, Resumed(), load_prompt(root=ROOT), case_ids=case_ids,
                        resume_document=saved[-1], checkpoint=lambda doc: None)
        self.assertEqual(resumed_calls, case_ids[1:])
        self.assertEqual(doc['responses'][0], saved[-1]['responses'][0])
        self.assertEqual(doc['run']['run_id'], saved[-1]['run']['run_id'])

    def test_seeded_counterbalanced_schedule_is_reproducible(self):
        import webfixbench.experiment as engine
        self.assertTrue(hasattr(engine, 'build_schedule'), 'missing paired scheduler')
        experiment = replace(load_experiment(ROOT / 'experiments/mock-skill-conditions.json'), schedule_seed=73)
        conditions = experiment.conditions
        first = engine.build_schedule(experiment, conditions)
        second = engine.build_schedule(experiment, conditions)
        self.assertEqual(first, second)
        order1 = [r['condition_id'] for r in first if r['repetition'] == 1]
        order2 = [r['condition_id'] for r in first if r['repetition'] == 2]
        self.assertEqual(order1, order2[::-1])
        self.assertEqual(len(first), 6)

    def test_explicit_skill_resources_and_full_tree_are_pinned(self):
        import webfixbench.conditions as loader
        import hashlib
        self.assertTrue(hasattr(loader, 'fingerprint_skill_tree'), 'missing skill-tree inventory')
        with tempfile.TemporaryDirectory(dir=ROOT / 'tasks') as directory:
            temp = Path(directory)
            main = temp / 'SKILL.md'
            resource = temp / 'checklist.md'
            main.write_text('Use the explicitly delivered checklist.')
            resource.write_text('Literal resource: {{DIFF}}')
            entry = {'condition_id': 'resource', 'kind': 'single_skill',
                     'path': str(main.relative_to(ROOT)), 'sha256': hashlib.sha256(main.read_bytes()).hexdigest(),
                     'resources': [{'path': str(resource.relative_to(ROOT)), 'sha256': hashlib.sha256(resource.read_bytes()).hexdigest()}],
                     'tree_sha256': loader.fingerprint_skill_tree(temp, ROOT)['sha256']}
            condition = loader.materialize_conditions([entry], load_prompt(root=ROOT), ROOT)[0]
            self.assertIn('Literal resource: {{DIFF}}', condition['text'])
            self.assertEqual(len(condition['files']), 2)
            resource.write_text('Changed resource')
            entry['resources'][0]['sha256'] = hashlib.sha256(resource.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ConfigError, 'tree'):
                loader.materialize_conditions([entry], load_prompt(root=ROOT), ROOT)

    def test_ordered_bundle_identity_and_resources(self):
        from webfixbench.conditions import materialize_conditions
        import hashlib
        with tempfile.TemporaryDirectory(dir=ROOT / 'tasks') as directory:
            temp = Path(directory)
            items = []
            for name, text in [('first.md', 'First instruction'), ('second.md', 'Second instruction')]:
                path = temp / name
                path.write_text(text)
                items.append({'path': str(path.relative_to(ROOT)),
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            prompt = load_prompt(root=ROOT)
            first = materialize_conditions([{'condition_id': 'bundle', 'kind': 'bundle', 'skills': items}], prompt, ROOT)[0]
            second = materialize_conditions([{'condition_id': 'bundle', 'kind': 'bundle', 'skills': items[::-1]}], prompt, ROOT)[0]
            self.assertNotEqual(first['sha256'], second['sha256'])
            self.assertLess(first['text'].index('First instruction'), first['text'].index('Second instruction'))
            self.assertEqual(len(first['files']), 2)

    def test_duplicate_responses_cannot_silently_overwrite(self):
        suite = load_suite(root=ROOT)
        doc = run_suite(suite, MockProvider(), load_prompt(root=ROOT), case_ids=[suite.cases[0].id])
        doc['responses'] *= 2
        with self.assertRaisesRegex(EvaluationError, 'duplicate'):
            evaluate_document(doc, suite)

    def test_label_pinned_replay_rejects_changed_case(self):
        suite = load_suite(root=ROOT)
        case = suite.cases[0]
        doc = run_suite(suite, MockProvider(), load_prompt(root=ROOT), case_ids=[case.id])
        doc['run']['case_fingerprints'] = {case.id: _case_hash(case)}
        altered = replace(suite, cases=[replace(case, notes='Changed evaluator evidence')])
        with self.assertRaisesRegex(EvaluationError, 'fingerprint'):
            evaluate_document(doc, altered)
