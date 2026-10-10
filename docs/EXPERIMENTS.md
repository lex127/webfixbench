# Reproducible experiments

WebFixBench supports `mock`, `openai`, `anthropic`, `gemini`, `xai`, and
`deepseek` as distinct providers. Obtain credentials from the official [OpenAI API keys],
[Anthropic API keys], [Gemini API keys], [xAI API keys], or [DeepSeek API platform] pages. Export
only the key you need:

```bash
export OPENAI_API_KEY='...'
export ANTHROPIC_API_KEY='...'
export XAI_API_KEY='...'
export DEEPSEEK_API_KEY='...'
export GEMINI_API_KEY='...'
```

The CLI reads the process environment. It does **not** load `.env` automatically.
If you copy `.env.example` to `.env`, load it with your shell or another tool;
never commit it.

## Experiment JSON

Start with [`experiments/mock-example.json`](../experiments/mock-example.json).
Every provider entry needs an explicit model. For a paid provider it must also
name its fixed credential variable, for example:

```json
{
  "provider": "xai",
  "model": "REPLACE_WITH_A_DOCUMENTED_MODEL_ID",
  "api_key_env": "XAI_API_KEY",
  "output_constraint": "json_schema",
  "reasoning_effort": "high"
}
```

The placeholder is deliberately not a claimed model ID; replace it using the
vendor's current [OpenAI models], [Anthropic models], [Gemini models], [xAI models], or
[DeepSeek models] documentation. OpenAI accepts `responses` or
`chat.completions` as `api_type`. Anthropic and xAI support `json_schema` or
`prompt_only` (xAI also supports `json_object`). DeepSeek supports
`json_object` or `prompt_only` and requires explicit `reasoning_effort`:
`none`, `low`, `high`, or `max`. DeepSeek temperature is accepted only with
`none`, because its thinking mode documents temperature as having no effect.
Gemini supports `json_schema`, `json_object`, or `prompt_only` and the current
3.8 Flash family supports `low`, `medium`, or `high` thinking, not disabled.
Anthropic supports explicit `disabled` or `adaptive` thinking; Sonnet 5 rejects
non-default sampling parameters.
Temperature and token-limit values do not represent equivalent reasoning
budgets across vendors.

Request shapes follow the official [OpenAI Responses API], [Anthropic Messages
API], [Gemini GenerateContent API], [xAI Responses API], and [DeepSeek Chat Completions API] references.

The reviewed five-provider wave is
[`v0.1-first-wave.json`](../experiments/v0.1-first-wave.json) (75 requests
while the sixteenth case remains pending review). Before that, use
[`v0.1-first-wave-canary.json`](../experiments/v0.1-first-wave-canary.json)
for one frozen case across all five providers (5 requests), then the explicit
three-case cross-framework smoke companion for 15 requests. The smoke cases are selected
by id rather than by suite order so Laravel, WordPress and PHP paths are all
exercised. See
[BASELINE_PROTOCOL.md](BASELINE_PROTOCOL.md) for the comparability boundary.

Validate selection without a network request:

```bash
webfixbench experiment experiments/mock-example.json --dry-run --max-requests 10
```

Run it locally:

```bash
webfixbench experiment experiments/mock-example.json --max-requests 10
```

Unknown fields, invalid combinations, unsafe IDs, missing cases/keys, and a
planned count above `--max-requests` fail before the first request. The request
guard is not a dollar budget. Transient 408/429/5xx and network timeout failures
are retried with bounded backoff; malformed model output is never retried.

If an invocation still records failed provider runs, retry only those runs
without paying for successful providers again:

```bash
webfixbench retry-failed results/experiments/<experiment>/<run>/manifest.json \
  --max-requests 20
```

The retry is written as a new invocation and links back to the source run; it
never overwrites the original evidence. Cost remains `null` unless a dated, sourced
pricing table supplies the relevant model prices.

Paid runs require all selected labels to be frozen. While labels await human
review, set `"mode": "smoke"`; paid smoke runs are limited to three cases,
marked provisional, and excluded from comparative ranking. Offline mock runs
remain available with pending labels. Pending labels cannot support final
benchmark claims because the expected answers have not received human review.

## Results

