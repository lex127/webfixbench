# Real-world case sources — inspected candidates

Inspected on **2026-09-20** against public advisories, upstream fix patches and
licenses at those commits. This is a small selection record, not an exhaustive
survey. The suite now contains three **synthetic reconstructions** from two
advisories, alongside twelve original synthetic cases. They are not original
upstream patches, evidence of real-world review performance, or frozen ground truth.

## Selection gate and measurements

Prefer one or two changed files, roughly <=80 added/deleted lines, one primary
mechanism, and enough context to decide the label without an upstream checkout.
Counts below include **all files, including tests**. Each patch's `+` and `-`
lines were counted directly (excluding headers/context), then cross-checked
against GitHub's per-file stats. Counts describe the exact fix, not a whole
release comparison or just its smallest hunk. No upstream code was executed.

| Decision | Advisory | Exact fix | Files | Added / deleted | Dominant mechanism | Upstream license |
| --- | --- | --- | --- | --- | --- | --- |
| USE | [GHSA-546h-56qp-8jmw / CVE-2024-13918](https://github.com/advisories/GHSA-546h-56qp-8jmw) | [Laravel 45287fb](https://github.com/laravel/framework/commit/45287fb2a91c69bb1c110539b9b7341faf5aee33) | 1 | +2 / -2 | `xss_unescaped_output` | [MIT, Taylor Otwell](https://github.com/laravel/framework/blob/45287fb2a91c69bb1c110539b9b7341faf5aee33/LICENSE.md) |
| SKIP | [GHSA-c7r6-vx3h-w5g2 / CVE-2026-84374](https://github.com/SpartnerNL/Laravel-Excel/security/advisories/GHSA-c7r6-vx3h-w5g2) | [Laravel-Excel b5cafdf](https://github.com/SpartnerNL/Laravel-Excel/commit/b5cafdfcf7ec63924e83303763be8fcae340f70b) | 4 | +133 / -22 | Filesystem-root bypass; no current type | [MIT, Spartner](https://github.com/SpartnerNL/Laravel-Excel/blob/b5cafdfcf7ec63924e83303763be8fcae340f70b/LICENSE) |
| SKIP | [GHSA-qg7r-fjh2-wvx8](https://github.com/WordPress/wordpress-develop/security/advisories/GHSA-qg7r-fjh2-wvx8) | [WordPress 95a9b73](https://github.com/WordPress/wordpress-develop/commit/95a9b738f2995588852ca5be193102816a6a691c), [r63665](https://core.trac.wordpress.org/changeset/63665) | 1 | +1 / -1 | XSS through unsafe HTML mutation; not ordinary missing escaping | [GPL-2.0-or-later, WordPress contributors](https://github.com/WordPress/wordpress-develop/blob/95a9b738f2995588852ca5be193102816a6a691c/src/license.txt) |
| USE | [GHSA-gv7v-rgg6-548h / CVE-2024-52301](https://github.com/laravel/framework/security/advisories/GHSA-gv7v-rgg6-548h) | [Laravel 18b326d](https://github.com/laravel/framework/commit/18b326d22d831e1fe05e737209e367e30796d5f3) | 1 | +3 / -1 | `environment_override_from_web_argv` | [MIT, Taylor Otwell](https://github.com/laravel/framework/blob/18b326d22d831e1fe05e737209e367e30796d5f3/LICENSE.md) |
| SKIP | [GHSA-w9mx-xmg4-gc4r](https://github.com/stefanzweifel/laravel-backup-restore/security/advisories/GHSA-w9mx-xmg4-gc4r) | [backup-restore a73f6c3](https://github.com/stefanzweifel/laravel-backup-restore/commit/a73f6c3dfd57c5efbc46cce4e93ed033bedce8b0) | 12 | +221 / -11 | Shell-command injection; no current type | [MIT, Stefan Zweifel](https://github.com/stefanzweifel/laravel-backup-restore/blob/a73f6c3dfd57c5efbc46cce4e93ed033bedce8b0/LICENSE.md) |
| SKIP | [GHSA-3pwp-g2mj-5p3v](https://github.com/WordPress/WordPress-Coding-Standards/security/advisories/GHSA-3pwp-g2mj-5p3v) | [WordPressCS a29048d](https://github.com/WordPress/WordPress-Coding-Standards/commit/a29048d0bbef5cf25d42349c74e4072d3cbc8325), [PR 2771](https://github.com/WordPress/WordPress-Coding-Standards/pull/2771) | 3 | +122 / -102 | Evaluation of untrusted PHP source; no current type | [MIT, John Godley and contributors](https://github.com/WordPress/WordPress-Coding-Standards/blob/a29048d0bbef5cf25d42349c74e4072d3cbc8325/LICENSE) |

## USE: Laravel diagnostic output

The fix changes two raw Blade expressions to escaped expressions in
`src/Illuminate/Foundation/resources/exceptions/renderer/components/context.blade.php`
(+2/-2): request body and route parameters. The advisory describes reflected
XSS on the debug error page, fixed in 11.36.0.

`laravel-ghsa-debug-xss-001` independently reconstructs **only the request-body
sink** in a four-line view with invented markup and names. Its diff deliberately
runs from escaped to raw output, so it introduces the defect instead of asking a
reviewer to flag a security fix. Context pins string input, HTML rendering,
endpoint exposure and the absence of later escaping. Debug exposure is a
precondition, not a second newly introduced defect. No framework layout or
advisory prose is copied into the fixture.

## USE: Laravel environment detection

The fix changes `src/Illuminate/Foundation/Application.php` (+3/-1): only a
console execution may supply argv to environment detection. The advisory pins
`register_argc_argv=on`. The companion
[EnvironmentDetector](https://github.com/laravel/framework/blob/18b326d22d831e1fe05e737209e367e30796d5f3/src/Illuminate/Foundation/EnvironmentDetector.php)
shows how console arguments override the callback's trusted environment.

`laravel-ghsa-env-001` reconstructs the missing SAPI gate in a new, complete
helper. Context explicitly states web SAPI `cgi-fcgi`, enabled argv population
from queries, trusted configured defaults, and the meaning of the return value.
The only option form modelled is `--env=`. It does not claim .env-file loading,
debug enablement, RCE or an end-to-end exploit. The new mechanism
`environment_override_from_web_argv` is **configuration injection**, reported
under `injection`; it must not match `sql_injection` merely because the broad
category is shared. No matching algorithm change is needed.

`laravel-ghsa-env-clean-001` is a safe-to-safe early-return refactor of the same
helper, with identical context. The web guard still returns before scanning
argv. It is an advisory-inspired control, not a separate vulnerability or
independent advisory sample. Review the siblings together but count this
advisory only once when discussing source diversity.

## SKIP evidence

- **Laravel-Excel:** `src/Files/Disk.php` is only +1/-10, but that is not the full
  fix. `src/Excel.php` adds exception-safe cleanup (+8/-8),
  `src/Files/RemoteTemporaryFile.php` changes remote-to-local copying (+9/-4),
  and `tests/ExcelTest.php` adds 115 lines covering root confinement, cleanup
  and leftover bytes. Four files and 155 changed lines exceed this slice's
  gate. The original direct filesystem write also failed to truncate. Do not
  present the isolated Disk hunk as a one-file fix or relabel it as SQL injection.
- **WordPress wpautop:** the official repository advisory exists even though
  the global `/advisories/` URL returned 404 at inspection. The sole changed
  line in `src/wp-includes/formatting.php` makes blockquote matching aware of
  quoted attributes. The surrounding function performs newline substitution,
  paragraph insertion, block unwrapping and later replacements on KSES-filtered
  input. The advisory's XSS claim concerns that composition. A tiny standalone
  rewrite has not been shown to preserve the same security effect; treating it
  as simple missing escaping would change the mechanism. Skip on self-contained
  reconstruction confidence, **not** patch size. No WordPress source excerpt or
  payload is included. A later slice may revisit with independently justified
  inert structural tests and an appropriate HTML-mutation taxonomy.
- **Backup restore:** the full fix changes archive entry validation, three DB
  importers, the decompression exception and dump enumeration, a PHPStan
  baseline and five test files (12 total, 232 changed lines). Shell escaping,
  traversal validation and filename filtering are multiple mechanisms; skip.
  No archives are generated or extracted for this work.
- **WordPressCS:** the sniff changes +58/-69, its fixture +59/-27, and its test
  expectations +5/-6. Replacing eval with token analysis is 224 changed lines
  across three files, beyond this slice's small-patch gate. No lint execution
  over untrusted source is performed.

## Excluded without further inspection

- GHSA-crmm signed-URL work: multi-PR scope excluded by this task.
- GHSA-52p2 login XSS-to-RCE chain: interacting defects excluded by this task.
- `mahdi-salmanzade/laravel-vuln-lab` and
  `appelsiini/vulnerable-laravel-app`: educational vulnerable apps are not
  evidence of real-incident ground truth; no code or labels imported.
- Wordfence-only plugin GHSAs without a public upstream fix: insufficient
  patch evidence. Large framework copies are excluded regardless of license.

## Provenance and review workflow

Every included case records `source_type: public_advisory`, the advisory URL
and ID, original project, `reconstruction_type: synthetic_reconstruction`,
license note, and exact fix/license links in `references`. Both validators
require nonempty advisory provenance. These fields survive case round-trips
but are not supplied to the reviewer, who sees only description/context/diff.

Oleksii Siniaiev explicitly reviewed and accepted the three reconstructed cases
on 2026-09-20. They now use `label_source:
public_advisory_plus_human_review`, `label_status: frozen`, and retain
`academic_review: false`. Reading an advisory and passing automated tests alone
would not have approved them; the human decision is preserved in
[HUMAN_REVIEW_PACKET.md](HUMAN_REVIEW_PACKET.md).

The upstream projects retain their licenses and attribution. The new fixture
code is independently written under this repository's Apache-2.0 license;
this does not relicense upstream code or remove the need to review provenance.
Public advisories may already be in training data. Reconstructions improve
source traceability, not evidence of generalisation or contamination control.
