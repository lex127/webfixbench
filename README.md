# WebFixBench

WebFixBench is a reproducible benchmark for evaluating the reliability of
LLM-assisted code review on web-application changes.

WebFixBench v0.1 reports a PHP web ecosystem baseline covering PHP, Laravel and
WordPress. It is an early research skeleton: a working evaluation harness and a
small, carefully labelled dataset — not a finished study. No model results are
published yet.

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
languages, and a 12-case synthetic suite cannot establish general model
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

**All twelve v0.1 cases are currently `pending_review`** — drafted and awaiting
the maintainer's review pass. The rules are in
[docs/ANNOTATION.md](docs/ANNOTATION.md).

## Why clean controls

Three of the twelve cases contain no defect at all, and the correct review of
them is silence. Without clean controls, a reviewer can post a high recall
score simply by reporting vulnerabilities on every diff — the benchmark would
reward exactly the behaviour that makes review tooling unusable. Clean controls
are what make that strategy cost something, and they are chosen to be tempting:
code that touches authorisation, `$_POST` or SQL and is nevertheless correct.

## Current suite

`php-web-v0.1` — 12 cases:

| | Laravel | WordPress | PHP | Total |
| --- | --- | --- | --- | --- |
| With a labelled defect | 4 | 3 | 2 | 9 |
| Clean controls | 1 | 1 | 1 | 3 |

Defect categories in use: `authorization` (3), `injection` (2), `xss` (2),
`secrets` (1), `unsafe_deserialization` (1).

All cases are synthetic, written for this benchmark. That is a design choice:
synthetic fixtures isolate one defect at a time, fix exactly what the reviewer
is allowed to assume, and make false-positive measurement reproducible against
controls known to be clean. They do not establish real-world validity, and no
claim of it is made. Advisory-derived cases are the next expansion — see
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

## Running with OpenAI / Anthropic

```bash
cp .env.example .env     # then export the key you need

export OPENAI_API_KEY=...
webfixbench run --provider openai --model <model-id> --limit 2 --out results/openai-smoke.json

export ANTHROPIC_API_KEY=...
webfixbench run --provider anthropic --model <model-id> --limit 2 --out results/anthropic-smoke.json
```

Notes:

- `--model` is required. WebFixBench pins no vendor model ids, so a run always
  records exactly which model produced it.
- Keys are read from the environment only, and are never written to result
  files. `.env` is git-ignored.
- Start with `--limit`. A full 12-case run is 12 requests.
- Cost is reported as `null` unless you pass `--pricing` with your own table
  (see [config/pricing.sample.json](config/pricing.sample.json)); the project
  ships no vendor prices, because stale prices produce wrong numbers.
- The test suite never contacts a paid API.

## Dataset

12 synthetic unified diffs with explicit ground truth, including three clean
controls whose correct review is "no findings". Case format and the full case
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

- Prompts are versioned files (current: `prompts/review_v2.txt`); every run records the
  prompt id and the SHA-256 of the exact text used.
- Runs record suite version, provider, model, temperature and token usage.
- Running and scoring are separate steps, so one (paid) run can be re-scored
  under different matching rules without calling a model again.
- Default temperature is 0.0. Model output is still not guaranteed to be
  deterministic; the mock provider is.

## Limitations

- 12 cases. Small: any per-category number rests on one to three cases.
- Labels are drafted and awaiting human review; results from them are
  provisional until frozen.
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
