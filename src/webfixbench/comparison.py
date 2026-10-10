"""Paired operational outcomes, with incident aggregation before cluster bootstrap.

This is exploratory inference, never proof that synthetic fixtures are independent.
"""
from __future__ import annotations

import random
import math
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Sequence

from .config import ConfigError


def _mean(values):
    return statistics.mean(values) if values else None


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def wilson_interval(successes: int, trials: int):
    if not trials:
        return None
    if not 0 <= successes <= trials:
        raise ConfigError('binary successes must be between zero and trials')
    z = 1.959963984540054
    proportion = successes / trials
    scale = 1 + z * z / trials
    center = (proportion + z * z / (2 * trials)) / scale
    margin = z * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)) / scale
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _interval(cluster_values, seed):
    if len(cluster_values) < 2:
        return None
    rng = random.Random(seed)
    groups = list(cluster_values.values())
    estimates = []
    for _ in range(2000):
        sampled = [value for _ in groups for value in rng.choice(groups)]
        estimates.append(statistics.mean(sampled))
    estimates.sort()
    return [estimates[49], estimates[1949]]


def compare_episodes(manifest: Dict[str, Any], episodes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    config = manifest['configuration']
    inventory = manifest['case_inventory']
    repetitions = config['repeat_count']
    instructions = manifest.get('conditions') or [{'condition_id': 'baseline', 'kind': 'baseline'}]
    condition_ids = [c['condition_id'] for c in instructions]
    baseline = [c['condition_id'] for c in instructions if c['kind'] == 'baseline']
    providers = (list(range(1, len(config['providers']) + 1)) if config.get('providers')
                 else sorted({e['provider_index'] for e in episodes} or {1}))
    incident_ids = config.get('incident_ids') or {cid: cid for cid in inventory}
    cluster_ids = config.get('cluster_ids') or {cid: cid for cid in inventory}
    audited_groups = bool(config.get('incident_ids') and config.get('cluster_ids'))
    for mapping in (incident_ids, cluster_ids):
        if set(mapping) != set(inventory):
            raise ConfigError('incident/cluster mapping must cover exactly selected cases')
    incident_clusters = {}
    for cid in inventory:
        incident = incident_ids[cid]
        if incident in incident_clusters and incident_clusters[incident] != cluster_ids[cid]:
            raise ConfigError('one incident cannot belong to multiple clusters')
        incident_clusters[incident] = cluster_ids[cid]
    indexed = {}
    for episode in episodes:
        key = (episode['provider_index'], episode['condition_id'], episode['repetition'], episode['case_id'])
        if key in indexed:
            raise ConfigError('duplicate comparison episode')
        if key[1] not in condition_ids or key[3] not in inventory or not 1 <= key[2] <= repetitions:
            raise ConfigError('unexpected comparison episode identity')
        indexed[key] = episode
    conditions = []
    pairs = []
    per_repetition = []
    for provider in providers:
        outcomes = {}
        for condition in condition_ids:
            records = [indexed.get((provider, condition, rep, cid), {})
                       for rep in range(1, repetitions + 1) for cid in inventory]
            valid = [e for e in records if e.get('valid') and not e.get('error')]
            known_costs = [e['cost_usd'] for e in records if _number(e.get('cost_usd'))]
            latencies = sorted(e['latency_ms'] for e in records if _number(e.get('latency_ms')))
            usages = [e['usage'] for e in records if isinstance(e.get('usage'), dict)]
            tokens = {}
            for name in ('input_tokens', 'output_tokens'):
                values = [u[name] for u in usages if _number(u.get(name))]
                tokens[name] = sum(values) if values else None
            defective = defaultdict(list)
            clean = defaultdict(list)
            complete_defective = defaultdict(list)
            for rep in range(1, repetitions + 1):
                for cid, meta in inventory.items():
                    e = indexed.get((provider, condition, rep, cid), {})
                    good = bool(e.get('valid') and not e.get('error'))
                    if not meta['is_clean']:
                        defective[incident_ids[cid]].append(float(good and e.get('detected', False)))
                        if good:
                            complete_defective[incident_ids[cid]].append(float(e.get('detected', False)))
                    elif good:
                        clean[incident_ids[cid]].append(float(e.get('false_positives', 0) > 0))
            for rep in range(1, repetitions + 1):
                valid_defects = []
                valid_clean = []
                all_defects = []
                for cid, meta in inventory.items():
                    e = indexed.get((provider, condition, rep, cid), {})
                    good = bool(e.get('valid') and not e.get('error'))
                    if not meta['is_clean']:
                        all_defects.append(bool(good and e.get('detected', False)))
                        if good:
                            valid_defects.append(bool(e.get('detected', False)))
                    elif good:
                        valid_clean.append(bool(e.get('false_positives', 0) > 0))
                def binary(values):
                    successes, trials = sum(values), len(values)
                    return {'successes': successes, 'trials': trials,
                            'rate': successes / trials if trials else None,
                            'wilson_95': wilson_interval(successes, trials)}
                per_repetition.append({'provider_index': provider, 'condition_id': condition, 'repetition': rep,
                                       'operational_detection': binary(all_defects),
                                       'valid_only_detection': binary(valid_defects),
                                       'valid_clean_alarms': binary(valid_clean)})
            outcomes[condition] = {incident: statistics.mean(values) for incident, values in defective.items()}
            conditions.append({
                'provider_index': provider, 'condition_id': condition,
                'planned': len(records), 'returned': sum(bool(e) for e in records), 'valid': len(valid),
                'coverage': len(valid) / len(records) if records else None,
                'provider_errors': sum(bool(e.get('error')) for e in records),
                'invalid_responses': sum(bool(e) and not e.get('valid') and not e.get('error') for e in records),
                'missing': sum(not e for e in records),
                'incidents': len(defective), 'detection_rate': _mean(list(outcomes[condition].values())),
                'valid_only_detection_rate': _mean([statistics.mean(v) for v in complete_defective.values()]),
                'clean_incidents_with_valid_response': len(clean),
                'clean_false_alarm_rate': _mean([statistics.mean(v) for v in clean.values()]),
                'mean_false_findings_per_valid_response': _mean([e.get('false_positives', 0) for e in valid]),
                'latency_median_ms': statistics.median(latencies) if latencies else None,
                'latency_p95_ms': latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)] if latencies else None,
                'known_cost_usd': sum(known_costs) if known_costs else None,
                'cost_complete': len(known_costs) == len(records) and bool(records),
                'unknown_cost_fraction': 1 - len(known_costs) / len(records) if records else None,
                'responses_with_usage': len(usages), **tokens,
                'true_positives': sum(e.get('true_positives', 0) for e in records),
                'false_positives': sum(e.get('false_positives', 0) for e in records),
                'false_negatives': sum(e.get('false_negatives', 0) for e in records),
            })
        if len(baseline) != 1:
            continue
        for condition in condition_ids:
            if condition == baseline[0]:
                continue
            a, b = outcomes[baseline[0]], outcomes[condition]
            deltas = {incident: b[incident] - a[incident] for incident in a}
            groups = defaultdict(list)
            for incident, delta in deltas.items():
                groups[incident_clusters[incident]].append(delta)
            pairs.append({
                'provider_index': provider, 'baseline': baseline[0], 'condition': condition,
                'incidents': len(deltas), 'clusters': len(groups),
                'delta_detection_rate': _mean(list(deltas.values())),
                'confidence_interval_95': _interval(groups, config.get('schedule_seed') or 0) if audited_groups else None,
                'improved': sum(v > 0 for v in deltas.values()),
                'worsened': sum(v < 0 for v in deltas.values()),
                'unchanged': sum(v == 0 for v in deltas.values()),
                'incident_deltas': deltas,
            })
    return {
        'comparison_format_version': 1, 'primary_metric': 'operational incident-level defect detection rate',
        'conditions': conditions, 'pairs': pairs, 'repetitions': per_repetition,
        'explicit_grouping': audited_groups,
        'comparative_ranking_permitted': bool(manifest.get('comparative_ranking_permitted')),
        'limitations': [
            'Exploratory only; no power claim, multiplicity correction or mechanism adjudication.',
            'Repeats/variants average within incident; percentile bootstrap resamples entire dependency clusters.',
            'Missing/invalid/error episodes score zero for operational detection, not silently excluded.',
            'Clean alarms and valid-only sensitivity exclude invalid/errors; coverage remains explicit.',
            'Grouping is supplied by the operator, not certified by the harness; missing maps disable intervals.',
            'Few clusters make bootstrap intervals unreliable; controls are not independent extra defects.',
            'TP/FP/FN totals are episode counts, not independent statistical units.',
            'Per-repetition Wilson intervals describe case-level binary counts, not cluster-aware inference.',
        ],
    }


