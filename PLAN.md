# PLAN — WebFixBench v0.1

The plan this release was built against, kept in the repository so that the
scope of v0.1 and the reasons for its architecture are legible to anyone
reading the code. Forward-looking work lives in [docs/ROADMAP.md](docs/ROADMAP.md).

## Goal

A public-ready **research skeleton**, not a study: a working CLI, one suite of
10–12 labelled diffs, mock plus vendor providers, metrics, tests, CI, and
documentation that is honest about what has not been done.

## Scope delivered

- Python package `webfixbench` and a CLI (`list`, `show`, `validate`, `run`,
  `evaluate`, `report`)
- Case schema and model-response schema, strictly validated
- One suite, `php-web-v0.1`: 12 synthetic cases, 3 of them clean controls
- Providers: base, mock, OpenAI, Anthropic — engine depends on the base class only
- Metrics: TP/FP/FN, precision, recall, F1, clean-control false-alarm rate,
  case-level detection, malformed responses, latency, tokens, optional cost,
  confidence summaries
- Deterministic matching (normalised category, optionally file); no LLM judge
- Frozen prompt `prompts/review_v1.txt`, recorded per run by SHA-256
- Docs: README, methodology, ethics, related work, dataset, roadmap, contributing
- Tests and CI that never call a paid API
- A committed mock baseline

## Architectural decisions

**No runtime dependencies.** The engine, the providers and the metrics are
standard library only. A benchmark whose results depend on a resolved
dependency tree is harder to reproduce years later, and the providers speak the
vendors' documented HTTP APIs directly rather than through SDKs that may change
behaviour under a version bump.

**`suite.json`, not `suite.yaml`.** A deviation from the original layout
sketch, and a direct consequence of the decision above: YAML is not in the
standard library. The manifest is small and JSON costs nothing in readability
here.

**Running and scoring are separate commands.** Result files hold raw output and
run metadata with no scoring applied, so a paid run can be re-scored under a
different matching mode without calling any model again.

**Matching lives in its own module.** `matching.py` is separate from
`evaluator.py` because the matching rule is the most contestable design choice
in the project and should be readable — and replaceable — on its own.

**Reporting lives in its own module.** `report.py` renders Markdown from an
evaluation document; the evaluator does no formatting.

**No vendor prices in the repository.** Pricing is a user-supplied, versioned
table (`config/pricing.sample.json`); cost is `null` without one. Hardcoded
prices go stale silently and corrupt published cost figures.

**No default model ids.** Paid providers require `--model`, so every run
records exactly what produced it and no result can be attributed to a model
that was never chosen.

**The mock provider is deliberately fallible.** It misses two cases and reports
three findings that are not in the ground truth, so precision, recall and
false-alarm metrics are visibly exercised rather than always reading 1.0.

## Non-goals for v0.1

- Additional language suites, or placeholder directories for them
- Subjective defect categories (style, readability, performance, architecture)
- Paid full-suite model runs, or any published model results
- Confidence calibration scores without well-defined event semantics
- Novelty claims of any kind

## Known risks, carried forward

- **Related work is unverified.** Drafted without network access; every entry
  is marked as such. This is a release blocker, tracked in the roadmap.
- **Single labeller.** Twelve cases labelled by one person.
- **Synthetic data.** Cleaner than real pull requests, and built from canonical
  patterns that are plausibly well represented in training data.
- **Small n.** No statistical claim can be made from this suite, and none is.
