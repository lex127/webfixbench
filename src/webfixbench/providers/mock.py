"""Deterministic offline reviewer used for pipeline testing.

The mock provider is **not a model and not a baseline for model quality**. It is
a small rule-based stub whose only jobs are to exercise the full pipeline
offline and to give contributors a reproducible, non-trivial result file to
develop metrics against.

Its behaviour is intentionally imperfect: it misses some defects and reports
some findings that are not in the ground truth, so that precision, recall and
false-alarm metrics are visibly exercised rather than always reading 1.0.
Output depends only on the prompt text and the case id, so a run is bit-for-bit
reproducible.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseProvider, ProviderError, ProviderResult

MOCK_MODES = ("heuristic", "empty", "oracle_free", "malformed")

#: Rules are applied to lines added by the diff. Each entry is
#: ``(category, defect_type, severity, confidence, pattern, message)``.
_ADDED_LINE_RULES: Tuple[Tuple[str, str, str, float, "re.Pattern[str]", str], ...] = (
    (
        "unsafe_deserialization",
        "unsafe_deserialization",
        "high",
        0.82,
        re.compile(r"\bunserialize\s*\("),
        "Added call to unserialize() on data that is not shown to be trusted.",
    ),
    (
        "injection",
        "sql_injection",
        "high",
        0.80,
        re.compile(r"(DB::(raw|select|statement)|whereRaw|mysqli_query|->query\s*\()"),
        "Raw SQL is built here; check that no request data reaches the statement unparameterised.",
    ),
    (
        "injection",
        "sql_injection",
        "high",
        0.74,
        re.compile(r"\$wpdb->(query|get_results|get_row|get_var)\s*\(\s*[\"'].*\$"),
        "SQL string interpolates a variable instead of using $wpdb->prepare().",
    ),
    (
        "xss",
        "xss_unescaped_output",
        "high",
        0.78,
        re.compile(r"\{!!"),
        "Unescaped Blade output ({!! !!}) renders a value without escaping.",
    ),
    (
        "xss",
        "xss_unescaped_output",
        "medium",
        0.70,
        re.compile(r"\b(echo|print)\s+\$(_GET|_POST|_REQUEST)"),
        "Request data is echoed without escaping.",
    ),
    (
        "secrets",
        "hardcoded_secret",
        "high",
        0.85,
        re.compile(
            r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token|private[_-]?key)"
            r"[\"']?\s*(=>|=|:)\s*[\"'][^\"']{6,}[\"']"
        ),
        "A credential-looking literal is committed in source.",
    ),
)

#: Rules applied to lines removed by the diff (a guard disappearing is itself
#: the defect in several authorization cases).
_REMOVED_LINE_RULES: Tuple[Tuple[str, str, str, float, "re.Pattern[str]", str], ...] = (
    (
        "authorization",
        "authorization_policy_removed",
        "high",
        0.76,
        re.compile(r"(->authorize\s*\(|Gate::|\bpolicy\s*\(|can\s*\(\s*['\"])"),
        "An authorization check was removed from this path.",
    ),
    (
        "authorization",
        "authorization_capability_missing",
        "high",
        0.72,
        re.compile(r"(current_user_can|check_ajax_referer|wp_verify_nonce)"),
        "A capability or nonce check was removed from this handler.",
    ),
    (
        "authorization",
        "authorization_middleware_removed",
        "medium",
        0.68,
        re.compile(r"middleware\s*\(\s*\[?\s*['\"](auth|can:|verified)"),
        "Auth middleware was removed from this route.",
    ),
)

#: A deterministic distractor the stub sometimes reports, so that false
#: positives (including on clean controls) appear in mock baselines.
_DISTRACTOR = (
    "xss",
    "xss_unescaped_output",
    "low",
    0.31,
    "Output in this change may need escaping; not confirmed from the supplied diff.",
)


def _stable_unit(case_id: str, salt: str) -> float:
    """Return a stable pseudo-random float in [0, 1) for a case/salt pair."""
    digest = hashlib.sha256(f"{case_id}:{salt}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _extract_diff(prompt: str) -> str:
    """Pull the diff out of a rendered prompt, falling back to the whole text."""
    marker = "BEGIN DIFF"
    end_marker = "END DIFF"
    start = prompt.find(marker)
    end = prompt.find(end_marker)
    if start != -1 and end > start:
        return prompt[start + len(marker) : end]
    return prompt


def _current_file(diff_line: str, current: Optional[str]) -> Optional[str]:
    if diff_line.startswith("+++ "):
        path = diff_line[4:].strip()
        if path in ("/dev/null", ""):
            return current
        if path.startswith(("a/", "b/")):
            path = path[2:]
        return path
    return current


class MockProvider(BaseProvider):
    """Offline rule-based reviewer (deterministic, no network)."""

    name = "mock"
    default_model = "mock-heuristic-v1"

    def __init__(self, model: Optional[str] = None, *, mode: str = "heuristic", **kwargs: Any):
        super().__init__(model, **kwargs)
        if mode not in MOCK_MODES:
            raise ProviderError(f"unknown mock mode {mode!r}; expected one of {list(MOCK_MODES)}")
        self.mode = mode
        self.extra.setdefault("mock_mode", mode)

    def describe(self) -> Dict[str, Any]:
        description = super().describe()
        description["mock_mode"] = self.mode
        description["note"] = (
            "Deterministic rule-based stub. Not a language model; its scores say "
            "nothing about any model's review quality."
        )
        return description

    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        if self.mode == "malformed":
            return ProviderResult(
                raw_text="I looked at the diff and it seems fine to me.",
                latency_ms=0.0,
                model=self.model,
                usage=self._usage(prompt, ""),
            )
        if self.mode == "empty":
            payload = {"findings": [], "overall_confidence": 0.5}
        else:
            payload = self._analyse(prompt, case_id)

        text = json.dumps(payload, indent=2, sort_keys=False)
        return ProviderResult(
            raw_text=text,
            latency_ms=0.0,
            model=self.model,
            usage=self._usage(prompt, text),
        )

    # -- internals -------------------------------------------------------

    def _analyse(self, prompt: str, case_id: str) -> Dict[str, Any]:
        diff = _extract_diff(prompt)
        findings: List[Dict[str, Any]] = []
        current_file: Optional[str] = None
        seen: set = set()

        for line in diff.splitlines():
            current_file = _current_file(line, current_file)
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                rules = _ADDED_LINE_RULES
            elif line.startswith("-"):
                rules = _REMOVED_LINE_RULES
            else:
                continue
            body = line[1:]
            for category, defect_type, severity, base_confidence, pattern, message in rules:
                if not pattern.search(body):
                    continue
                key = (category, current_file)
                if key in seen:
                    continue
                seen.add(key)
                jitter = (_stable_unit(case_id, category) - 0.5) * 0.08
                findings.append(
                    {
                        "category": category,
                        "defect_type": defect_type,
                        "severity": severity,
                        "file": current_file,
                        "line": None,
                        "description": message,
                        "confidence": round(min(0.97, max(0.05, base_confidence + jitter)), 2),
                    }
                )

        # `oracle_free` keeps only the rule hits; `heuristic` additionally emits
        # a deterministic distractor on a fixed subset of cases.
        if self.mode == "heuristic" and _stable_unit(case_id, "distractor") < 0.25:
            category, defect_type, severity, confidence, message = _DISTRACTOR
            if not any(f["category"] == category for f in findings):
                findings.append(
                    {
                        "category": category,
                        "defect_type": defect_type,
                        "severity": severity,
                        "file": current_file,
                        "line": None,
                        "description": message,
                        "confidence": confidence,
                    }
                )

        if findings:
            overall = round(sum(f["confidence"] for f in findings) / len(findings), 2)
        else:
            overall = round(0.55 + 0.3 * _stable_unit(case_id, "clean"), 2)

        return {"findings": findings, "overall_confidence": overall}

    @staticmethod
    def _usage(prompt: str, output: str) -> Dict[str, Any]:
        """Report a coarse, clearly-labelled token estimate (no tokenizer)."""
        approx_in = max(1, len(prompt) // 4)
        approx_out = max(1, len(output) // 4)
        return {
            "input_tokens": approx_in,
            "output_tokens": approx_out,
            "total_tokens": approx_in + approx_out,
            "estimated": True,
        }
