"""Running a suite (or a single case) against a provider.

The runner produces a *result file*: raw provider output plus run metadata,
with no scoring applied. Scoring happens later in :mod:`webfixbench.evaluator`,
so a single (possibly paid) run can be re-scored under different matching rules
without calling any model again.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import __version__
from .cases import Case, Suite
from .config import Prompt, PricingTable
from .providers.base import BaseProvider
from .schemas import ValidationError, parse_model_response

#: Bumped when the result-file layout changes in a backwards-incompatible way.
RESULTS_FORMAT_VERSION = 1


@dataclass
class CaseResult:
    """The stored outcome of reviewing one case."""

    case_id: str
    valid: bool
    latency_ms: float
    model: str
    usage: Optional[Dict[str, Any]] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    raw: Optional[str] = None
    parsed: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_prompt_text(prompt: Prompt, case: Case) -> str:
    """Render the frozen prompt for a case."""
    return prompt.render(
        case_description=case.description,
        diff=case.diff,
        context=case.context,
    )


def run_cases(
    cases: Sequence[Case],
    provider: BaseProvider,
    prompt: Prompt,
    *,
    suite: Optional[Suite] = None,
    pricing: Optional[PricingTable] = None,
    store_raw: bool = True,
    progress: Optional[Callable[[int, int, Case], None]] = None,
) -> Dict[str, Any]:
    """Review every case and return a result document.

    Provider and parsing failures are recorded per case; the run continues.
    """
    pricing = pricing or PricingTable.empty()
    results: List[CaseResult] = []

    for index, case in enumerate(cases, start=1):
        if progress:
            progress(index, len(cases), case)

        rendered = build_prompt_text(prompt, case)
        outcome = provider.review(rendered, case_id=case.id)

        result = CaseResult(
            case_id=case.id,
            valid=False,
            latency_ms=outcome.latency_ms,
            model=outcome.model,
            usage=outcome.usage,
            cost_usd=pricing.cost_usd(outcome.model, outcome.usage),
            error=outcome.error,
            raw=outcome.raw_text if store_raw else None,
            metadata=dict(outcome.metadata),
        )

        if outcome.ok and outcome.raw_text is not None:
            try:
                parsed = parse_model_response(outcome.raw_text)
            except ValidationError as exc:
                result.validation_errors = list(exc.errors)
            else:
                result.valid = True
                result.parsed = parsed.to_dict()
        elif result.error is None:
            result.error = "provider returned no text"

        results.append(result)

    document: Dict[str, Any] = {
        "webfixbench_version": __version__,
        "results_format_version": RESULTS_FORMAT_VERSION,
        "run": {
            "run_id": uuid.uuid4().hex[:12],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "suite": {
                "id": suite.id if suite else None,
                "version": suite.version if suite else None,
                "case_count": len(suite) if suite else None,
            },
            "cases_run": [c.id for c in cases],
            "prompt": {"id": prompt.id, "sha256": prompt.sha256},
            "provider": provider.describe(),
            "pricing": (
                {"as_of": pricing.as_of, "source": pricing.source} if pricing.models else None
            ),
        },
        "responses": [r.to_dict() for r in results],
    }
    return document


def run_suite(
    suite: Suite,
    provider: BaseProvider,
    prompt: Prompt,
    *,
    case_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    pricing: Optional[PricingTable] = None,
    store_raw: bool = True,
    progress: Optional[Callable[[int, int, Case], None]] = None,
) -> Dict[str, Any]:
    """Run all (or a subset of) the cases in ``suite``."""
    cases: List[Case] = list(suite.cases)
    if case_ids:
        selected = []
        for case_id in case_ids:
            try:
                selected.append(suite.get(case_id))
            except KeyError:
                raise KeyError(f"case {case_id!r} is not in suite {suite.id!r}")
        cases = selected
    if limit is not None:
        cases = cases[:limit]

    return run_cases(
        cases,
        provider,
        prompt,
        suite=suite,
        pricing=pricing,
        store_raw=store_raw,
        progress=progress,
    )


def write_results(document: Dict[str, Any], path: Path) -> Path:
    """Write a result document as pretty-printed JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def read_results(path: Path) -> Dict[str, Any]:
    """Read a result document and check its format version."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    version = document.get("results_format_version")
    if version != RESULTS_FORMAT_VERSION:
        raise ValueError(
            f"{path}: unsupported results_format_version {version!r} "
            f"(this build reads version {RESULTS_FORMAT_VERSION})"
        )
    return document
