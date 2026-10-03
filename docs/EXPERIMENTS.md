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
[`v0.1-first-wave.json`](../experiments/v0.1-first-wave.json) (75 requests).
Its explicit three-case smoke companion plans 15 requests. See
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
guard is not a dollar budget. Cost remains `null` unless a dated, sourced
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
mode, and links/status for every provider/model/repetition. Each run directory
contains `results.json`, `evaluation.json`, and `report.md`. Raw text is retained
when parsing fails. The manifest is updated after each run and existing run
directories are never overwritten.

Compare runs only when suite version, prompt hash, case fingerprints, output
constraint, and relevant model settings match. Raw output, exact inputs, and
settings are needed to audit malformed responses and distinguish model changes
from benchmark changes.

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
