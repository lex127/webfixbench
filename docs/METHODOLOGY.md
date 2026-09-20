# Methodology

This document describes how WebFixBench v0.1 measures what it measures, and
where the measurement stops being trustworthy. It reflects the state of the
repository at v0.1: a harness and a small labelled dataset. No model results
are published yet.

## 1. Research question

> How reliably do current LLM reviewers identify defects in web-application
> diffs, and how do detection quality, false-positive rate and confidence vary
> across defect categories and frameworks?

Three sub-questions shape the design:

1. When a reviewer reports a defect, is the defect real? (precision, clean
   controls)
2. When a defect is present, is it reported? (recall, case-level detection)
3. Does the confidence attached to a finding carry information about whether
   the finding is correct? (confidence data; calibration is future work)

## 2. Why the PHP web ecosystem first

- PHP still runs a very large share of the public web, and WordPress and
  Laravel concentrate that traffic into two conventions-heavy ecosystems.
- Both frameworks make correctness depend on *framework-specific* obligations —
  a Laravel policy call, a WordPress capability check and nonce — which a
  reviewer must know rather than infer from the syntax. That makes them a
  useful probe for whether a reviewer understands the ecosystem or just
  pattern-matches on dangerous function names.
- The maintainer has production experience in these ecosystems, which is what
  makes hand-labelling defensible. Labels in an unfamiliar ecosystem would be
  weaker, not stronger, for being more numerous.

This is a starting point, not a claim that PHP is more important than other
ecosystems.

## 3. Case selection

Cases were chosen against four criteria:

1. **Objective ground truth.** A competent reviewer, given the diff and the
   stated context, should agree on the label without debate.
2. **Realism.** Each case reflects a defect pattern that occurs in production
   PHP work (a guard deleted during a refactor, a query builder replaced by
   string concatenation, a cookie format switched to `unserialize`).
3. **Decidable from the supplied context.** The reviewer must not need to guess
   about unseen files. Where surrounding facts matter, they are stated in the
   case's `context` field and included in the prompt.
4. **Reproducibility.** A fixed diff, fixed context, fixed labels.

Categories are restricted to five broad groups with objective ground truth:
`authorization`, `injection`, `xss`, `secrets`, `unsafe_deserialization`.
Subjective categories (style, readability, maintainability, architecture,
performance) are excluded from v0.1 — not because they do not matter, but
because their ground truth is a matter of opinion and would silently turn the
benchmark into a measure of taste agreement.

## 4. Synthetic case construction

All v0.1 cases are synthetic: written for this benchmark, inspired by defect
patterns that are common in the ecosystem. They contain no client code, no
private repository code and no third-party code.

Each case is a unified diff, as a reviewer would see it in a pull request, with
a short description and an explicit context paragraph that fixes the facts the
reviewer may rely on. Filenames, plugin names and identifiers are invented.

Synthetic fixtures are the right choice for v0.1, not a compromise forced on
it: they make it possible to isolate one defect at a time, to state exactly
what the reviewer is allowed to assume, and to measure false positives
reproducibly against controls that are known to be clean. None of that is
available when the ground truth has to be inferred from someone else's patch.

What they do not provide is real-world validity. Real pull requests are larger
and noisier, and the defect is rarely centred in the diff. The cases are
disclosed as synthetic everywhere they are described, no claim of real-world
validity is made from them. Three independently written advisory-derived
reconstructions now document two public Laravel source patterns ([REAL_WORLD_SOURCES.md](REAL_WORLD_SOURCES.md)).

## 5. Clean controls

Four of the fifteen cases contain no defect and must produce zero findings.

Clean controls are mandatory, and the reason is mechanical: **without clean
controls, a model can achieve high recall simply by reporting vulnerabilities
on every diff.** A benchmark made only of defective cases rewards exactly the
behaviour that makes review tooling unusable — flag everything, always be
"right". Clean controls are what make that strategy cost something.

They are chosen to be *plausible* rather than trivially safe:

