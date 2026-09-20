# Annotation guide

How ground truth is produced, reviewed and frozen in WebFixBench, and how
predictions are matched against it.

## The rule everything else follows from

> **Ground truth is frozen before any model is evaluated.**

Cases are authored or accepted by a human maintainer. Model outputs are never
used as ground truth. LLMs may draft fixtures; labels are frozen before
evaluation.

Evaluation begins only after the expected findings for a case have been
finalized.

A benchmark whose answer key is produced by the class of system under test
measures agreement with that system, not correctness. The distinction is
enforced in the schema, not just in prose: a case cannot be marked `frozen`
unless its `label_source` is a human one and `reviewed_by` names a person.

## What counts as a benchmark finding

A finding is a **specific, material defect introduced or exposed by the change
under review**, identifiable from the diff plus the case's `context`.

It is a finding when:

- the change itself causes it — a guard removed, an escape dropped, a
  parameterised query replaced by concatenation;
- it belongs to one of the v0.1 categories: `authorization`, `injection`,
  `xss`, `secrets`, `unsafe_deserialization`;
- a competent reviewer, given only what the case supplies, would call it a
  defect without argument.

It is **not** a finding when:

- it is a style, naming, formatting, performance or architecture preference;
- it depends on code the case does not show and does not state in `context`;
- it is a pre-existing condition the change neither introduces nor worsens;
- reasonable reviewers could disagree about whether it is a defect at all.

## Authoring workflow

1. An LLM or agent **may propose** a fixture: diff, description, context and a
   suggested label. This is a draft (`label_source: "agent_drafted"`,
   `label_status: "pending_review"`, `reviewed_by: []`).
2. The maintainer reviews the fixture by hand and confirms:
   - the intended defect really exists in the diff as written;
   - the defect is realistic for the ecosystem;
   - there is exactly one primary intended defect, unless multiple defects are
     explicitly labelled;
   - no accidental second vulnerability changes the ground truth;
   - clean controls are genuinely clean **within the supplied context**.
3. The maintainer writes or approves `expected_findings`.
4. The label is frozen: `label_status: "frozen"`, `label_source` set to a human
   value, `reviewed_by` naming the reviewer.
5. Only then may models be evaluated on the case.

Reviewer names are recorded only for reviews that actually happened. A case is
never marked frozen or attributed to a reviewer speculatively.

### Academic review

The academic collaborator reviews the taxonomy, these annotation rules, the
methodology, and two to three representative cases. Per-case annotation of the
whole suite is explicitly not expected. A case that received that separate
review sets `academic_review: true`; every other case leaves it `false`.

### Status of the v0.1 suite

All twelve cases are currently `agent_drafted` / `pending_review`. They were
drafted with the workflow above and are awaiting the maintainer's review pass.
Until that pass is done and the labels are frozen, any scores the harness
produces are provisional — the CLI, the evaluation document and the rendered
report all say so, with a count of frozen cases.

## Choosing a category

Pick the category describing the **mechanism of the defect**, not its
consequence. A missing capability check that lets a user read other people's
data is `authorization`, not a data-exposure category — the reason the data
leaked is that nothing checked permission.

When two categories genuinely apply (a missing nonce *and* a missing capability
check), they collapse into the single category that describes the primary
mechanism, and the description names both aspects. When a case has two
genuinely distinct defects, label both explicitly or simplify the case.

New categories are a deliberate decision, not an ad-hoc one. v0.1's five
categories were chosen because their ground truth is objective; adding
subjective categories would turn the benchmark into a measure of taste
agreement.

## Clean controls

A `clean_control` case contains **no defect**: the correct review is an empty
findings list, and any finding reported on it is a false positive.

Clean controls are mandatory, not decorative. Without them, a reviewer can
score high recall simply by reporting vulnerabilities on every diff — and the
benchmark would reward exactly the behaviour that makes review tooling
unusable in practice.

A good clean control is *tempting*: it touches security-relevant code, or looks
like a pattern that usually is a defect, and is nevertheless correct. A diff
that is obviously safe tests nothing.

"Clean within the supplied context" is the standard. If a case's safety depends
on a fact the reviewer cannot see — that an attribute is fillable, that a nonce
check exists upstream — that fact goes in `context` or the case is rejected.

## Rejecting ambiguous cases

A case is rejected or simplified when:

- two competent reviewers could disagree about the label;
- the defect depends on unstated assumptions about unseen code;
- the diff contains an accidental second defect that was not intended;
- the "clean" control turns out to have a real problem;
- the defect is only a defect under a specific runtime configuration that the
  case does not pin down.

Rejection is cheap; a wrong label silently corrupts every result computed from
it thereafter.

## Multiple defects

**One case should ideally have one primary defect.**

If a case has multiple meaningful defects, either label all of them explicitly,
or reject or simplify the case. What is not acceptable is a case with an
unlabelled second defect: a reviewer that correctly reports it would be
penalised with a false positive.

v0.1 uses exactly one expected finding per defective case. For example,
`wp-authz-001` includes nonce verification and a prepared query so that its
missing capability check is the only intended defect. Multi-finding labelling
remains a v0.2 item.

## Freezing and versioning

- A frozen label is not edited in place. If a label turns out to be wrong, the
  fix is a new case revision, and results produced under the old labels are not
  compared with results produced under the new ones as if they were the same
  experiment.
- Changing a diff, a `context` paragraph or an `expected_findings` entry after
  freezing is a **case revision**: bump the suite version and note the change in
  the changelog, because it changes what past numbers meant.
- Adding a new case bumps the suite's `case_count` and its version.
- The prompt is frozen the same way: `prompts/review_v1.txt` is immutable, and
  a wording change becomes `review_v2.txt`.

## Matching predictions to ground truth

Deterministic, conservative, and documented — no LLM judge.

1. **Normalise** the predicted category onto the v0.1 taxonomy through the
   explicit alias table in `src/webfixbench/schemas.py`. The mapping is a
   deliberate, versioned list, not fuzzy string similarity: "missing
   authorization", "broken access control" and "missing capability check" are
   equivalent **because the table says so**, and an alias only becomes
   equivalent when someone adds it deliberately. Categories that do not map
   become `other` and are counted as false positives, never discarded.
2. **Match** on normalised category (default mode `category`), optionally also
   on file (`category_file`). Assignment is greedy and one-to-one, preferring a
   candidate that also points at the right file.
3. **Do not** require the prediction's natural-language wording to resemble the
   label's wording. Wording similarity is not evidence of understanding, and
   scoring it would make results depend on prose style.
4. **Unmatched predictions** are false positives; **unmatched expected
   findings** are false negatives.
5. **Malformed output** is never scored as correct — not as a true positive,
   and not as a clean "no findings" answer.

Known limitation: a prediction with the right category and the wrong
explanation counts as a true positive. Any fuzzy or semantic LLM-as-judge
scoring is future work, and if it is ever added it will be reported alongside
deterministic matching, never as a replacement for it — including the
disagreement between the two as a result in its own right.

## Checklist before freezing a case

- [ ] The defect is present in the diff as written
- [ ] The defect is realistic for the ecosystem
- [ ] Exactly one primary defect, or all defects labelled
- [ ] No accidental second vulnerability
- [ ] Decidable from `diff` + `context` alone
- [ ] Category describes the mechanism and comes from the fixed taxonomy
- [ ] Clean controls are clean within the supplied context
- [ ] `expected_findings` written or approved by a human
- [ ] `reviewed_by` names that human
- [ ] `label_status` set to `frozen`
