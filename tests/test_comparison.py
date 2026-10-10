"""Tests for paired incident-level research summaries, no provider calls."""
import unittest
import importlib
import importlib.util


class ComparisonTest(unittest.TestCase):
    def test_binary_intervals_keep_empty_denominators_unknown(self):
        from webfixbench import comparison
        self.assertTrue(hasattr(comparison, 'wilson_interval'), 'missing per-run binary intervals')
        self.assertIsNone(comparison.wilson_interval(0, 0))
        interval = comparison.wilson_interval(1, 1)
        self.assertGreater(interval[0], 0)
        self.assertAlmostEqual(interval[1], 1.0)

    def test_unknown_grouping_disables_intervals_and_duplicate_is_rejected(self):
        from webfixbench.comparison import compare_episodes
        from webfixbench.config import ConfigError
        manifest = {'configuration': {'repeat_count': 1}, 'case_inventory': {'a': {'is_clean': False}},
                    'conditions': [{'condition_id': 'base', 'kind': 'baseline'},
                                   {'condition_id': 'skill', 'kind': 'single_skill'}]}
        baseline = {'provider_index': 1, 'condition_id': 'base', 'repetition': 1, 'case_id': 'a',
                    'valid': True, 'detected': True, 'false_positives': 0, 'cost_usd': None}
        skill = {**baseline, 'condition_id': 'skill', 'valid': False, 'error': 'offline error'}
        report = compare_episodes(manifest, [baseline, skill])
        self.assertEqual(report['pairs'][0]['delta_detection_rate'], -1.0)
        self.assertIsNone(report['pairs'][0]['confidence_interval_95'])
        self.assertEqual(report['conditions'][1]['provider_errors'], 1)
        self.assertEqual(report['conditions'][1]['invalid_responses'], 0)
        self.assertEqual(report['conditions'][1]['coverage'], 0)
        with self.assertRaisesRegex(ConfigError, 'duplicate'):
            compare_episodes(manifest, [baseline, baseline])

    def test_repetitions_and_variants_are_not_independent_units(self):
        self.assertIsNotNone(importlib.util.find_spec('webfixbench.comparison'), 'missing comparison engine')
        comparison = importlib.import_module('webfixbench.comparison')
        manifest = {
            'configuration': {'repeat_count': 3, 'schedule_seed': 7,
                              'incident_ids': {'a': 'one', 'b': 'one', 'c': 'two'},
                              'cluster_ids': {'a': 'family1', 'b': 'family1', 'c': 'family2'}},
            'case_inventory': {cid: {'is_clean': False} for cid in ['a', 'b', 'c']},
            'conditions': [{'condition_id': 'base', 'kind': 'baseline'},
                           {'condition_id': 'skill', 'kind': 'single_skill'}],
            'comparative_ranking_permitted': True,
        }
        episodes = []
        for repetition in range(1, 4):
            for cid in ['a', 'b', 'c']:
                for condition in ['base', 'skill']:
                    episodes.append({'provider_index': 1, 'condition_id': condition,
                                     'repetition': repetition, 'case_id': cid, 'valid': True,
                                     'detected': condition == 'skill', 'false_positives': 0,
                                     'error': None, 'latency_ms': 1, 'cost_usd': None, 'usage': None})
        report = comparison.compare_episodes(manifest, episodes)
        pair = report['pairs'][0]
        self.assertEqual(pair['incidents'], 2)
        self.assertEqual(pair['clusters'], 2)
        self.assertEqual(pair['delta_detection_rate'], 1.0)
        self.assertEqual(pair['confidence_interval_95'], [1.0, 1.0])
        self.assertEqual(report['conditions'][0]['known_cost_usd'], None)
        self.assertEqual(report['conditions'][0]['unknown_cost_fraction'], 1.0)
