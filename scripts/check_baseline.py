#!/usr/bin/env python3
"""Check that the committed mock baseline still matches a fresh mock run.

The mock provider is deterministic, so its predictions must not drift when the
engine, the prompt or a case changes without the baseline being regenerated.
Fields that legitimately differ between runs (run id, timestamp, latency) are
ignored.

Usage:  python scripts/check_baseline.py
Regenerate:
    webfixbench run --provider mock --out results/mock-baseline.json --quiet
    webfixbench report results/mock-baseline.json --out results/mock-baseline.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from webfixbench.cases import load_suite  # noqa: E402
from webfixbench.config import load_prompt  # noqa: E402
from webfixbench.providers.mock import MockProvider  # noqa: E402
from webfixbench.runner import run_suite  # noqa: E402

BASELINE = ROOT / "results" / "mock-baseline.json"


def comparable(document: dict) -> dict:
    """Strip the fields that are expected to differ between runs."""
    return {
        "suite": document["run"]["suite"],
        "prompt": document["run"]["prompt"],
        "provider": document["run"]["provider"],
        "responses": [
            {
                "case_id": response["case_id"],
                "valid": response["valid"],
                "parsed": response["parsed"],
                "usage": response["usage"],
                "validation_errors": response["validation_errors"],
            }
            for response in document["responses"]
        ],
    }


def main() -> int:
    if not BASELINE.is_file():
        print(f"error: {BASELINE} is missing", file=sys.stderr)
        return 1

    committed = json.loads(BASELINE.read_text(encoding="utf-8"))
    suite = load_suite(committed["run"]["suite"]["id"], root=ROOT)
    prompt_id = committed["run"]["prompt"]["id"]
    fresh = run_suite(suite, MockProvider(), load_prompt(prompt_id, root=ROOT))

    if comparable(committed) == comparable(fresh):
        print(f"ok: {BASELINE.relative_to(ROOT)} matches a fresh mock run "
              f"({len(fresh['responses'])} cases)")
        return 0

    print(
        f"error: {BASELINE.relative_to(ROOT)} is out of date.\n"
        "The mock provider, the prompt or the suite changed. Regenerate with:\n"
        "  webfixbench run --provider mock --out results/mock-baseline.json --quiet\n"
        "  webfixbench report results/mock-baseline.json --out results/mock-baseline.md",
        file=sys.stderr,
    )
    committed_by_case = {r["case_id"]: r["parsed"] for r in committed["responses"]}
    for response in fresh["responses"]:
        case_id = response["case_id"]
        if committed_by_case.get(case_id) != response["parsed"]:
            print(f"  differs: {case_id}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
