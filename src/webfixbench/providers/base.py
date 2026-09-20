"""Provider abstraction.

The benchmark engine talks to reviewers exclusively through
:class:`BaseProvider`. Nothing in ``runner``, ``evaluator`` or ``metrics``
imports vendor code, so adding a provider never requires touching the engine.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


RESPONSE_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "defect_type", "severity", "file", "line", "description", "confidence"],
                "properties": {
                    "category": {"type": "string"},
                    "defect_type": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "file": {"type": ["string", "null"]},
                    "line": {"type": ["integer", "null"]},
                    "description": {"type": "string"},
                    "confidence": {"type": ["number", "null"], "minimum": 0.0, "maximum": 1.0},
                },
            },
        },
        "overall_confidence": {
            "type": ["number", "null"],
            "minimum": 0.0,
            "maximum": 1.0,
        },
    },
    "required": ["findings", "overall_confidence"],
}


class ProviderError(RuntimeError):
    """Raised when a provider cannot be constructed or configured.

    Transport and API failures during a run are *not* raised: they are recorded
    on :class:`ProviderResult` so that one failing case does not discard a run.
    """


@dataclass
class ProviderResult:
    """The raw outcome of a single review call."""

    raw_text: Optional[str]
    latency_ms: float
    model: str
    usage: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.raw_text)


class BaseProvider(ABC):
    """Base class for reviewers.

    Subclasses implement :meth:`_review` and must not raise on remote failures;
    returning a :class:`ProviderResult` with ``error`` set is the contract.
    """

    #: Short provider id used on the CLI and recorded in result files.
    name: str = "base"

    #: Model used when the caller does not specify one.
    default_model: str = "unspecified"

    def __init__(
        self,
        model: Optional[str] = None,
        *,
        temperature: float = 0.0,
        max_output_tokens: int = 2048,
        timeout: float = 120.0,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.model = model or self.default_model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.timeout = timeout
        self.extra: Dict[str, Any] = dict(extra or {})

    # -- public API ------------------------------------------------------

    def review(self, prompt: str, *, case_id: str) -> ProviderResult:
        """Run one review and measure wall-clock latency."""
        started = time.perf_counter()
        try:
            result = self._review(prompt, case_id=case_id)
        except Exception as exc:  # pragma: no cover - defensive
            elapsed = (time.perf_counter() - started) * 1000.0
            return ProviderResult(
                raw_text=None,
                latency_ms=round(elapsed, 3),
                model=self.model,
                error=f"{type(exc).__name__}: {exc}",
            )
        elapsed = (time.perf_counter() - started) * 1000.0
        if result.latency_ms <= 0:
            result.latency_ms = round(elapsed, 3)
        return result

    def describe(self) -> Dict[str, Any]:
        """Settings recorded in the run metadata for reproducibility."""
        return {
            "provider": self.name,
            "model": self.model,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            **({"settings": self.extra} if self.extra else {}),
        }

    # -- to implement ----------------------------------------------------

    @abstractmethod
    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        """Return the reviewer's raw response for ``prompt``."""
        raise NotImplementedError
