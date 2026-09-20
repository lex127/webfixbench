# Real-world case sources — research plan

Where the next dataset expansion should come from, and the rules it must
follow. This is a **plan, not a survey**.

> **Status.** This document was written in a build environment with no network
> access. **No source listed here has been inspected yet.** Nothing below is a
> claim about what any repository, advisory or project currently contains; the
> entries are candidates to investigate, recorded with their selection
> criteria so the research pass is reproducible rather than ad hoc.

No advisory-derived cases exist in the repository today. v0.1 is synthetic only.

## Why expand beyond synthetic cases

Synthetic fixtures isolate one defect at a time and make false-positive
measurement reproducible — that is precisely why v0.1 uses them. What they
cannot do is tell you how a reviewer behaves on the shape of a real patch:
larger context, incidental changes, and defects that are not centred in the
diff. Advisory-derived cases are the cheapest way to add that, provided their
provenance is clean.

Target for the first expansion, provisionally `php-web-real-v0.1`: **5–10
carefully selected cases**, not fifty.

## Candidate sources to investigate

Listed in priority order. Each must be inspected before anything is written
about it here.

1. **Official Laravel framework security advisories** —
   <https://github.com/laravel/framework/security/advisories>
   Advisory classes worth examining include signed-URL path confusion, CRLF
   injection, file-validation bypass, Blade/XSS, and historical SQL-related
   advisories. *Not yet inspected.*
2. **GitHub Advisory Database entries for Laravel and PHP packages.** Prefer
   small packages where the patch is short and the defect is easy to state.
   *Not yet inspected.*
3. **WordPress core security advisories.** *Not yet inspected.*
4. **Public WordPress plugin advisories** with source or fix references.
   Defect classes of interest: missing capability checks, missing nonce
   verification, unsafe `unserialize`, path traversal, unsafe output escaping.
   *Not yet inspected.*
5. **Intentionally vulnerable educational Laravel repositories.** Two
   candidates named by the maintainer:
   - <https://github.com/mahdi-salmanzade/laravel-vuln-lab>
   - <https://github.com/appelsiini/vulnerable-laravel-app>

   Described to the maintainer as, respectively, an intentionally vulnerable
   Laravel security-research application and an older deliberately vulnerable
   Laravel demonstration application. **Both descriptions are unverified**, as
   is each repository's licence — which decides whether anything may be derived
   from it at all. *Not yet inspected.*

Preference throughout: sources where an upstream commit or fix reference
exists, so the defect and its correction can both be understood.

## Selection criteria for a candidate case

Include only when **all** of these hold:

- the advisory is public;
- the fix is public;
- both the vulnerable and the fixed behaviour are understood, not guessed;
- the patch is small — preferably one or two files, under roughly 80 changed
  lines;
- one dominant defect category;
- the surrounding context can be made self-contained in a `context` paragraph;
- licence and attribution are clear;
- no live exploitation is required to understand or verify it.

Good candidate defect types: authorization / capability checks, nonce and CSRF
validation, XSS and output escaping, SQL and query injection, unsafe
deserialization, path traversal, validation bypass, secret exposure.

Avoid, at least initially: massive framework refactors; race conditions needing
complex environments; multi-component vulnerabilities; bugs that depend on
undocumented runtime assumptions; anything whose ground truth is disputed.

## Per-case workflow

1. Inspect the advisory.
2. Inspect the upstream repository.
3. Identify the fix commit, if public.
4. Understand the exact defect — mechanism, not just category.
5. Reconstruct a minimal diff.
6. Verify the ground truth by hand.
7. Record provenance.
8. Freeze the label ([ANNOTATION.md](ANNOTATION.md)).
9. Only then benchmark models.

## Case format for advisory-derived cases

```json
{
  "source_type": "public_advisory",
  "source_url": "https://…",
  "advisory_id": "GHSA-…",
  "original_project": "vendor/package",
  "reconstruction_type": "synthetic_reconstruction",
  "license_note": "how the original is licensed and what that permits here",
  "label_source": "public_advisory_plus_human_review",
  "label_status": "frozen",
  "reviewed_by": ["…"]
}
```

`advisory_id`, `original_project`, `reconstruction_type` and `license_note` are
not yet in the case schema; they are added when the first advisory-derived case
is, so that the schema never advertises fields nothing uses.

**Prefer synthetic reconstruction of the vulnerability pattern over copying
source fragments.** A reconstruction that captures the defect in newly written
code avoids the licensing question entirely and usually makes a better case,
because irrelevant surrounding code can be dropped. Where an excerpt genuinely
is necessary, keep it minimal and record `reconstruction_type: "excerpt"` with
the original licence.

An advisory's text alone is **not** sufficient ground truth. Advisories
summarise; they are frequently vague about which line is the defect. The label
comes from reading the patch.

## Explicitly not the plan

- Scraping a hundred CVEs
- Bulk-importing advisories
- Auto-labelling advisories with an LLM
- Treating advisory text as ground truth on its own
- Copying large amounts of code from any of the repositories above
- Any live exploitation harness