Each invocation creates
`results/experiments/<experiment-id>/<unique-run-id>/`. `manifest.json` records
the suite and prompt hashes, Git state, exact case fingerprints, request count,
mode, and links/status for every provider/model/repetition. Each run directory contains `results.json`, `evaluation.json`, and
`report.md`; the invocation root also contains `summary.md`, a descriptive
cross-provider table. Raw text is retained
when parsing fails. The manifest is updated after each run and existing run
directories are never overwritten.

Compare runs only when suite version, prompt hash, case fingerprints, output
constraint, and relevant model settings match. Raw output, exact inputs, and
settings are needed to audit malformed responses and distinguish model changes
from benchmark changes.

## Skill-condition API protocol

The optional `conditions` array compares instructions through the existing API
runner. See [`mock-skill-conditions.json`](../experiments/mock-skill-conditions.json):

```bash
PYTHONPATH=src python3 -m webfixbench.cli experiment \
  experiments/mock-skill-conditions.json --dry-run --max-requests 12
PYTHONPATH=src python3 -m webfixbench.cli experiment \
  experiments/mock-skill-conditions.json --max-requests 12
```

Each condition needs a unique `condition_id` and `kind`. `baseline` has no other
fields. `single_skill` and `generic_checklist` require a repository-relative
`path` and the lowercase SHA-256 of the **exact UTF-8 file bytes**. Paths resolve
relative to the benchmark data root, not the config file. Traversal and symlinks
outside that root are rejected. Digest mismatches fail even in dry-run, before
provider construction or requests. Text is pinned in memory before execution;
resources, Markdown links, commands and template placeholders inside it are
never loaded or executed. Review supplied instruction files for answer leakage:
the materializer is not a semantic ground-truth or secret scanner.

Baseline sends the original rendered prompt byte-for-byte. Other conditions
prepend their literal text in a `review-instructions` block. Providers remain
stateless API calls; no native agent or global profile is involved. This measures
forced instruction delivery, not skill selection or autonomous tool use.

The guard counts cases × provider configurations × conditions × repetitions.
With `schedule_seed`, execution shuffles condition order within provider blocks
and reverses it in the next repetition, balancing relative order across each pair.
The exact block schedule is recorded. Cases retain their selected order. Without
a seed, legacy fixed order is preserved. This is run-block counterbalancing, not
case-level randomization or isolation from provider-side caching. Every condition/repetition has a
separate result/evaluation directory, retaining raw output and `inputs.json`
with the exact delivered prompts. Input hashes are condition-specific. The
manifest snapshots instruction text and pins the original case fingerprints.
Condition-aware manifests use experiment format 2; legacy manifests remain
format 1. Result format 2 and evaluation format 1 remain compatible because each
result document still contains one response per distinct case.

Re-score a stored `results.json` using `evaluate` without calling a model.
The evaluator verifies recorded case fingerprints (including labels) before
scoring: changed ground truth fails rather than silently changing the answer.
Duplicate case responses are rejected. Keep the original suite available; it is
not archived inside the invocation. Legacy result documents without fingerprints
remain re-scoreable and are not represented as pinned replay.

`retry-failed` is an explicit new invocation: only saved provider-error responses
are selected, not successful or malformed responses. Exact provider settings,
condition, selected cases and original repetition are retained. The aggregate
retry manifest links separate recoverable attempts; original artifacts are never
overwritten. Selective retries are not valid comparative samples. A partial run
must be resumed before retrying its errors. Legacy pre-checkpoint manifests use
the older failed-run retry behavior. No automatic API retry is added.

### Resources, bundles and skill trees

`bundle` conditions require an ordered `skills` array. Each item uses `path` and
`sha256`; single skills and bundle items can additionally list `resources`
(ordered pinned UTF-8 files). Explicit resources are delivered literally after
the main text; Markdown links are never followed implicitly. Scripts are not
executed. An optional `tree_sha256` pins the full parent-directory inventory,
including undelivered/binary files, and rejects symlinks anywhere in that tree.
Explicit delivered resources must stay in the pinned tree. Keep configs outside
the tree to avoid self-referential hashes. Each snapshot records exact delivered
text/bytes, resource ordering, tree inventory and composite identity.

