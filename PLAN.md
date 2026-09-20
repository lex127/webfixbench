# Multi-provider experiment slice

1. Keep the dependency-free provider boundary and add dedicated `xai` and
   `deepseek` modules with fixed official endpoints and environment keys.
2. Use xAI Responses (`/v1/responses`) and DeepSeek Chat Completions
   (`/chat/completions`); shape and parse each payload independently.
3. Support only documented constraint modes: xAI schema/object/prompt and
   DeepSeek object/prompt; reject unsupported combinations before requests.
4. Preserve vendor usage breakdowns (reasoning/cache) while treating vendor
   totals as authoritative and never synthesising missing metadata.
5. Redact configured secrets from transport/provider errors and keep raw model
   text when model-response parsing fails.
6. Add strict JSON experiment validation with no unknown fields, explicit
   models/key-variable names, safe IDs, bounded values, and provider settings.
7. Add `experiment CONFIG` with dry-run, request guard, reviewed-label gate,
   and an explicit paid smoke mode limited to at most three cases.
8. Preflight every provider/config/case before any request, then use the current
   runner, evaluator, and report renderer for each provider/model/repetition.
9. Write a unique experiment directory and incremental manifest; store each
   run's raw results, optional evaluation, report, status, and links separately.
10. Record Git state, prompt/suite identity, exact case fingerprints, requested
    and returned models, actual provider settings, latency, usage, and errors.
11. Add mock-only example config and a manual-only Actions workflow with secrets,
    request limits, concurrency, failure-safe artifact upload, and job summary.
12. Document credentials, environment behavior, model/settings selection,
    smoke/reviewed boundaries, output layout, artifact retention, and archiving.
13. Add offline HTTP/provider/config/execution tests, including failures,
    no-overwrite behavior, partial preservation, redaction, and request counts.
14. Run unittest, pytest, baseline, CLI validation/dry-run/mock execution, and
    workflow syntax checks available locally; make focused commits and open PR.
