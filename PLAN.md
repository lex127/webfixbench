# Real GHSA draft slice

Base: `520d433` (latest main inspected 2026-09-20); branch `oleksii/real-ghsa-drafts`.
Read README, annotation/methodology/dataset/source/review docs, schemas, three cases,
matching.py and review_v2. Keep the existing engine and deterministic matching.
Counts below were counted from every +/- line in the full upstream commit patches,
including tests, and cross-checked against GitHub file stats; no vendored sources.

## Inspected candidates
| Decision | Advisory / actual fix | Files; added/deleted | Dominant mechanism / defect_type | License | Reconstruction plan / reason |
| --- | --- | --- | --- | --- | --- |
| USE | GHSA-546h-56qp-8jmw / laravel/framework `45287fb2a91c69bb1c110539b9b7341faf5aee33` | 1; +2/-2 | `xss_unescaped_output` | MIT (Taylor Otwell) | New tiny debug Blade view; regress request-body escaping, omit upstream layout and second sink. |
| SKIP | GHSA-c7r6-vx3h-w5g2 / SpartnerNL/Laravel-Excel `b5cafdfcf7ec63924e83303763be8fcae340f70b` | 4; +133/-22 | filesystem-root bypass (outside current types) | MIT (Spartner) | Full fix also changes cleanup/remote copy and truncation behaviour; exceeds small one-defect gate. No case. |
| SKIP | GHSA-qg7r-fjh2-wvx8 / WordPress/wordpress-develop `95a9b738f2995588852ca5be193102816a6a691c` (r63665) | 1; +1/-1 | XSS via unsafe HTML mutation (not ordinary unescaped output) | GPL-2.0-or-later (WordPress contributors) | Read official repository advisory and surrounding wpautop pipeline; quote-aware blockquote fix depends on paragraph/filter composition. Cannot justify equivalent tiny standalone XSS fixture without that pipeline; no forced case. |
| USE | GHSA-gv7v-rgg6-548h / laravel/framework `18b326d22d831e1fe05e737209e367e30796d5f3` | 1; +3/-1 | `environment_override_from_web_argv` (new, injection) | MIT (Taylor Otwell) | New local function with explicit SAPI/argv inputs; remove console guard. Add guarded clean sibling. |
| SKIP | GHSA-w9mx-xmg4-gc4r / stefanzweifel/laravel-backup-restore `a73f6c3dfd57c5efbc46cce4e93ed033bedce8b0` | 12; +221/-11 | shell-command injection (outside current types) | MIT (Stefan Zweifel) | Multiple database importers plus archive traversal validation; too broad, no archive or case. |
| SKIP | GHSA-3pwp-g2mj-5p3v / WordPress/WordPress-Coding-Standards `a29048d0bbef5cf25d42349c74e4072d3cbc8325` | 3; +122/-102 | eval/code injection (outside current types) | MIT (John Godley and contributors) | Replaces token evaluator across sniff/tests; exceeds size gate, no case. |

## Implement in this session
1. Add short root AGENTS.md (<=80 lines); no CLAUDE.md duplicate.
2. Add conditional public-advisory provenance fields to JSON/Python case schema,
   preserve them on round-trip, and keep them out of reviewer prompts.
3. Add exactly three synthetic_reconstruction drafts, two defects and one control.
   All remain agent_drafted / pending_review / reviewed_by [] / academic_review false.
4. Add one configuration-injection mechanism, not a broad SQL alias; append review_v3
   and select it by default without editing frozen v1/v2 prompts or matching logic.
5. Bump suite revision to 0.1.1 (15 cases), update dataset/source/checklist docs and
   related counts/taxonomy references; record exact upstream and license links.
6. Add offline provenance, taxonomy and fixture-integrity tests; regenerate mock
   baseline without tuning mock rules or calling any paid provider.
7. Verify `PYTHONPATH=src python3 -m unittest discover -s tests -t .`, available
   pytest/schema checks, CLI validation and scripts/check_baseline.py.
8. Make focused commits; push branch and open PR to main. Do not merge.

Explicit exclusions: GHSA-crmm signed-URL multi-PR, GHSA-52p2 XSS-to-RCE chain,
educational vulnerable apps as real GT, Wordfence-only reports without public fixes,
large framework copies, exploits, malicious ZIPs, paid APIs, LLM judges, label freezing,
and Claude co-author trailers. Full source links and selection evidence go in docs.
