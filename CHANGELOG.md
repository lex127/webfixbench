# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/) with the understanding that
pre-1.0 releases may change the case schema and the result-file format.

## [Unreleased]

Pre-release research skeleton. A working harness and a small labelled dataset.
**No formal v0.1.0 release or model results have been published.**

### Added

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
- Suite `php-web-v0.1`: 12 synthetic cases (9 with a labelled defect, 3 clean
  controls) across PHP, Laravel and WordPress.
- Providers: `BaseProvider`, deterministic offline `MockProvider`, and OpenAI
  and Anthropic providers speaking the vendors' HTTP APIs. Model ids are never
  defaulted; credentials come from the environment only.
- Metrics: precision, recall, F1, finding-level false positives, clean-control
  false-alarm rate, case-level detection, malformed-response counts, latency,
  token usage, optional cost, and confidence summaries including the gap
  between mean confidence on true and false positives.
- Frozen prompt `prompts/review_v1.txt`, recorded in every run by id and
  SHA-256.
- Documentation: methodology, annotation guide, ethics, related work, dataset,
  real-world source research plan, roadmap and a contributor guide.
- Test suite (136 tests) that never contacts a paid API, plus GitHub Actions CI.
- Mock baseline artifacts in `results/`.

### Known gaps

- Related-work entries are drafted but **not yet verified against primary
  sources**; the project makes no novelty claim until that pass is complete.
- Confidence calibration (Brier, ECE) is **not yet measured**.
- All twelve cases are `pending_review`: drafted, and awaiting the maintainer's
  review pass before their labels are frozen.
- Labels come from a single labeller; inter-rater agreement is **not yet
  measured**.
- No advisory-derived cases yet; [docs/REAL_WORLD_SOURCES.md](docs/REAL_WORLD_SOURCES.md)
  is a research plan whose sources have **not yet been inspected**.
