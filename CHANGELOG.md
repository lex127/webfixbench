# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/) with the understanding that
pre-1.0 releases may change the case schema and the result-file format.

## [0.1.0rc1] - 2026-09-20

Release candidate with a working harness and a small human-reviewed dataset.
**No final v0.1.0 release or real-model results have been published.**

### Added

- Suite revision 0.1.1: three public-advisory synthetic reconstructions (Laravel
  diagnostic XSS, web argv environment override, and its clean sibling), bringing
  the suite to 15 cases / 11 defects / 4 controls.
- Suite revision 0.1.2: Oleksii Siniaiev reviewed, accepted and froze all 15
  labels. No case received separate academic review.
- Conditional advisory provenance in both case validators and serialization;
  exact fix/license references and measured USE/SKIP decisions for six candidates.
- One precise configuration-injection type, `environment_override_from_web_argv`,
  and immutable `review_v3`; prior prompts and matching logic are unchanged.
- Root AGENTS.md and per-case human review checklists; refreshed offline baseline.
- Reproducible multi-provider experiments with request guards, incremental
  artifacts and manual-only GitHub Actions execution.
- First-party OpenAI, Anthropic, Google Gemini, DeepSeek and xAI adapters with
  vendor-specific structured-output and reasoning controls.

- Benchmark engine: case loading, suite execution, deterministic matching,
  metrics, evaluation and Markdown reporting. No runtime dependencies.
- `webfixbench` CLI: `list`, `show`, `validate`, `run`, `evaluate`, `report`.
- Case schema and model-response schema, validated in Python and published as
  JSON Schema documents in `schema/`.
- Label provenance on every case (`label_source`, `label_status`,
  `reviewed_by`, `academic_review`), enforcing the project's ground-truth rule:
  an agent may draft a fixture, but a case cannot be marked `frozen` without a
  human label source and a named reviewer. Runs against unfrozen labels are
  marked provisional in the CLI, the evaluation document and the report.
- Suite `php-web-v0.1`: 15 synthetic-code cases (11 with a labelled defect, 4
  clean controls), including three advisory-derived reconstructions.
- Providers: `BaseProvider`, deterministic offline `MockProvider`, OpenAI,
  Anthropic, Google Gemini, DeepSeek and xAI. Model ids are never
  defaulted; credentials come from the environment only.
- Metrics: precision, recall, F1, finding-level false positives, clean-control
  false-alarm rate, case-level detection, malformed-response counts, latency,
  token usage, optional cost, and confidence summaries including the gap
  between mean confidence on true and false positives.
- Current prompt `prompts/review_v3.txt`, recorded in every run by id and
  SHA-256.
- Documentation: methodology, annotation guide, ethics, related work, dataset,
  real-world source research plan, roadmap and a contributor guide.
- Offline test suite that never contacts a paid API, plus GitHub Actions CI.
- Mock baseline artifacts in `results/`.

### Known gaps

- Related-work entries have been checked against linked primary sources. The
  project makes no first/only/unique claim.
- Confidence calibration (Brier, ECE) is **not yet measured**.
- Labels come from a single labeller; inter-rater agreement is **not yet
  measured**.
- The three advisory-derived cases are synthetic reconstructions, not vendored
  patches or three independent real-world incidents; two share one mechanism.
