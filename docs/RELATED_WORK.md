# Related work

> **Verification status — read this first.**
>
> This file was drafted in a build environment with no network access, so **no
> entry below has been checked against its primary source yet**. Every factual
> cell is marked accordingly, and cells the maintainer could not state with
> confidence say `unclear` rather than being guessed.
>
> Consequences, stated plainly:
>
> - Do not cite this file as a literature review yet.
> - WebFixBench makes **no novelty claim**. Not "first", not "only", not "first
>   PHP benchmark". Whether related work already covers what this project does
>   is an open question until the checklist at the bottom is complete.
> - Completing that checklist is a release blocker for v0.1 (see
>   [ROADMAP.md](ROADMAP.md)).

## Position

Existing benchmarks cover complementary aspects of software engineering and
security evaluation. WebFixBench v0.1 narrows the scope to labelled PHP
web-application diffs and emphasises false positives, clean controls,
confidence, and reproducibility.

The distinction WebFixBench is *attempting* to draw is between **repair** and
**review**:

- repair benchmarks ask whether a model can produce a change that makes a test
  pass or a vulnerability disappear;
- WebFixBench asks whether a model, shown a change, correctly says what is
  wrong with it — and, just as importantly, says nothing when nothing is wrong.

Whether that distinction is already served by an existing benchmark is exactly
what the verification pass must establish.

## Comparison table

Columns describe **what WebFixBench needs to know about each project**, not a
ranking. `unclear` means the maintainer has not confirmed it from a primary
source.

| Benchmark | Primary task | Real-world changes | Diff/PR based | Ground truth | Clean controls | FP measurement | Confidence calibration | Security focus | PHP/Laravel/WordPress focus | Verified? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWE-bench | unclear (understood as: resolve a GitHub issue so tests pass) | unclear | unclear | unclear (understood as: test suites) | unclear | unclear | unclear | unclear | unclear | **no** |
| SEC-bench | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | **no** |
| SecCodeBench | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | **no** |
| Martian Code Review Benchmark | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | **no** |
| SEVRA-BENCH | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | unclear | **no** |
| **WebFixBench v0.1** | review a diff and report defects | no — synthetic | yes | hand-written labels per case | yes (3 of 12) | yes (finding-level FP + clean-control false-alarm rate) | no — confidence stored, calibration not yet measured | yes (5 defect categories) | yes (PHP, Laravel, WordPress) | n/a |

Only the WebFixBench row is a statement of fact the maintainer can back, because
it describes this repository.

## Notes on individual entries

Each entry records what the maintainer believes and flags it as unconfirmed. If
verification contradicts any of it, the entry is corrected, not quietly dropped.

### SWE-bench

Understood to evaluate whether language models can resolve real GitHub issues
in Python repositories, scored by whether the repository's own tests pass after
the model's patch. If that understanding holds, the difference from
WebFixBench is task-shaped: patch generation with execution-based ground truth,
versus review with labelled ground truth and no execution. **Unverified**;
primary source (project site, repository, paper) to be confirmed.

### SEC-bench

Understood to be a benchmark for LLM agents on real-world software security
tasks. If so, it is closer to WebFixBench in subject matter but is understood
to differ in unit of work (agentic security tasks versus single-diff review).
**Unverified**; the maintainer will not record a paper identifier here until it
is confirmed from the primary source, to avoid publishing a wrong citation.

### SecCodeBench

The maintainer cannot describe this project accurately from memory.
**Unverified, unclear.** To be filled in from the primary source.

### Martian Code Review Benchmark

Understood to be a code-review-focused evaluation, which makes it the closest
listed neighbour and the most important entry to verify carefully — including
whether it already measures false positives and clean controls, which are the
dimensions WebFixBench is built around. **Unverified, unclear.**

### SEVRA-BENCH

The maintainer cannot describe this project accurately from memory.
**Unverified, unclear.** To be filled in from the primary source.

## Also to be searched during verification

Beyond the five named projects, the verification pass covers:

- LLM code review benchmarks and AI code review evaluations generally
- security pull-request benchmarks
- LLM vulnerability review / detection benchmarks
- PHP security benchmarks for LLMs
- WordPress and Laravel specific LLM evaluations
- false-positive and calibration measurement in automated code review
  (including the pre-LLM static-analysis literature, where false-positive rate
  is a long-standing concern)

Primary sources only: official repositories, papers, and project sites. Blog
posts may point at a source but do not stand in for one.

## Verification checklist

For each project, before the `unclear` cells are replaced:

- [ ] Locate the primary source (official repository, paper, or project site)
- [ ] Record the exact title, authors, venue/date and canonical URL
- [ ] Confirm the primary task from the source, not from a summary of it
- [ ] Confirm the ground-truth mechanism
- [ ] Confirm whether clean / negative controls exist
- [ ] Confirm whether false positives are measured and how
- [ ] Confirm whether confidence or calibration is evaluated
- [ ] Confirm language and ecosystem coverage
- [ ] Record the date of verification next to the entry
- [ ] Re-examine whether WebFixBench still adds anything — and say so honestly
      in this file if it does not
