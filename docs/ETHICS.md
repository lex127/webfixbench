# Ethics and responsible use

WebFixBench studies whether LLM reviewers are reliable. It is an evaluation
artifact, not a security tool, and it is built so that publishing it cannot
harm anyone.

## What this repository contains

- Synthetic code changes written for this benchmark.
- Labels describing what is wrong with each change.
- A harness for sending those changes to a reviewer and scoring the answers.

## What it must never contain

- **No client code.** Nothing from any employer, customer or contract.
- **No private repository code.** Nothing from a repository that is not public.
- **No credentials.** No API keys, tokens, passwords or connection strings.
  The credential-shaped literal in `php-secrets-001` is fabricated for the
  purpose of measuring secret detection and grants access to nothing.
- **No personal data.** Names, e-mail addresses and identifiers in cases are
  invented.
- **No undisclosed vulnerabilities.** No zero-days, and no collection of
  unpublished issues.

Contributions that would violate any of these are out of scope regardless of
how useful the case would be. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Third-party and advisory-derived cases

v0.1 uses synthetic cases only. If cases derived from public advisories or
public repositories are added later, each must record:

- the source URL and the original licence;
- the modifications made for the benchmark;
- attribution to the original authors.

Licence compatibility is checked before a case is merged. The project's
Apache-2.0 licence is not assumed to cover third-party material.

## No exploitation, no offensive use

- The benchmark does not run the code in its cases. Nothing is executed,
  deployed or attacked.
- It is not a penetration-testing tool, a scanner, or an exploit collection.
- Cases are illustrations of defect *patterns* at the level of detail needed to
  judge a review, not working exploits.

## Responsible disclosure

If work on this benchmark — writing a case, running a model, reviewing a
contribution — surfaces a previously unknown vulnerability in real software,
it is disclosed to the maintainers of that software first, through their
published security process, and it does not enter this repository until it is
public and the affected project is comfortable with its inclusion.

## What results do and do not mean

**This benchmark does not certify anything.** A score here is not a statement
that a model, a tool or a product is safe, secure, or fit for review work.

Specifically:

- v0.1 is twelve synthetic cases in one ecosystem. It cannot support claims
  about a model's general security capability.
- Results must not be the sole justification for a security decision — choosing
  a review tool, sizing a security budget, or deciding that a change has been
  adequately reviewed.
- An LLM reviewer that scores well here still misses defects. Benchmark results
  must not be used to argue for removing human review.
- Comparative claims between providers require more data than v0.1 has, and
  this repository will say "not yet measured" rather than imply otherwise.

The overreliance risk runs in both directions: a benchmark that overstates
reviewer reliability encourages skipping human review, and one that overstates
unreliability encourages ignoring real findings. Both are failures of this
project, so numbers here are published with their denominators, their
limitations and their `null`s visible.

## Model providers

- API keys are read from the environment only and are never written to result
  files or logs.
- Prompts contain only this repository's synthetic cases. No private or client
  code is ever sent to a model provider through this harness.
- Paid runs are opt-in and explicit; the automated test suite never contacts a
  paid API.

## Contact

Issues and questions: <https://github.com/alexsinyaev/webfixbench/issues>.
For anything that should not be public, contact the maintainer via
<https://alexsinyaev.com/>.
