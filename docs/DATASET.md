# Dataset — `php-web-v0.1`

Fifteen labelled changes from the PHP web ecosystem, suite revision **0.1.2**:
twelve original synthetic fixtures and three **advisory-derived synthetic
reconstructions** from two public Laravel advisories. All code is written for
this benchmark; no upstream framework files are vendored.

These small fixtures isolate a pattern with explicit context. Advisory
provenance makes the selection traceable but does not establish real-world
review performance. Inspected patches, licenses and rejection reasons are in
[REAL_WORLD_SOURCES.md](REAL_WORLD_SOURCES.md).

> **Label status.** Oleksii Siniaiev explicitly reviewed and accepted all
> fifteen cases on 2026-09-20. Every label is frozen; `academic_review` remains
> false for every case. See [ANNOTATION.md](ANNOTATION.md).

## Composition

| | Laravel | WordPress | PHP | Total |
| --- | --- | --- | --- | --- |
| With a labelled defect | 6 | 3 | 2 | 11 |
| Clean controls | 2 | 1 | 1 | 4 |
| **Total** | **8** | **4** | **3** | **15** |

By category:

| Category | Cases |
| --- | --- |
| `authorization` | 3 |
| `injection` | 3 |
| `xss` | 3 |
| `secrets` | 1 |
| `unsafe_deserialization` | 1 |
| `clean_control` | 4 |

## The cases

| id | Ecosystem | Category | Difficulty | What the change does |
| --- | --- | --- | --- | --- |
| `laravel-authz-001` | laravel | authorization | easy | Drops `$this->authorize('update', $post)` from a controller action |
| `laravel-authz-002` | laravel | authorization | medium | Lifts admin routes out of the `['auth', 'can:admin']` middleware group |
| `laravel-injection-001` | laravel | injection | easy | Replaces a query-builder call with `DB::select()` on a concatenated string |
| `laravel-xss-001` | laravel | xss | easy | Switches a Blade partial from `{{ }}` to `{!! !!}` for user-submitted comment bodies |
| `laravel-clean-001` | laravel | clean_control | easy | Collapses three assignments into `fill()`/`save()`; `authorize()` untouched |
| `wp-authz-001` | wordpress | authorization | medium | Adds a nonce-protected `wp_ajax_` subscriber-export handler with no capability check |
| `wp-xss-001` | wordpress | xss | easy | Echoes `$_GET['wfb_q']` into a template instead of `esc_html( $query )` |
| `wp-deser-001` | wordpress | unsafe_deserialization | medium | Decodes an unsigned cookie with `unserialize()` instead of `json_decode()` |
| `wp-clean-001` | wordpress | clean_control | medium | Adds `sanitize_text_field()` to an existing guarded AJAX handler and returns the value as JSON |
| `php-secrets-001` | php | secrets | easy | Replaces `getenv()` with a hardcoded mailer API key literal |
| `php-injection-001` | php | injection | easy | Replaces a prepared statement with `mysqli_query()` on a concatenated string |
| `php-clean-001` | php | clean_control | medium | Reformats a PDO lookup and adds `LIMIT 1`; stays parameterised |
| `laravel-ghsa-debug-xss-001` | laravel | xss | medium | Renders a diagnostic request body with raw Blade output (GHSA-546h-56qp-8jmw) |
| `laravel-ghsa-env-001` | laravel | injection | medium | Lets web argv override a trusted environment after removing the CLI gate (GHSA-gv7v-rgg6-548h) |
| `laravel-ghsa-env-clean-001` | laravel | clean_control | medium | Refactors the same selector with an early web return, preserving the CLI gate |

`webfixbench show <id>` prints any case in full, including its diff.

## Why these clean controls

Clean controls are the false-positive measurement, so they are chosen to be
tempting rather than obviously safe. Each one puts a reviewer next to the kind
of code that usually *is* a defect:

- `laravel-clean-001` touches an authorisation-protected action and uses
  `fill()`, which is a mass-assignment smell in general — but the values are
  literals and the attributes are fillable.
- `wp-clean-001` mentions `$_POST`, writes to the database, and sits in an AJAX
  handler. Every change it makes is an improvement, and the nonce and
  capability checks are visible as context lines.
- `php-clean-001` is a SQL change that remains fully parameterised.
- `laravel-ghsa-env-clean-001` returns an argument-derived value only on CLI;
  the web SAPI returns the trusted default before any argument is inspected.

A reviewer that reports findings here is producing exactly the output that
makes teams stop reading review comments.

## Case format

One JSON file per case in `suites/php-web-v0.1/cases/`, validated against
[`schema/case.schema.json`](../schema/case.schema.json) and by the Python
validator in `src/webfixbench/schemas.py`.