- a Laravel refactor that touches an authorisation-protected controller action
  while leaving the `authorize()` call intact;
- a WordPress AJAX handler that is *improved* (input sanitised, output escaped)
  while mentioning `$_POST` and touching the database;
- a PDO query reformatted while staying parameterised;
- an argv environment-selector refactor preserving its CLI-only boundary.

A reviewer that reports findings on these is producing exactly the kind of
output that erodes trust in review tooling.

## 6. Labelling and the ground-truth rule

Labels live in the case file under `expected_findings`: a category, a severity,
the file the defect is in, and a human-readable description of the defect.
Clean controls carry an empty list. The case schema enforces the invariants
(clean cases have no findings; defect cases have at least one; the case's
primary category matches one of its findings).

The governing rule:

> **Ground truth is frozen before any model is evaluated.**

Cases are authored or accepted by a human maintainer. Model outputs are never
used as ground truth. LLMs may draft fixtures; labels are frozen before
evaluation.

Evaluation begins only after the expected findings for a case have been
finalized.

This is enforced in the schema rather than only asserted in prose. Each case
records `label_source`, `label_status` and `reviewed_by`, and a case cannot be
marked `frozen` unless its label source is a human one and a reviewer is named
— an agent-drafted case is rejected by the validator if it claims frozen
status. The evaluator reports how many of the scored cases are frozen, and the
CLI and the rendered report mark results from unfrozen labels as provisional.

The full workflow — who may draft, what the reviewer checks, how labels are
frozen and how revisions are versioned — is in [ANNOTATION.md](ANNOTATION.md).

**Status of the v0.1 suite:** all fifteen cases are currently `agent_drafted` /
`pending_review`, awaiting the maintainer's review pass. Until that pass is
complete, any numbers the harness produces are provisional and are labelled as
such.

Labels are the maintainer's. That is a single labeller — a real limitation,
recorded here rather than dressed up. Inter-rater agreement is *not yet
measured*; adding a second labeller is a v0.2 item. The academic collaborator
reviews the taxonomy, the annotation rules, the methodology and two to three
representative cases, and is not expected to annotate the whole suite; cases
that received that separate review carry `academic_review: true`.

Each defective case carries exactly one expected finding in v0.1. That keeps
matching unambiguous, at the cost of not testing how reviewers handle several
interacting defects in one change.

## 7. Defect taxonomy

| Category | Ground truth means |
| --- | --- |
| `authorization` | The change removes, bypasses or fails to add an access-control obligation (policy, gate, middleware or capability check) |
| `injection` | The change lets untrusted input reach SQL without parameterisation, or a console environment-option parser across the web/CLI trust boundary |
| `xss` | The change causes untrusted data to reach output without escaping |
| `secrets` | The change commits credential material into the repository |
| `unsafe_deserialization` | The change deserialises untrusted input into PHP objects |
| `clean_control` | The change contains no defect; any finding is a false positive |

Each finding also carries one of eight machine-readable defect types:
`authorization_policy_removed`, `authorization_middleware_removed`,
`authorization_capability_missing`, `sql_injection`, `xss_unescaped_output`,
`hardcoded_secret`, `unsafe_deserialization`, or
`environment_override_from_web_argv`. The last type is configuration injection:
request-controlled web argv overrides trusted runtime environment selection. It
is not a SQL-injection alias and cannot match `sql_injection`. CSRF and nonce
verification are distinct mechanisms and are not aliases for authorization in v0.1.

Broad model categories are mapped onto the reporting taxonomy through a fixed,
versioned alias table (`CATEGORY_ALIASES` in `src/webfixbench/schemas.py`), so
that "SQL injection", "sqli" and "injection" are treated alike. The table is an
explicit, deliberate list, not fuzzy string similarity: two phrasings are
equivalent only because someone added them to it. Categories that do not map
are normalised to `other` and counted as false positives — never discarded.

## 8. Evaluation unit

The primary unit is the **finding**: each expected finding is matched against
at most one predicted finding, one-to-one.

