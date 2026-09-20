# Results

## What is committed here

| File | What it is |
| --- | --- |
| `mock-baseline.json` | A full 15-case run of the `mock` provider — raw output plus run metadata |
| `mock-baseline.md` | The rendered report for that run |

**No model results are published in this release.** The only committed run uses
the mock provider.

The run is also **provisional** in the project's own terms: all fifteen cases
are `pending_review`, so the labels it was scored against are not yet frozen.
The report says so at the top, and the evaluation document records how many
cases are frozen. See [../docs/ANNOTATION.md](../docs/ANNOTATION.md).

## Reading the mock baseline

The `mock` provider is a deterministic rule-based stub, not a language model.
It matches a handful of regular expressions against added and removed diff
lines and emits a fixed distractor finding on a subset of cases.

Its numbers exist so that the metrics pipeline can be seen working on a run
that is neither perfect nor empty. **They are not a model result and must not
be quoted as one.** The stub scores 8 true positives, 4 false positives and 3
false negatives on this suite because it was written to be fallible — that is a
property of the fixture, not a finding about anything.

## Reproducing it

```bash
webfixbench run --provider mock --out results/mock-baseline.json --quiet
webfixbench report results/mock-baseline.json --out results/mock-baseline.md
```

The predictions are byte-identical on every run: mock output depends only on
the prompt text and the case id. Two fields do change — `run_id` and
`created_at` — so a regenerated baseline will show a small diff even when the
scores are unchanged.

## Adding a real run

```bash
export OPENAI_API_KEY=...        # or ANTHROPIC_API_KEY
webfixbench run --provider openai --model <model-id> --limit 2 \
  --out results/openai-<model>-smoke.json
webfixbench evaluate results/openai-<model>-smoke.json --out results/openai-<model>-smoke.eval.json
webfixbench report  results/openai-<model>-smoke.json --out results/openai-<model>-smoke.md
```

Before committing a real run:

- check the file for anything that should not be public (it stores raw model
  output verbatim);
- state the model id, the prompt version and the number of cases anywhere the
  numbers are quoted;
- do not present a single run of a handful of cases as a model evaluation. Say
  what it is: a smoke test.

Files matching `results/*.local.json` are git-ignored, for runs you do not want
to publish.

## Result file layout

```
webfixbench_version      package version that produced the file
results_format_version   bumped on incompatible layout changes
run.run_id               random id for this run
run.created_at           UTC timestamp
run.suite                suite id, version, case count
run.cases_run            case ids, in execution order
run.prompt               prompt id and SHA-256 of the exact prompt text
run.provider             provider, API type/endpoint, model, output constraint,
                         temperature and max output tokens
run.pricing              pricing table metadata, or null
responses[]              per case: valid, raw, parsed, validation_errors,
                         error, latency_ms, usage, cost_usd
```

Scoring is not stored in a result file. Run `webfixbench evaluate` to produce
an evaluation document, which records the match mode it used — the same run can
be re-scored under different matching rules without calling a model again.
