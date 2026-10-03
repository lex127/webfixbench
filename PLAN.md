# v0.1 release-candidate plan

1. Base work on merged PR #5 at `origin/main` and inventory the suite, labels,
   prompts, providers, schemas, result metadata, docs, workflows, and open PRs.
2. Resolve stale 12-case/all-synthetic claims from the actual 15-case suite;
   retain the advisory-derived synthetic reconstruction distinction.
3. Make sampling optional end to end: omission must mean omitted, and recorded
   `settings_sent` must match each vendor request exactly.
4. Align Anthropic with Sonnet 5: optional sampling, explicit disabled/adaptive
   thinking, effort validation, and no unsupported manual-thinking settings.
5. Align OpenAI reasoning with current GPT-5.6 values, including `none`, using
   Responses by default and preserving detailed usage/returned model IDs.
6. Document xAI alias/version behavior and lowest supported Grok 4.6 reasoning;
   send no tools, search, or realtime configuration.
7. Document DeepSeek `deepseek-flash` as a mutable V4.1 Flash alias and preserve
   requested/returned IDs, timestamps, endpoint, usage, and configuration.
8. Add a narrow first-party Gemini GenerateContent provider with official auth,
   schema output, explicit low reasoning, no tools/search, and mocked tests.
9. Extend experiment validation/schema, secrets, examples, result metadata, and
   manual workflow for Gemini without making provider requests.
10. Add a five-provider first-wave template with verified current IDs, explicit
    mutability notes, one repetition, and a 75-request full-run guard.
11. Define the fair baseline protocol and a provider-capability table, including
    structured-output and model-stability comparison boundaries.
12. Audit PR #5 failure recovery, fingerprints, manifests, redaction, and gates;
    fix correctness gaps and add regression tests rather than redesigning it.
13. Generate a complete per-case human review packet with ACCEPT/MODIFY/REMOVE
    recommendations; do not freeze any label before Oleksii explicitly approves.
14. Add concise SECURITY.md and CODE_OF_CONDUCT.md if the audit confirms they
    are absent; reconcile changelog, citation, release version, and OSS claims.
15. Run all offline unit/schema/CLI/baseline/workflow checks, make focused commits,
    push a reviewable PR, and leave tagging and paid experiments unexecuted.