A secondary, case-level view is also reported (`detection`): did the reviewer
report at least one finding that matches an expected defect? An unrelated
finding does not count as detection. The rate uses defective cases with valid
responses; malformed responses are reported separately (sections 10 and 14).

## 9. Matching strategy

Deterministic, no LLM judge.

- Default mode `defect_type`: a prediction matches an expected finding when its
  normalised defect type equals the expected defect type. Unknown types remain
  predictions and therefore become false positives; they are never dropped.
- Stricter mode `defect_type_file`: as above, and the predicted file must identify
  the same file (trailing path segments compared, so `b/app/X.php` and
  `app/X.php` are the same file).
- Assignment is greedy and one-to-one, in expected-finding order, preferring a
  candidate that also points at the right file. Unmatched predictions are false
  positives; unmatched expected findings are false negatives.

Known limitations of this rule:

- A prediction with the right defect type and the wrong explanation still counts
  as a true positive. With one expected finding per case this is a narrow gap,
  but it is a real one.
- Line numbers are stored but not used in matching; diff line numbering is too
  ambiguous to score fairly.
- Severity is stored but not matched; severity judgement is closer to opinion
  than to ground truth.

An LLM judge would catch the "right category, wrong reason" case, but it would
also make the benchmark's results depend on a model, which is the thing being
measured. That trade may be revisited later as an *additional* reported metric,
never as the only one.

## 10. Malformed output

A response that does not parse and validate against
`schema/model_response.schema.json` is recorded as malformed: it produces no
true positives and no false positives, all of the case's expected findings
count as false negatives, and it is counted in `counts.invalid_responses`.

The important consequence: a reviewer that emits prose instead of JSON does not
get credit for "no findings" on a clean control. Structural unreliability is
itself a reliability result and is reported as its own number.

One documented leniency: if the payload is wrapped in a code fence or
surrounded by prose, the outermost JSON object is extracted before validation.
Anything beyond that is malformed.

## 11. Provider settings

- Temperature defaults to 0.0 and is recorded per run.
- `max_output_tokens` defaults to 2048 and is recorded.
- The model id is never defaulted for paid providers; `--model` is required and
  the id the API reports back is stored.
- OpenAI uses `POST /v1/responses` by default. Chat Completions remains an
  explicit `--api-type chat.completions` option; the provider never guesses an
  endpoint from a model name. Anthropic uses `POST /v1/messages`.
- Both providers can apply the same model-response JSON Schema: OpenAI through
  Responses `text.format` (or Chat Completions `response_format`) and Anthropic
  through `output_config.format`. Each run records `api_type`, endpoint, model
  and `output_constraint` (`json_schema`, `json_object`, or `prompt_only`).
- Structured-output support depends on the selected model. The harness does not
  silently weaken a rejected constraint. Malformed-output rates are not
  directly comparable when runs used different output constraints.
- Fable models are excluded by project policy.
- Latency is wall-clock around the provider call, in milliseconds.
- Token usage is taken from the provider response when available and flagged
  `estimated: false`; the mock provider reports a character-based estimate and
  flags it `estimated: true`.
- Cost is computed only from a user-supplied pricing table and is otherwise
  `null`. The project ships no vendor prices; a stale table would quietly
  produce wrong numbers in published results.

## 12. Prompt freezing

The reviewer prompt is a file, not a string in the code. The current default is
`prompts/review_v3.txt`.
Every run records the prompt id and the SHA-256 of the exact text used, so a
result file can always be tied to the prompt that produced it.

Prompts are versioned by filename and are append-only: `review_v1.txt` and
`review_v2.txt` are frozen. The configuration-injection addition uses `review_v3.txt`, and results
produced under different prompt versions are not compared as if they were the
same experiment.

The v3 prompt asks the reviewer to report material defects visible in the diff,
to reason only from the supplied context, to avoid speculation, to return an
empty list when the change looks safe, and to attach self-reported confidence to
each finding without claiming calibration. It states explicitly that reporting a defect that is not there is
an error of the same kind as missing one.