```json
{
  "id": "laravel-authz-001",
  "title": "Policy check removed from PostController::update",
  "language": "php",
  "ecosystem": "laravel",
  "category": "authorization",
  "difficulty": "easy",
  "source_type": "synthetic",
  "source_url": null,
  "description": "What the change does, shown to the reviewer.",
  "context": "Facts about surrounding code the reviewer may rely on. Shown to the reviewer.",
  "diff": "unified diff, shown to the reviewer",
  "expected_findings": [
    {
      "id": "laravel-authz-001-f1",
      "category": "authorization",
      "defect_type": "authorization_policy_removed",
      "severity": "high",
      "file": "app/Http/Controllers/PostController.php",
      "description": "Ground truth, for humans. Not shown to the reviewer."
    }
  ],
  "is_clean": false,
  "label_source": "human_reviewed",
  "label_status": "frozen",
  "reviewed_by": ["Oleksii Siniaiev"],
  "academic_review": false,
  "tags": ["policy", "broken-access-control"],
  "notes": "Labelling rationale. Not shown to the reviewer.",
  "references": []
}
```

What the reviewer sees: `description`, `context`, `diff`. Nothing else — labels,
notes and tags never enter the prompt.

Schema invariants, enforced at load time:

- `is_clean: true` ⇒ `expected_findings` is empty and `category` is
  `clean_control`;
- `is_clean: false` ⇒ at least one expected finding, and `category` matches one
  of them;
- ids are unique within a suite and lowercase-kebab;
- unknown fields are rejected, so a typo cannot silently become an unlabelled
  case;
- `source_type: "public_advisory"` requires a nonempty `source_url`, `advisory_id`,
  `original_project`, `reconstruction_type` and `license_note`; the supported
  reconstruction type is `synthetic_reconstruction`.
- `label_status: "frozen"` requires a human `label_source` and a non-empty
  `reviewed_by`, so an agent-drafted case cannot claim final ground truth.

## The `context` field

Review quality depends on what a reviewer is allowed to assume. Rather than
leave that implicit, each case states the relevant facts — that a policy exists
and is registered, that a cookie is unsigned, that `$_GET` input reaches the
template unfiltered — and the prompt tells the reviewer to reason from those
facts and not to invent unseen code.

This makes the label decidable from what the reviewer was given, which is the
difference between measuring review ability and measuring guessing.

## One finding per case

Every defective case carries exactly one expected finding in v0.1. That keeps
matching unambiguous and keeps per-case scores readable. The cost is that
interacting defects, and a reviewer's ability to prioritise among several real
findings, are untested. Multi-finding cases are a v0.2 item.

`wp-authz-001` verifies its nonce and uses a prepared query, leaving only the
missing capability check as its intended defect. The other eight defective
cases were also reviewed for a second reasonable finding; none was identified.
This is an implementation review, not the required human ground-truth approval,
before the maintainer's acceptance; all labels are now frozen.

## Difficulty

`easy` / `medium` / `hard` is the maintainer's judgement of how visible the
defect is in the diff alone, not a measured quantity. v0.1 has no `hard` cases.
Once real runs exist, difficulty should be revisited against observed
detection rates instead of left as an opinion.

## Provenance and licensing

The original twelve cases use `source_type: "synthetic"` and `source_url: null`.
The three additions use `source_type: "public_advisory"`, `advisory_id`,
`original_project`, `reconstruction_type: "synthetic_reconstruction"` and
`license_note`, plus exact commit/license links in `references`. These fields
are preserved by the loader and CLI but never added to model prompts.

Both source advisories concern MIT-licensed Laravel code (Taylor Otwell).
Fixtures use newly written code and invented names under Apache-2.0, not copied
framework trees. The defect diffs are synthetic regressions (safe to vulnerable);
the sibling control is safe to safe. Neither is represented as an original
upstream patch. The environment siblings share one source and are not independent
incident samples. All three remain unapproved drafts.

The new `environment_override_from_web_argv` type covers request-controlled web
arguments overriding trusted runtime environment selection. Its broad category
is `injection` (configuration injection); it is distinct from `sql_injection`.
The schema, current `review_v3` prompt and deterministic type matching support
it. No new broad category or matching algorithm is introduced. Earlier prompt
versions remain immutable, and results from suite revision 0.1.0 / earlier
prompts are not directly comparable to the expanded baseline.

## Adding a case

See [CONTRIBUTING.md](../CONTRIBUTING.md). In short: one defect, decidable from
the supplied context, a category from the fixed taxonomy, and a clean control
for every few defect cases — a dataset without clean controls cannot measure
the failure mode this benchmark exists to measure.

## Known dataset limitations

- **Small.** Per-category numbers rest on one to three defective cases.
- **Synthetic.** Tidier than real pull requests; the defect is always in the
  diff, and the diff is short. Good for controlled measurement, not evidence of
  real-world validity.
- **Single human reviewer.** All fifteen labels were reviewed by the maintainer;
  no inter-rater agreement or per-case academic review is available.
- **Single labeller.** Labels are the maintainer's; inter-rater agreement is
  *not yet measured*.
- **Canonical patterns.** These are textbook defects, well represented in public
  writing and therefore plausibly in training data. Detection here is evidence
  about textbook patterns, not about novel ones.
- **English-language, one language, one paradigm.** PHP web code only.
