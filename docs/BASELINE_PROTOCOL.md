# v0.1 baseline protocol

This protocol compares review behaviour under a shared task while preserving
the real differences among vendor APIs. It does not pretend that identically
named controls create equivalent computation.

## Fixed experimental boundary

- Exact `review_v3` prompt and exact case description, context and diff.
- One request per case and one repetition in the first wave.
- No tools, search, grounding, agent loop, repository retrieval or hidden
  WebFixBench context.
- Native structured output where documented; the constraint mechanism is
  recorded and disclosed when results are compared.
- Lowest or disabled reasoning level that the provider explicitly supports.
- No sampling parameter by default. Temperature zero is not deterministic.
- Requested/returned model IDs, actual settings, prompt/case hashes, UTC time,
  usage and latency are preserved.

## Initial provider matrix

| Provider | Model ID | API / JSON constraint | Baseline reasoning | Sampling | ID stability | Usage and limitation |
| --- | --- | --- | --- | --- | --- | --- |
| Anthropic | `claude-sonnet-5` | Messages / `output_config.format` | thinking `disabled` | omitted; Sonnet 5 rejects non-default sampling | pinned dateless ID | input/output/cache tokens; no manual extended thinking on Sonnet 5 |
| OpenAI | `gpt-5.6-terra` | Responses / `text.format` | `none` | omitted | stable alias | input/output/cache/reasoning details when returned |
| Google | `gemini-3.8-flash` | GenerateContent / `responseJsonSchema` | `low` (cannot disable) | omitted | stable alias; record `modelVersion` | prompt/candidate/cache/thought counts when returned |
| DeepSeek | `deepseek-flash` | Chat Completions / JSON object | `none` | omitted | mutable alias for current V4.1 Flash | prompt/completion/cache details; no immutable ID documented |
| xAI | `grok-4.6` | Responses / `text.format` | `low` (cannot disable) | omitted | mutable alias; dated IDs may exist | input/output/cache/reasoning details when returned |

The checked-in configurations are
[`v0.1-first-wave.json`](../experiments/v0.1-first-wave.json) and its enforced
three-case smoke variant. They contain no credentials and have not been run.

## Official API references checked 2026-09-20

- [Anthropic models](https://platform.claude.com/docs/en/about-claude/models/overview), [thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking), and [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [OpenAI GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) and [Responses](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Gemini models](https://ai.google.dev/gemini-api/docs/models), [thinking](https://ai.google.dev/gemini-api/docs/thinking), and [structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [DeepSeek models](https://api-docs.deepseek.com/quick_start/pricing), [thinking](https://api-docs.deepseek.com/guides/thinking_mode), and [JSON output](https://api-docs.deepseek.com/guides/json_mode)
- [xAI models and aliases](https://docs.x.ai/developers/models), [reasoning](https://docs.x.ai/developers/model-capabilities/text/reasoning), and [structured outputs](https://docs.x.ai/developers/model-capabilities/text/structured-outputs)

Vendor documentation and aliases can change. Recheck them immediately before a
paid wave and preserve the returned model identifier whenever supplied.
