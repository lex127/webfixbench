# Contributing

Thanks for considering a contribution. The most valuable contributions to
WebFixBench are **good cases** and **honest criticism of the methodology** —
including "this label is wrong" and "this metric does not mean what you say it
means".

## Ground rules

- No client code, no private repository code, no credentials, no personal data,
  no undisclosed vulnerabilities. See [docs/ETHICS.md](docs/ETHICS.md).
- No inflated claims in documentation. If something has not been measured, the
  text says *not yet measured*.
- No fabricated numbers, citations or experiments.

By contributing you agree that your contribution is licensed under Apache-2.0,
the licence of this repository.

## Development setup

Python 3.9+. The package has no runtime dependencies.

```bash
git clone https://github.com/lex127/webfixbench.git
cd webfixbench
pip install -e ".[dev]"
pytest
```

Without installing anything:

```bash
python -m unittest discover -s tests -t .
```

The test suite never contacts a paid API, and a pull request that makes it do
so will not be merged.

## Contributing a benchmark case

Read [docs/ANNOTATION.md](docs/ANNOTATION.md) first — it is the annotation
standard, and it governs anything below.

The rule that overrides everything else: **ground truth is frozen before any
model is evaluated.** An LLM or agent may draft a fixture; a draft is not
ground truth. A human maintainer reviews the fixture, writes or approves
`expected_findings`, and only then is the label frozen. Submit new cases as
`label_source: "agent_drafted"` or `"human_authored"` with
`label_status: "pending_review"` and an empty `reviewed_by` — the maintainer
freezes them after review. A pull request that marks its own cases `frozen`
will be rejected by the validator.

A case earns its place by being *decidable*. Before opening a pull request:

1. **One defect**, from the fixed taxonomy: `authorization`, `injection`,
   `xss`, `secrets`, `unsafe_deserialization`. New categories need a separate
   discussion — subjective categories (style, performance, architecture) are
   out of scope.
2. **Objective ground truth.** A competent reviewer with the diff and the
   `context` paragraph should agree on the label without argument. If two
   reviewers could reasonably disagree, the case is not ready.
3. **Decidable from what is shown.** State in `context` any fact the reviewer
   must rely on (a policy exists, a cookie is unsigned, input is unfiltered).
   Do not require guessing about unseen files.
4. **Realistic.** A pattern that occurs in production work, not a puzzle.
5. **Synthetic, or properly sourced.** Synthetic is the default. Advisory- or
   repository-derived cases must record `source_type`, `source_url`, the
   original licence, the modifications made, and attribution.
6. **Clean controls are contributions too.** A dataset without them cannot
   measure false alarms. Near-miss controls — code that looks dangerous and is
   not — are especially welcome.

Then:

```bash
# add suites/php-web-v0.1/cases/<your-case-id>.json
webfixbench validate
webfixbench show <your-case-id>
webfixbench run --case <your-case-id> --provider mock --out /tmp/check.json --evaluate
pytest
```

Update `case_count` in `suites/php-web-v0.1/suite.json`, the composition tables
in [docs/DATASET.md](docs/DATASET.md), and the case counts asserted in
`tests/test_cases.py`. Note in the pull request why the label is unambiguous.

The mock provider's rule table is a test fixture, not a target. Do not tune a
case so the stub scores better on it.

## Contributing a provider

Subclass `BaseProvider`, implement `_review()`, and register the provider in
`src/webfixbench/providers/__init__.py`. Requirements:

- read credentials from environment variables only, and never write them into
  results;
- do not raise on remote failures — return a `ProviderResult` with `error` set,
  so one failing case does not discard a run;
- report token usage and latency when the API provides them;
- pin no default model id; require `--model`;
- add offline tests only. Payload shaping and error handling can be tested
  without a network call, and that is the level of coverage expected.

Nothing in `runner`, `evaluator` or `metrics` may import vendor code.

## Contributing to metrics or matching

Metric changes need a written justification of the semantics — what the number
means, what its denominator is, and when it is undefined. Two standing rules:

- a metric that cannot be computed returns `null`, never `0`;
- deterministic matching stays the primary scoring path. Anything model-based
  is reported alongside it, never instead of it.

## Documentation

Prose in this repository is meant to survive a sceptical reader. Prefer stating
a limitation to omitting it; prefer a denominator to a percentage on its own;
prefer *not yet measured* to an estimate.

## Pull requests

- Keep the change focused; separate a dataset change from an engine change.
- Run `pytest` and mention the result.
- Describe what you verified, not just what you wrote.
- Reviews are done by the maintainer and may take a while — this is a
  side-of-desk project.

## Reporting a problem with a case

Open an issue titled `case <id>: <problem>` and say what is ambiguous, wrong or
unrealistic. A well-argued "this label is wrong" is more useful than a new case.
