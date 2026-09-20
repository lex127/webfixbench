# WebFixBench run report

| Field | Value |
| --- | --- |
| Suite | `php-web-v0.1` (version 0.1.1) |
| Provider | `mock` |
| Model | `mock-heuristic-v1` |
| Temperature | 0.00 |
| Prompt | `review_v3` (sha256 `d2e983ec0fd2…`) |
| Match mode | `defect_type` |
| Run id | `12af5055f743` |
| Run at (UTC) | 2026-09-20T12:44:29+00:00 |
| WebFixBench | 0.1.0.dev0 |
| Mock mode | `heuristic` |

> **Provisional.** 15 of 15 cases have labels that a human has not yet reviewed and frozen. These results are provisional and must not be published as a model evaluation. See docs/ANNOTATION.md.

> The `mock` provider is a deterministic rule-based stub, not a language model. This report exercises the pipeline; it says nothing about any model's review quality.

## Coverage

- Cases scored: **15** (11 with a defect, 4 clean controls)
- Valid structured responses: **15**, malformed: **0**, provider errors: **0**
- Cases with frozen labels: **0** of **15**

## Finding-level results

| Metric | Value |
| --- | --- |
| Expected findings | 11 |
| Predicted findings | 12 |
| True positives | 8 |
| False positives | 4 |
| False negatives | 3 |
| Precision | 0.667 |
| Recall | 0.727 |
| F1 | 0.696 |

## False alarms and detection

| Metric | Value |
| --- | --- |
| Clean-control false-alarm rate | 50.0% (2 of 4 clean cases) |
| Findings on clean controls | 2 |
| Mean false positives per defect case | 0.182 |
| Defect cases with ≥1 correct finding | 72.7% |
| Defect cases with all findings found | 72.7% |

## By ecosystem

| Ecosystem | Cases | TP | FP | FN | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- |
| laravel | 8 | 5 | 2 | 1 | 0.714 | 0.833 |
| php | 3 | 2 | 1 | 0 | 0.667 | 1.000 |
| wordpress | 4 | 1 | 1 | 2 | 0.500 | 0.333 |

## By category

| Category | Expected | TP | FN | FP | Recall | Precision |
| --- | --- | --- | --- | --- | --- | --- |
| authorization | 3 | 2 | 1 | 0 | 0.667 | 1.000 |
| injection | 3 | 2 | 1 | 0 | 0.667 | 1.000 |
| secrets | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| unsafe_deserialization | 1 | 1 | 0 | 0 | 1.000 | 1.000 |
| xss | 3 | 2 | 1 | 4 | 0.667 | 0.333 |

## Confidence

| Metric | Value |
| --- | --- |
| Findings with confidence | 12 |
| Mean finding confidence | 0.620 |
| Mean confidence, true positives | 0.775 |
| Mean confidence, false positives | 0.310 |
| Confidence gap (TP − FP) | 0.465 |
| Mean overall_confidence | 0.668 |

Calibration: Confidence values are recorded but not turned into a calibration score in v0.1: a single self-reported confidence does not have well-defined event semantics for Brier/ECE. Not yet measured.

## Cost and latency

| Metric | Value |
| --- | --- |
| Mean latency (ms) | 0.03 |
| Median latency (ms) | 0.03 |
| p95 latency (ms) | 0.05 |
| Input tokens | 14413 |
| Output tokens | 1099 |
| Token counts estimated | yes |
| Total cost (USD) | n/a |

## Per-case results

| Case | Ecosystem | Clean | Valid | Expected | Predicted | TP | FP | FN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `laravel-authz-001` | laravel | no | yes | 1 | 1 | 1 | 0 | 0 |
| `laravel-authz-002` | laravel | no | yes | 1 | 1 | 1 | 0 | 0 |
| `laravel-clean-001` | laravel | yes | yes | 0 | 0 | 0 | 0 | 0 |
| `laravel-ghsa-debug-xss-001` | laravel | no | yes | 1 | 1 | 1 | 0 | 0 |
| `laravel-ghsa-env-001` | laravel | no | yes | 1 | 0 | 0 | 0 | 1 |
| `laravel-ghsa-env-clean-001` | laravel | yes | yes | 0 | 1 | 0 | 1 | 0 |
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