Compute the tree hash with `webfixbench.conditions.fingerprint_skill_tree` using
the skill directory and explicit benchmark root. See
[`mock-skill-protocol.json`](../experiments/mock-skill-protocol.json) for the full
offline example (24 requests). The demo grouping maps are assumptions for testing
statistics, not a human certification of independent defects.

### Recovery

Every run saves an empty result checkpoint before the first review and atomically
replaces it after every returned response, including errors and malformed output.
`experiment CONFIG --resume-dir INVOCATION --max-requests N` validates config,
HEAD, harness source, suite/prompt, labels, pricing, condition/input hashes and
ordered response prefixes before providers are constructed. Completed runs make
zero requests. Saved errors/malformed output are preserved without retry. The
request cap still covers the original plan; missing requests are a suffix of it.
`--dry-run` plans a new invocation and cannot be combined with resume.

An exclusive `.active` file prevents simultaneous execution/resume. Normal errors
and interrupts release it; after SIGKILL inspect its recorded PID before manually
removing a stale lock. Charged in-flight calls may be interrupted before returning
and checkpointing: resume is **not exactly-once billing**; check vendor usage.
Only invocations made by the recoverable runner can be resumed. Aggregate retry
roots are audit indexes; resume individual attempt invocations, not the index.

### Comparison and interpretation

`comparison.json` and the appended summary show operational coverage, errors
separately from malformed output, missing episodes, clean alarms, per-incident
detection, latency, reported tokens and known/unknown cost coverage. Unknown cost
is `n/a`, never zero. Partial known costs are subtotals, not full experiment spend.
Mock/smoke/provisional runs and selective retries explicitly prohibit rankings.

`incident_ids` and `cluster_ids`, when supplied, must cover exactly selected cases.
Variants/repetitions average inside incident first. Paired detection deltas compare
conditions only within the same provider configuration. A seeded 2000-resample
percentile bootstrap resamples whole dependency clusters; absent explicit grouping
or fewer than two defective clusters disables its interval. Few clusters still
make intervals unreliable; no power/multiplicity or mechanism-review claim is
made. Invalid/error/missing episodes score zero in operational detection; valid-only
sensitivity and clean alarms show their different denominators alongside coverage.

Fixtures are illustrative, not validated production skills or token-matched
controls. Mock output proves mechanics, not real model benefit. Native agents,
repository/test-gap/plan/routing tracks and human-reviewed corpus expansion remain
separate milestones; this API protocol does not pretend to implement them.

## GitHub Actions

In repository **Settings → Secrets and variables → Actions**, add only the
secrets needed by the selected config: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, `XAI_API_KEY`, and/or `DEEPSEEK_API_KEY`. Run **Experiments (manual)** from the
Actions tab, choose a config committed under `experiments/`, and set a maximum
request count. The workflow exists only under `workflow_dispatch`; it never
runs paid APIs on pushes, pull requests, or schedules.

Download the `webfixbench-experiment-*` artifact from the completed workflow
run. Actions artifact retention is temporary and is not a research archive.
After checking raw output for sensitive material, deliberately archive a
selected run with `git add -f results/experiments/<experiment-id>/<run-id>` and
commit it in a reviewable pull request. The workflow never commits or pushes.

[OpenAI API keys]: https://platform.openai.com/api-keys
[Anthropic API keys]: https://console.anthropic.com/settings/keys
[xAI API keys]: https://console.x.ai/
[DeepSeek API platform]: https://platform.deepseek.com/api_keys
[Gemini API keys]: https://aistudio.google.com/app/apikey
[OpenAI models]: https://platform.openai.com/docs/models
[Anthropic models]: https://platform.claude.com/docs/en/about-claude/models/overview
[xAI models]: https://docs.x.ai/developers/models
[DeepSeek models]: https://api-docs.deepseek.com/quick_start/pricing
[Gemini models]: https://ai.google.dev/gemini-api/docs/models
[OpenAI Responses API]: https://platform.openai.com/docs/api-reference/responses/create
[Anthropic Messages API]: https://platform.claude.com/docs/en/api/messages/create
[xAI Responses API]: https://docs.x.ai/developers/rest-api-reference/inference/responses
[DeepSeek Chat Completions API]: https://api-docs.deepseek.com/api/create-chat-completion/
[Gemini GenerateContent API]: https://ai.google.dev/api/generate-content
