# Roadmap

Dated plans are avoided: this is a small project run alongside other work, and
a schedule would be a guess. The ordering below is real; the timing is not
promised.

## Before v0.1 is considered publishable

These are blockers, not enhancements:

- [ ] **Freeze the ground truth.** All twelve cases are `pending_review`. The
      maintainer reviews each one against the checklist in
      [HUMAN_REVIEW_CHECKLIST.md](HUMAN_REVIEW_CHECKLIST.md), writes or approves the expected findings,
      and sets `label_status: "frozen"` with `reviewed_by` filled in. No model
      evaluation is published before this is done.
- [ ] Academic review of the taxonomy, the annotation rules, the methodology
      and two to three representative cases; set `academic_review: true` on
      exactly those cases
- [x] Complete the related-work verification pass and replace every `unclear`
      in [RELATED_WORK.md](RELATED_WORK.md) with a primary-source fact — or with
      a confirmed "not stated by the source"
- [x] Re-check whether the project's stated contribution survives that pass, and
      revise the positioning if it does not
- [ ] A small real-model smoke run (2–3 cases per provider) to confirm the
      providers work end to end against live APIs
- [ ] A second reader over the twelve cases, to catch labels that are less
      obvious than the maintainer thinks

## v0.2 — a dataset worth drawing conclusions from

- Grow `php-web-v0.1` to a size where per-category numbers mean something
- A first real-world expansion, provisionally `php-web-real-v0.1`: 5–10
  advisory-derived cases, each with source, licence and modifications recorded,
  following the research plan in
  [REAL_WORLD_SOURCES.md](REAL_WORLD_SOURCES.md) — not a bulk CVE import
- Multi-finding cases, so prioritisation and interacting defects are testable
- Harder cases: defects that need framework knowledge rather than pattern
  recognition, and near-miss clean controls
- A second labeller and a reported inter-rater agreement figure
- First published model results, with run-to-run variance rather than a single
  run per model

## v0.3 — confidence and context

- **Calibration.** Redesign the prompt so confidence has well-defined event
  semantics, then report Brier score and ECE properly. Until then the fields
  stay `null` and the answer stays *not yet measured*.
- **Context levels.** Hold the defect fixed and vary what the reviewer sees:
  diff only, diff plus the full changed file, diff plus repository context.
  This is the experiment the case format was designed for.
- Optional LLM-as-judge scoring reported *alongside* deterministic matching,
  never replacing it, with the disagreement between the two reported as a
  result in its own right.

## Later

- A JavaScript/TypeScript web suite
- A Python web suite
- Contributor-created ecosystem packs, with a documented suite contract
- Cross-framework defect pairs: the same defect expressed in two ecosystems, to
  separate "knows the defect" from "knows the framework"
- Cost- and latency-aware comparisons, once pricing metadata is routinely
  supplied with runs

No suite for a future ecosystem exists in this repository, and none will be
created before there are cases to put in it.

## Explicit non-goals

- Becoming a security scanner, a linter, or a CI gate
- Certifying models, tools or products as safe
- Leaderboard-driven development
- Growing case count at the expense of label quality
