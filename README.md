# WebFixBench

WebFixBench is a reproducible benchmark for evaluating the reliability of
LLM-assisted code review on web-application changes.

WebFixBench v0.1 reports a PHP web ecosystem baseline covering PHP, Laravel and
WordPress. Version 0.1.0rc1 is a release candidate with a working evaluation
harness and a small, human-reviewed dataset; it is not a completed empirical
study. No real-model results are published yet.

## Why

LLM reviewers are already embedded in pull-request workflows. Most public
evaluation of them measures whether a model can *solve* an issue or *produce a
patch*. Reviewing is a different job, and its failure modes are different:

- a confident finding that is not real costs reviewer attention and trust;
- a missed defect gives false assurance that a change was checked;
- confidence language is what humans actually act on, and it may not track
  correctness at all.

WebFixBench is built around those failure modes rather than around patch
success rates.

## Research question

> How reliably do current LLM reviewers identify defects in web-application
> diffs, and how do detection quality, false-positive rate and confidence vary
> across defect categories and frameworks?

v0.1 can only speak to the PHP web ecosystem. It makes no claim about other
languages, and a 15-case synthetic suite cannot establish general model
capability.

## Scope

**v0.1 = the PHP web ecosystem only**, through a single suite, `php-web-v0.1`.
The engine is language-agnostic; other ecosystems are roadmap items, and this
repository deliberately ships no placeholder directories for them.

## What it measures

| Signal | How |
| --- | --- |
| Detection | true positives / false negatives against per-case labelled ground truth |
| False positives | findings that match no label, plus a dedicated clean-control false-alarm rate |
| Structural reliability | responses that fail the output schema, counted as malformed and never scored as correct |
| Confidence | per-finding and overall confidence, stored and summarised, including mean confidence on true vs. false positives |
| Cost and latency | wall-clock latency and provider-reported token usage; cost only when you supply a pricing table |
| Ecosystem differences | metrics broken down by PHP / Laravel / WordPress and by defect category |

## Ground truth

> **Ground truth is frozen before any model is evaluated.**

Cases are authored or accepted by a human maintainer. Model outputs are never
used as ground truth. LLMs may draft fixtures; labels are frozen before
evaluation. Evaluation begins only after the expected findings for a case have
been finalized.

This is enforced, not just stated: every case records `label_source`,
`label_status` and `reviewed_by`, and the validator rejects a case that claims
frozen status without a human label source and a named reviewer. Runs against
unfrozen labels are marked provisional in the CLI output, the evaluation
document and the report.

**All fifteen v0.1 cases are `frozen`** after explicit review and acceptance by
maintainer Oleksii Siniaiev. The three advisory-derived cases use
`public_advisory_plus_human_review`; the other twelve use `human_reviewed`.
No case received separate academic review. The rules and preserved decision
packet are in [docs/ANNOTATION.md](docs/ANNOTATION.md) and
[docs/HUMAN_REVIEW_PACKET.md](docs/HUMAN_REVIEW_PACKET.md).

## Why clean controls

Four of the fifteen cases contain no defect at all, and the correct review of
them is silence. Without clean controls, a reviewer can post a high recall
score simply by reporting vulnerabilities on every diff — the benchmark would
reward exactly the behaviour that makes review tooling unusable. Clean controls
are what make that strategy cost something, and they are chosen to be tempting:
code that touches authorisation, `$_POST` or SQL and is nevertheless correct.

## Current suite

`php-web-v0.1` — 15 cases (suite revision 0.1.2):

| | Laravel | WordPress | PHP | Total |
| --- | --- | --- | --- | --- |
| With a labelled defect | 6 | 3 | 2 | 11 |
| Clean controls | 2 | 1 | 1 | 4 |

Defect categories in use: `authorization` (3), `injection` (3), `xss` (3),
`secrets` (1), `unsafe_deserialization` (1).

All case code is synthetic and written for this benchmark: twelve fixtures are
original synthetic examples and three are advisory-derived synthetic
reconstructions of patterns from two inspected Laravel advisories. These are
not vendored real-world patches or independent incident samples. Synthetic
fixtures isolate one defect at a time, fix exactly what the reviewer may assume,
and make false-positive measurement reproducible. They do not establish
real-world validity. See
[docs/DATASET.md](docs/DATASET.md) and
[docs/REAL_WORLD_SOURCES.md](docs/REAL_WORLD_SOURCES.md).

## Quick start

Python 3.9+ and no dependencies:

```bash
git clone https://github.com/lex127/webfixbench.git
cd webfixbench
pip install -e .

webfixbench list
webfixbench show laravel-authz-001
```

You can also run it straight from a checkout without installing:

```bash
PYTHONPATH=src python -m webfixbench.cli list
```

## Running with the mock provider

The `mock` provider is a deterministic rule-based stub. It exists so the whole
pipeline can be exercised offline; **it is not a model, and its scores say
nothing about any model's review quality.**

```bash
webfixbench run --provider mock --out results/my-run.json
webfixbench evaluate results/my-run.json
webfixbench report results/my-run.json --out results/my-run.md
```

A committed example of that output is in
[results/mock-baseline.md](results/mock-baseline.md).

## Running with hosted providers