## 13. Run metadata

Every result file records: WebFixBench version, result-format version, run id,
UTC timestamp, suite id and version, cases run, prompt id and SHA-256, provider
settings (provider, model, temperature, max output tokens), and per case the
raw response text, the parsed response, validation errors, latency, usage and
cost.

Running and scoring are separate commands. A paid run is stored raw and can be
re-scored under a different matching mode without calling the model again.

## 14. Metrics

Finding-level:

- true positives, false positives, false negatives
- precision = TP / (TP + FP), recall = TP / (TP + FN), F1

Clean-control and case-level:

- **clean-control false-alarm rate** = clean cases with at least one finding /
  clean cases with a valid response. This is the primary false-positive number
  in v0.1. It is *not* a textbook FPR: finding-level review has no well-defined
  true-negative count, so a TN-based FPR would be a fabricated denominator.
- mean findings per clean case; mean false positives per defect case
- case detection rate (defect cases with ≥1 correct finding) and full detection
  rate (defect cases with no false negatives)

Breakdowns by ecosystem and by defect category, plus latency, token usage, cost
and confidence summaries.

Every rate is either a number or `null`. `null` means "not computable from this
run" — an empty denominator, or data the provider did not report. Nothing is
silently rendered as zero.

## 15. Confidence data

Stored per finding and per response (`overall_confidence`). Reported as
distribution summaries plus the mean confidence on true positives, the mean on
false positives, and the gap between them.

That gap is the honest v0.1 version of "is this confidence worth anything":
a reviewer whose wrong findings are as confident as its right ones is
telling a human nothing useful, regardless of its F1.

**Calibration is not yet measured.** Brier score and ECE need a well-defined
binary event with a probability attached. A single self-reported confidence on
a finding does not cleanly provide one (confidence in *what* — that the line is
wrong, that the category is right, that a human would agree?). Rather than ship
a number that looks rigorous and is not, v0.1 stores the raw values, keeps the
fields in the metrics document as `null`, and defers the metric to a prompt
design that asks for a well-specified probability.

## 16. Known limitations

1. **Size.** 15 cases. Any per-category number is computed over one to three
   cases and should be read as illustrative, not as an estimate.
2. **Synthetic data.** Cleaner and smaller than real pull requests.
3. **Single labeller.** No inter-rater agreement yet.
4. **One defect per case.** Interacting defects are untested.
5. **Diff-only context.** Real reviewers can open the repository.
6. **Category-level matching.** Right category for the wrong reason scores as a
   hit.
7. **No statistical claims.** Provider differences on this small, purposively
   selected suite are descriptive. Statistical significance has not been
   assessed, and these differences do not establish a general provider ranking.
8. **Single run.** Run-to-run variance at temperature 0 is not yet measured.

## 17. Data contamination risk

The cases are new text, which reduces the chance of verbatim memorisation, but
they are built from *well-known* defect patterns that are extensively described
in public training data. A model may score well by recognising the pattern
family rather than by reasoning about the change.

Nothing in v0.1 controls for this. The roadmap's repository-context experiments
and the introduction of harder, less canonical cases are partly aimed at it.
Treat high scores on this suite as evidence that a reviewer handles textbook
patterns, not that it reviews well.

## 18. Future repository-context experiments

The planned v0.3 experiment holds the defect fixed and varies how much context
the reviewer sees: diff only, diff plus the full changed file, diff plus
relevant repository context. Because the ground truth is attached to the defect
rather than to the presentation, the same cases can be reused across all three
conditions, which makes "how much of review quality is a context problem" a
directly measurable question.

## 19. What this benchmark cannot tell you

A small synthetic benchmark does **not** establish general model security
capability. A good score here means a reviewer handled fifteen specific,
clearly-labelled changes. It is not evidence that the reviewer is safe to rely
on for a codebase, and it must not be used to certify a model or a tool as
secure. See [ETHICS.md](ETHICS.md).
