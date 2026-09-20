# WebFixBench agent rules

Technical lead and maintainer: Oleksii Siniaiev.
Continue this repository; do not restart it or redesign the engine.
Use the latest main and the task's requested branch. Preserve unrelated worktrees.

## Before changing cases
- Read README.md, docs/ANNOTATION.md, docs/METHODOLOGY.md, docs/DATASET.md,
  docs/REAL_WORLD_SOURCES.md and docs/HUMAN_REVIEW_CHECKLIST.md.
- Read schema/case.schema.json, the suite manifest, 2-3 existing cases,
  src/webfixbench/matching.py and the current versioned reviewer prompt.
- Write a task-specific PLAN.md of at most 40 lines, then implement in the same
  session. Do not wait for chat approval unless there is a hard blocker.
- For each inspected source record USE/SKIP, actual patch file/line counts,
  dominant defect_type, license and reconstruction plan or rejection reason.
- Read both the public advisory and the actual upstream fix commit/PR.
  Count all changed files/lines yourself, including tests; do not trust summaries.
- Prefer 1-2 files and roughly <=80 changed lines with one dominant defect.
  Skip patches that do not fit; never force a case from a complex real patch.

## Drafting and provenance
- Prefer 2-4 small, self-contained synthetic_reconstruction cases per slice.
  Reconstruct the pattern in new code; do not vendor framework trees.
- Include a clean_control sibling when cheap; its expected_findings must be [].
- For advisory cases record source_type public_advisory, advisory_id, source_url,
  original_project, reconstruction_type and license_note; link the exact fix.
- Preserve upstream attribution and license facts; do not assume Apache-2.0
  covers copied third-party material. Prefer independent synthetic code.
- One primary defect_type per defective case; use existing types or document
  at most one necessary new type for the slice. Do not conflate mechanisms.
- Every runtime/security assumption needed to decide the label belongs in context.
- New drafts: label_status pending_review, label_source agent_drafted,
  reviewed_by [], academic_review false. NEVER freeze labels or invent reviews.
- Only Oleksii may record his manual approval in the human-review checklist.
- Keep labels, notes and provenance out of model prompts. No LLM-as-judge.
- Prompts are immutable once versioned; append a new version when wording changes.

## Source boundaries
- For this GHSA slice the mandatory inspected sources are GHSA-546h-56qp-8jmw
  (Laravel 45287fb2a91c69bb1c110539b9b7341faf5aee33), GHSA-c7r6-vx3h-w5g2
  (Laravel-Excel Disk::copy), and GHSA-qg7r-fjh2-wvx8 (WordPress wpautop).
- Optional only after inspection: GHSA-gv7v-rgg6-548h, GHSA-w9mx-xmg4-gc4r,
  GHSA-3pwp-g2mj-5p3v. Retain USE/SKIP evidence in REAL_WORLD_SOURCES.md.
- Skip GHSA-crmm signed-URL multi-PR and GHSA-52p2 login XSS-to-RCE chain.
- Do not treat mahdi-salmanzade/laravel-vuln-lab or
  appelsiini/vulnerable-laravel-app as real ground truth.
- Skip Wordfence-only plugin advisories without a public upstream fix.
- No exploits, malicious ZIPs, paid API calls, private/client code or credentials.

## Completion
- Update suite.json (count and version), DATASET.md, HUMAN_REVIEW_CHECKLIST.md
  and REAL_WORLD_SOURCES.md, including rejected candidates and reasons.
- Keep JSON Schema and Python validation in sync; add meaningful offline tests.
- If suite or matching changes, regenerate and verify the committed mock baseline.
  Never tune cases or mock rules just to improve its score.
- Run `PYTHONPATH=src python3 -m unittest discover -s tests -t .` and applicable
  CI checks, including `python3 scripts/check_baseline.py`.
- Use focused commits. No Co-Authored-By Claude trailers.
- When requested, push and open a PR to main; do not merge it.
- Keep this file <=80 lines; no duplicate CLAUDE.md unless genuinely necessary.