def render_comparison(report: Dict[str, Any]) -> str:
    def show(value):
        if value is None:
            return 'n/a'
        return f'{value:.4f}' if isinstance(value, float) else str(value)
    lines = ['## Operational condition comparison', '',
             '| Config | Condition | Valid/planned | Detection | Clean alarms | Errors | Invalid | Missing | Median ms | p95 ms | Known USD | Unknown cost fraction |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in report['conditions']:
        cells = [row['provider_index'], row['condition_id'], f"{row['valid']}/{row['planned']}",
                 row['detection_rate'], row['clean_false_alarm_rate'], row['provider_errors'],
                 row['invalid_responses'], row['missing'], row['latency_median_ms'], row['latency_p95_ms'],
                 row['known_cost_usd'], row['unknown_cost_fraction']]
        lines.append('| ' + ' | '.join(show(c) for c in cells) + ' |')
    lines += ['', '## Paired incident outcomes', '',
              '| Config | Baseline → condition | Incidents | Clusters | Delta | 95% cluster CI | Improved | Worsened | Unchanged |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for pair in report['pairs']:
        ci = pair['confidence_interval_95']
        cells = [pair['provider_index'], f"{pair['baseline']} → {pair['condition']}", pair['incidents'],
                 pair['clusters'], pair['delta_detection_rate'], 'n/a' if ci is None else f'{ci[0]:.4f} … {ci[1]:.4f}',
                 pair['improved'], pair['worsened'], pair['unchanged']]
        lines.append('| ' + ' | '.join(show(c) for c in cells) + ' |')
    lines += ['', '## Binary counts per repetition (descriptive)', '',
              '| Config | Condition | Rep | Operational detection | 95% Wilson | Valid-only detection | Valid clean alarms |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for row in report.get('repetitions', []):
        def counts(name):
            b = row[name]
            return f"{b['successes']}/{b['trials']}"
        ci = row['operational_detection']['wilson_95']
        cells = [row['provider_index'], row['condition_id'], row['repetition'],
                 counts('operational_detection'), 'n/a' if ci is None else f'{ci[0]:.4f} … {ci[1]:.4f}',
                 counts('valid_only_detection'), counts('valid_clean_alarms')]
        lines.append('| ' + ' | '.join(show(c) for c in cells) + ' |')
    lines += ['', '### Limitations', ''] + ['- ' + s for s in report['limitations']]
    if not report['comparative_ranking_permitted']:
        lines += ['', '**MOCK/SMOKE/PROVISIONAL/SELECTIVE RETRY: comparative ranking is prohibited.**']
    return '\n'.join(lines) + '\n'
