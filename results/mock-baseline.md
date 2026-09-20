# WebFixBench run report

| Field | Value |
| --- | --- |
| Suite | `php-web-v0.1` (version 0.1.0) |
| Provider | `mock` |
| Model | `mock-heuristic-v1` |
| Temperature | 0.00 |
| Prompt | `review_v2` (sha256 `c7ad40735a4a…`) |
| Match mode | `defect_type` |
| Run id | `6915f22f0198` |
| Run at (UTC) | 2026-09-20T10:38:17+00:00 |
| WebFixBench | 0.1.0.dev0 |
| Mock mode | `heuristic` |

> **Provisional.** 12 of 12 cases have labels that a human has not yet reviewed and frozen. These results are provisional and must not be published as a model evaluation. See docs/ANNOTATION.md.

> The `mock` provider is a deterministic rule-based stub, not a language model. This report exercises the pipeline; it says nothing about any model's review quality.

## Coverage

- Cases scored: **12** (9 with a defect, 3 clean controls)
- Valid structured responses: **12**, malformed: **0**, provider errors: **0**
- Cases with frozen labels: **0** of **12**

## Finding-level results

| Metric | Value |
| --- | --- |
| Expected findings | 9 |
| Predicted findings | 10 |
| True positives | 7 |
| False positives | 3 |
| False negatives | 2 |
| Precision | 0.700 |
| Recall | 0.778 |
| F1 | 0.737 |

## False alarms and detection

| Metric | Value |
| --- | --- |
| Clean-control false-alarm rate | 33.3% (1 of 3 clean cases) |
| Findings on clean controls | 1 |
| Mean false positives per defect case | 0.222 |
| Defect cases with ≥1 correct finding | 77.8% |
| Defect cases with all findings found | 77.8% |

## By ecosystem

| Ecosystem | Cases | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| laravel | 5 | 4 | 1 | 0 | 0.800 | 1.000 |
| php | 3 | 2 | 1 | 0 | 0.667 | 1.000 |
| wordpress | 4 | 1 | 1 | 2 | 0.500 | 0.333 |

## By category

| Category | Expected | TP | FN | FP | Recall | Precision |
| --- | --- | --- | --- | --- | --- | --- |
| authorization | 3 | 2 | 1 | 0 | 0.667 | 1.000 |
| injection | 2 | 2 | 0 | 0 | 1.000 | 1.000 |
| secrets | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| unsafe_deserialization | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| xss | 2 | 1 | 1 | 3 | 0.500 | 0.250 |

## Confidence

| Metric | Value |
| --- | --- |
| Findings with confidence | 10 |
| Mean finding confidence | 0.638 |
| Mean confidence, true positives | 0.779 |
| Mean confidence, false positives | 0.310 |
| Confidence gap (TP − FP) | 0.469 |
| Mean overall_confidence | 0.680 |

Calibration: Confidence values are recorded but not turned into a calibration score in v0.1: a single self-reported confidence does not have well-defined event semantics for Brier/ECE. Not yet measured.

## Cost and latency

| Metric | Value |
| --- | --- |
| Mean latency (ms) | 0.05 |
| Median latency (ms) | 0.04 |
| p95 latency (ms) | 0.06 |
| Input tokens | 10403 |
| Output tokens | 910 |
| Token counts estimated | yes |
| Total cost (USD) | n/a |

## Per-case results

| Case | Ecosystem | Clean | Valid | Expected | Predicted | TP | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `laravel-authz-001` | laravel | no | yes | 1 | 1 | 1 | 0 | 0 |
| `laravel-authz-002` | laravel | no | yes | 1 | 1 | 1 | 0 | 0 |
| `laravel-clean-001` | laravel | yes | yes | 0 | 0 | 0 | 0 | 0 |
| `laravel-injection-001` | laravel | no | yes | 1 | 2 | 1 | 1 | 0 |
| `laravel-xss-001` | laravel | no | yes | 1 | 1 | 1 | 0 | 0 |
| `php-clean-001` | php | yes | yes | 0 | 0 | 0 | 0 | 0 |
| `php-injection-001` | php | no | yes | 1 | 1 | 1 | 0 | 0 |
| `php-secrets-001` | php | no | yes | 1 | 2 | 1 | 1 | 0 |
| `wp-authz-001` | wordpress | no | yes | 1 | 0 | 0 | 0 | 1 |
| `wp-clean-001` | wordpress | yes | yes | 0 | 1 | 0 | 1 | 0 |
| `wp-deser-001` | wordpress | no | yes | 1 | 1 | 1 | 0 | 0 |
| `wp-xss-001` | wordpress | no | yes | 1 | 0 | 0 | 0 | 1 |

---

Numbers describe this single run of a small synthetic suite. They are not a general statement about the reviewer's security capability.