```bash
cp .env.example .env     # then export the key you need

export OPENAI_API_KEY=...
webfixbench run --provider openai --model <model-id> --limit 2 --out results/openai-smoke.json

export ANTHROPIC_API_KEY=...
webfixbench run --provider anthropic --model <model-id> --limit 2 --out results/anthropic-smoke.json

export XAI_API_KEY=...
webfixbench run --provider xai --model <model-id> --limit 2 --out results/xai-smoke.json

export DEEPSEEK_API_KEY=...
webfixbench run --provider deepseek --model <model-id> --reasoning-effort none \
  --output-constraint json_object --limit 2 --out results/deepseek-smoke.json

export GEMINI_API_KEY=...
webfixbench run --provider gemini --model <model-id> --reasoning-effort low \
  --output-constraint json_schema --limit 2 --out results/gemini-smoke.json
```

Notes:

- `--model` is required. The CLI selects no paid default; a run records the
  requested ID and the provider-returned ID when supplied. The checked-in first
  wave records IDs verified for that protocol.
- OpenAI defaults to the Responses API; `--api-type chat.completions` selects
  Chat Completions explicitly. Use `prompt_only` only when a selected model lacks structured
  output support, and do not compare malformed-output rates across different
  constraint modes.
- Fable models are excluded by project policy.
- Keys are read from the environment only, and are never written to result
  files. `.env` is git-ignored and is not loaded automatically.
- Start with `--limit`. A full 15-case run is 15 requests.
- Cost is reported as `null` unless you pass `--pricing` with your own table
  (see [config/pricing.sample.json](config/pricing.sample.json)); the project
  ships no vendor prices, because stale prices produce wrong numbers.
- The test suite never contacts a paid API.

Repeatable multi-model/repetition runs use strict JSON experiment files. See
[docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) for dry runs, the pending-label smoke
boundary, result layout, current vendor documentation, and manual Actions runs.

## Dataset

15 synthetic unified diffs, including three advisory-derived reconstructions,
with explicit frozen labels and four clean controls whose correct review is "no findings". Case format and the full case
table: [docs/DATASET.md](docs/DATASET.md). How labels are written, reviewed and
frozen: [docs/ANNOTATION.md](docs/ANNOTATION.md). Machine-readable schemas:
[schema/](schema/).

## Metrics

Finding-level precision, recall and F1; clean-control false-alarm rate; case-level
detection rate; malformed-response count; latency; token usage; optional cost;
confidence summaries including the gap between mean confidence on true and on
false positives.

Two things v0.1 deliberately does **not** do:

- **No calibration score.** Confidence is stored, but Brier/ECE need
  well-defined event semantics that a single self-reported number does not
  have. Reported as *not yet measured*.
- **No LLM judge.** Matching is deterministic (normalised category, optionally
  file), so every scored true positive can be re-derived by hand from a result
  file. The cost of that choice is documented in
  [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Reproducibility

- Prompts are versioned files (current: `prompts/review_v3.txt`); every run records the
  prompt id and the SHA-256 of the exact text used.
- Runs record suite version, provider, requested and returned model IDs,
  settings actually sent, model-ID stability, and provider-reported usage.
- Running and scoring are separate steps, so one (paid) run can be re-scored
  under different matching rules without calling a model again.
- Sampling parameters are omitted by default. An explicit temperature is sent
  only when the selected provider/configuration supports it. Neither omission
  nor temperature zero guarantees deterministic model output; the mock provider
  is deterministic.

## Limitations

- 15 cases. Small: any per-category number rests on one to three cases.
- Labels were reviewed by one maintainer. Inter-rater agreement and independent
  academic per-case review are not measured.
- Synthetic cases are cleaner than real pull requests, and say nothing about
  real-world validity.
- One defect per defective case, and diff-only context. Real review has
  repository context and interacting defects.
- Category-level matching can credit a finding that names the right category
  for the wrong reason.
- Synthetic cases written in 2026 may resemble patterns in model training data;
  contamination is not controlled for.
- No model results are published in this release — **not yet measured**.

## Related work

Comparison with SWE-bench, SEC-bench, SecCodeBench, the Martian code review
benchmark and SEVRA-BENCH is in
[docs/RELATED_WORK.md](docs/RELATED_WORK.md), together with an explicit note on
which entries have been verified against primary sources and which have not.
WebFixBench complements existing benchmarks by focusing its first suite on
labelled PHP web-application diffs, clean controls, false-positive measurement
and explicit model confidence.

## Roadmap

[docs/ROADMAP.md](docs/ROADMAP.md).

## Contributors

**Oleksii Siniaiev** — Technical Lead and Maintainer
<https://alexsinyaev.com/>

**Valeriia Chumak** — Academic Collaborator, Evaluation Design and Research Framing
Senior Lecturer, Department of Media Engineering and Information Radioelectronic
Systems, Kharkiv National University of Radio Electronics
<https://nure.ua/staff/valerija-sergiivna-chumak>

Contributions are welcome: [CONTRIBUTING.md](CONTRIBUTING.md).

## Ethics and licence

Ethical boundaries of the project — no client code, no live exploitation, no
zero-day collection, and what this benchmark must not be used to certify — are
in [docs/ETHICS.md](docs/ETHICS.md).

Code and dataset: Apache-2.0 ([LICENSE](LICENSE), [NOTICE](NOTICE)).
