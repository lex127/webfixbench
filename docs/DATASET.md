# Dataset — `php-web-v0.1`

Twelve labelled changes from the PHP web ecosystem. All are **synthetic**:
written for this benchmark, inspired by defect patterns that are common in
production PHP work. They contain no client, private or third-party source
code.

Synthetic fixtures are deliberate. They isolate one defect at a time, fix
exactly what a reviewer is allowed to assume, and make false-positive
measurement reproducible against controls that are known to be clean. They do
not demonstrate real-world validity, and none is claimed;
[REAL_WORLD_SOURCES.md](REAL_WORLD_SOURCES.md) plans the advisory-derived
expansion.

> **Label status.** All twelve cases are currently `label_status:
> "pending_review"` — drafted, and awaiting the maintainer's review pass. Under
> the project's ground-truth rule, scores computed against unfrozen labels are
> provisional, and the harness says so. See [ANNOTATION.md](ANNOTATION.md).

## Composition

| | Laravel | WordPress | PHP | Total |
| --- | --- | --- | --- | --- |
| With a labelled defect | 4 | 3 | 2 | 9 |
| Clean controls | 1 | 1 | 1 | 3 |
| **Total** | **5** | **4** | **3** | **12** |

By category:

| Category | Cases |
| --- | --- |
| `authorization` | 3 |
| `injection` | 2 |
| `xss` | 2 |
| `secrets` | 1 |
| `unsafe_deserialization` | 1 |
| `clean_control` | 3 |

## The cases

| id | Ecosystem | Category | Difficulty | What the change does |
| --- | --- | --- | --- | --- |
| `laravel-authz-001` | laravel | authorization | easy | Drops `$this->authorize('update', $post)` from a controller action |
| `laravel-authz-002` | laravel | authorization | medium | Lifts admin routes out of the `['auth', 'can:admin']` middleware group |
| `laravel-injection-001` | laravel | injection | easy | Replaces a query-builder call with `DB::select()` on a concatenated string |
| `laravel-xss-001` | laravel | xss | easy | Switches a Blade partial from `{{ }}` to `{!! !!}` for user-submitted comment bodies |
| `laravel-clean-001` | laravel | clean_control | easy | Collapses three assignments into `fill()`/`save()`; `authorize()` untouched |
| `wp-authz-001` | wordpress | authorization | medium | Adds a `wp_ajax_` subscriber-export handler with no capability check and no nonce |
| `wp-xss-001` | wordpress | xss | easy | Echoes `$_GET['wfb_q']` into a template instead of `esc_html( $query )` |
| `wp-deser-001` | wordpress | unsafe_deserialization | medium | Decodes an unsigned cookie with `unserialize()` instead of `json_decode()` |
| `wp-clean-001` | wordpress | clean_control | medium | Adds `sanitize_text_field()` and `esc_html()` to an existing guarded AJAX handler |
| `php-secrets-001` | php | secrets | easy | Replaces `getenv()` with a hardcoded mailer API key literal |
| `php-injection-001` | php | injection | easy | Replaces a prepared statement with `mysqli_query()` on a concatenated string |
| `php-clean-001` | php | clean_control | medium | Reformats a PDO lookup and adds `LIMIT 1`; stays parameterised |

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
      "severity": "high",
      "file": "app/Http/Controllers/PostController.php",
      "description": "Ground truth, for humans. Not shown to the reviewer."
    }
  ],
  "is_clean": false,
  "label_source": "agent_drafted",
  "label_status": "pending_review",
  "reviewed_by": [],
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

`wp-authz-001` is the visible seam: it is missing both a capability check and a
nonce, which a reviewer might reasonably report as two findings. It is labelled
as one authorization finding, and a second authorization finding on that case
would be scored as a false positive. That is a known rough edge of the
one-finding rule, recorded rather than hidden.

## Difficulty

`easy` / `medium` / `hard` is the maintainer's judgement of how visible the
defect is in the diff alone, not a measured quantity. v0.1 has no `hard` cases.
Once real runs exist, difficulty should be revisited against observed
detection rates instead of left as an opinion.

## Provenance and licensing

All v0.1 cases are `source_type: "synthetic"` with `source_url: null`, written
for this project and licensed Apache-2.0 with the rest of the repository.

If advisory-derived or repository-derived cases are added later, each must set
`source_type` and `source_url`, record the original licence and the
modifications made, and attribute the original authors. Apache-2.0 is not
assumed to cover third-party material. See [ETHICS.md](ETHICS.md).

## Adding a case

See [CONTRIBUTING.md](../CONTRIBUTING.md). In short: one defect, decidable from
the supplied context, a category from the fixed taxonomy, and a clean control
for every few defect cases — a dataset without clean controls cannot measure
the failure mode this benchmark exists to measure.

## Known dataset limitations

- **Small.** Per-category numbers rest on one to three cases.
- **Synthetic.** Tidier than real pull requests; the defect is always in the
  diff, and the diff is short. Good for controlled measurement, not evidence of
  real-world validity.
- **Labels not yet frozen.** All twelve are `pending_review`.
- **Single labeller.** Labels are the maintainer's; inter-rater agreement is
  *not yet measured*.
- **Canonical patterns.** These are textbook defects, well represented in public
  writing and therefore plausibly in training data. Detection here is evidence
  about textbook patterns, not about novel ones.
- **English-language, one language, one paradigm.** PHP web code only.
