# Related work

Verified against the linked primary sources on **2026-09-20**. Where those
sources do not answer a comparison question, the table says `not stated by
source`; it does not infer an answer. Blog posts were not used as evidence.

## Comparison

| Project and exact title | Primary task | Data | PR/diff based? | Ground truth | Clean/negative controls | False-positive measurement | Confidence/calibration | Security focus | Languages/ecosystems | Primary sources |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?** | Generate a patch for a GitHub issue | Real issues and corresponding PRs; the paper reports 2,294 problems from 12 repositories | Issue/PR sourced, but the task is patch generation rather than review of a supplied diff | `FAIL_TO_PASS` and `PASS_TO_PASS` tests after applying the patch | not stated by source as a clean-diff review design | not stated by source; success is test-based resolution | not stated by source | not stated by source as a security benchmark | Original paper: Python; official later variants are separate artifacts | [paper](https://arxiv.org/abs/2310.06770), [repository](https://github.com/SWE-bench/SWE-bench), [site](https://www.swebench.com/) |
| **SEC-bench: Automated Benchmarking of LLM Agents on Real-World Software Security Tasks** | Agentic proof-of-concept generation and vulnerability patching | Real CVE instances; paper reports 200 verified instances selected from 898 seeds | Gold patches exist, but agents generate PoCs/patches in containers rather than review labelled diffs | Sanitizer verdicts: a PoC triggers the expected report and a patch makes it disappear | not stated by source | not stated by source as review precision | not stated by source | Yes | C/C++ memory-safety tasks; “PHP” in results is a project name, not a PHP-language suite | [paper](https://arxiv.org/abs/2506.11791), [repository](https://github.com/SEC-bench/SEC-bench), [site](https://sec-bench.github.io/) |
| **SecCodeBench-V2 Technical Report** (repository: SecCodeBench) | Generate or fix secure functions inside project scaffolds | 98 generation/fix scenarios derived from Alibaba industrial production | not stated by source as PR/diff review | Expert-authored functional and security PoC tests, double review, Docker execution; an LLM judge only where deterministic tests cannot decide | not stated by source as clean review controls | Scores generated/fixed code with pass@k, not reviewer FPs on clean diffs | not stated by source | Yes, 22 CWE categories | Java, C/C++, Python, Go and Node.js; PHP is not listed | [paper](https://arxiv.org/abs/2602.15485), [repository](https://github.com/alibaba/sec-code-bench), [site](https://alibaba.github.io/sec-code-bench) |
| **Code Review Bench** (Martian) | Evaluate AI code-review tools on pull requests | Offline: 50 real PRs from five major open-source projects; online: fresh real PRs | Yes | Offline human-curated golden comments with semantic LLM matching; online developer post-review fixes with LLM matching | Dedicated synthetic clean diffs: not stated by source | Yes: precision and recall; duplicate comments are deduplicated | Self-reported model confidence/Brier/ECE: not stated by source; judge calibration is listed as future methodology | Security is one category among several | Offline set: Python, Go, TypeScript, Ruby and Java; PHP/Laravel/WordPress are not listed | [repository](https://github.com/withmartian/code-review-benchmark), [site](https://codereview.withmartian.com) |
| **SEVRA-BENCH: Social Engineering of Vulnerabilities in Review Agents** | Test whether review agents approve or reject vulnerability-reintroducing PRs under deceptive narratives | Paper: 1,062 adversarial PRs from 150 source records; repository/dataset additionally describe a deterministic release with 2,250 malicious and 347 benign PRs | Yes, in an isolated Gitea instance | Agent approval/refusal and whether a rejection cites security; repository/dataset report malicious detection and benign false-decline rate | Paper text retrieved does not state benign controls; repository and dataset state 347 benign security-fix PRs | Paper does not state finding-level precision; repository reports false-decline rate on benign PRs | not stated by source | Yes | not stated by source | [paper](https://arxiv.org/abs/2606.13757), [repository](https://github.com/rufimelo99/malicious-pr-bench), [dataset](https://huggingface.co/datasets/RedAI4Code/SEVRA) |
| **WebFixBench v0.1 development suite** | Review a supplied diff and report labelled defects or none | 15 synthetic cases, including 3 advisory-derived reconstructions | Yes | Hand-written expected findings; deterministic defect-type matching | Yes, 4 of 15 | Finding-level FPs and clean-control false-alarm rate | Confidence stored; calibration not measured | Yes, five broad categories and eight defect types | PHP, Laravel and WordPress | this repository |

## Relationship to WebFixBench

SWE-bench, SEC-bench and SecCodeBench primarily evaluate repair, generation or
agentic security work rather than finding-level review of a supplied change.
They provide important complementary evidence but answer a different primary
question.

Code Review Bench is the closest neighbour in task shape and already measures
precision and recall for review findings on real pull requests. WebFixBench
does not claim to originate that evaluation design. Its narrower contribution
is a small, inspectable PHP/Laravel/WordPress fixture suite with explicit clean
controls, machine-readable defect mechanisms, deterministic matching without
an LLM judge, and content-addressed prompts and results.

SEVRA-BENCH already evaluates security review decisions and benign false
declines under adversarial PR narratives. It differs from WebFixBench in its
approve/reject unit, adversarial social-engineering focus and ground-truth
construction. The paper and repository/dataset describe different published
counts, so this document reports them separately rather than collapsing them.

This comparison supports no “first”, “only”, “unique”, or “first PHP
benchmark” claim. It also does not establish real-world validity for
WebFixBench: the current suite is synthetic, small, and has one human
ground-truth review.

## Verification log

| Project | Sources checked | Verified |
| --- | --- | --- |
| SWE-bench | paper, official repository, project site | 2026-09-20 |
| SEC-bench | paper, official repository, project site | 2026-09-20 |
| SecCodeBench | paper, official repository, project site | 2026-09-20 |
| Code Review Bench | official repository (including offline methodology), project site | 2026-09-20 |
| SEVRA-BENCH | paper, official repository, official dataset card | 2026-09-20 |

The verification pass also searched for directly relevant LLM code-review,
security pull-request, vulnerability-review, PHP, Laravel and WordPress
benchmarks. No additional project was added without enough primary-source
evidence to populate the comparison fields conservatively.
