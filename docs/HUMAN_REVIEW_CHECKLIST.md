# Human ground-truth review checklist

This is the maintainer's manual review record. Checking boxes is a human act;
no script or agent may infer approval from passing tests. Until Oleksii reviews
and approves a case, it remains `label_source: agent_drafted`, `label_status:
pending_review`, with an empty `reviewed_by` list.

For a defective case, “Clean control is genuinely clean” means “not
applicable, because this is not a clean control”; the reviewer should check it
only after confirming that classification. For a clean case, “Intended defect
exists” means “not applicable, because no defect is intended.”

## `laravel-authz-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `laravel-authz-002`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `laravel-clean-001`

- [ ] Diff is realistic
- [ ] Intended defect exists / not applicable
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct / not applicable
- [ ] Expected severity is reasonable / not applicable
- [ ] Clean control is genuinely clean
- [ ] Oleksii manually approved ground truth

## `laravel-injection-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `laravel-xss-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `php-clean-001`

- [ ] Diff is realistic
- [ ] Intended defect exists / not applicable
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct / not applicable
- [ ] Expected severity is reasonable / not applicable
- [ ] Clean control is genuinely clean
- [ ] Oleksii manually approved ground truth

## `php-injection-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `php-secrets-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `wp-authz-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `wp-clean-001`

- [ ] Diff is realistic
- [ ] Intended defect exists / not applicable
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct / not applicable
- [ ] Expected severity is reasonable / not applicable
- [ ] Clean control is genuinely clean
- [ ] Oleksii manually approved ground truth

## `wp-deser-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `wp-xss-001`

- [ ] Diff is realistic
- [ ] Intended defect exists
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct
- [ ] Expected severity is reasonable
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `laravel-ghsa-debug-xss-001`

Review focus: Confirm the request body is a plain string and raw Blade output introduces the sole XSS sink under the stated debug exposure.

- [ ] Advisory, exact upstream fix and license links inspected
- [ ] Independent reconstruction faithfully isolates the sourced pattern
- [ ] Diff is realistic
- [ ] Intended defect exists / not applicable for clean control
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct / not applicable for clean control
- [ ] Expected severity is reasonable / not applicable for clean control
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `laravel-ghsa-env-001`

Review focus: Confirm web argv control and the exact SAPI/configuration assumptions; classify configuration injection separately from SQL injection.

- [ ] Advisory, exact upstream fix and license links inspected
- [ ] Independent reconstruction faithfully isolates the sourced pattern
- [ ] Diff is realistic
- [ ] Intended defect exists / not applicable for clean control
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct / not applicable for clean control
- [ ] Expected severity is reasonable / not applicable for clean control
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## `laravel-ghsa-env-clean-001`

Review focus: Compare with the defective sibling: the non-cli return must precede argument scanning, and first-match CLI behaviour must be preserved.

- [ ] Advisory, exact upstream fix and license links inspected
- [ ] Independent reconstruction faithfully isolates the sourced pattern
- [ ] Diff is realistic
- [ ] Intended defect exists / not applicable for clean control
- [ ] No unintended second defect
- [ ] Context contains every fact needed by reviewer
- [ ] Expected defect_type is correct / not applicable for clean control
- [ ] Expected severity is reasonable / not applicable for clean control
- [ ] Clean control is genuinely clean / not applicable
- [ ] Oleksii manually approved ground truth

## After manual approval

Only after all applicable boxes for a case are checked should Oleksii update
its provenance fields. That later change must name the actual human reviewer,
remain auditable in Git, and rerun validation and the full test suite. This
repository deliberately provides no automatic approval or freeze command.
