"""Anthropic provider (Messages API over HTTPS).

As with the OpenAI provider, the model id is never defaulted: pass ``--model``
and the exact id used is recorded in the result file.

Reads ``ANTHROPIC_API_KEY`` from the environment. Tests never call this provider.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import ENV_ANTHROPIC_KEY
from ._http import HttpError, post_json, redact
from .base import RESPONSE_JSON_SCHEMA, BaseProvider, ProviderError, ProviderResult

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

SYSTEM_PROMPT = (
    "You are a precise code reviewer. Reply with a single JSON object and nothing else."
)


OUTPUT_CONSTRAINTS = ("json_schema", "prompt_only")
THINKING_MODES = ("disabled", "adaptive")
REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max")


class AnthropicProvider(BaseProvider):
    """Review a diff with an Anthropic model."""

    name = "anthropic"

    def __init__(
        self,
        model: Optional[str] = None,
        *,
        output_constraint: str = "json_schema",
        thinking_mode: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if not model:
            raise ProviderError(
                "the anthropic provider requires an explicit --model "
                "(WebFixBench does not pin vendor model ids)"
            )
        if output_constraint not in OUTPUT_CONSTRAINTS:
            raise ProviderError(
                f"unknown output constraint {output_constraint!r}; expected {list(OUTPUT_CONSTRAINTS)}"
            )
        if "fable" in model.lower():
            raise ProviderError("Fable models are excluded by WebFixBench owner policy")
        if thinking_mode is not None and thinking_mode not in THINKING_MODES:
            raise ProviderError(f"unsupported Anthropic thinking_mode {thinking_mode!r}")
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ProviderError(f"unsupported Anthropic reasoning_effort {reasoning_effort!r}")
        if reasoning_effort is not None and thinking_mode != "adaptive":
            raise ProviderError("Anthropic reasoning_effort requires thinking_mode='adaptive'")
        if model == "claude-sonnet-5" and kwargs.get("temperature") is not None:
            raise ProviderError("claude-sonnet-5 requests must omit temperature")
        super().__init__(model, **kwargs)
        self.output_constraint = output_constraint
        self.thinking_mode = thinking_mode
        self.reasoning_effort = reasoning_effort
        self.api_key = os.environ.get(ENV_ANTHROPIC_KEY)
        if not self.api_key:
            raise ProviderError(
                f"{ENV_ANTHROPIC_KEY} is not set; export it or use --provider mock"
            )
        self.api_url = API_URL
        self.api_version = API_VERSION

    def describe(self) -> Dict[str, Any]:
        description = super().describe()
        description.update(
            {
                "api_type": "messages",
                "endpoint": self.api_url,
                "output_constraint": self.output_constraint,
            }
        )
        sent: Dict[str, Any] = {"model": self.model, "max_tokens": self.max_output_tokens}
        if self.temperature is not None:
            sent["temperature"] = self.temperature
        if self.thinking_mode is not None:
            sent["thinking"] = {"type": self.thinking_mode}
        if self.reasoning_effort is not None:
            sent["output_config.effort"] = self.reasoning_effort
        description["settings_sent"] = sent
        if self.thinking_mode is not None:
            description["thinking"] = {"type": self.thinking_mode}
        if self.reasoning_effort is not None:
            description["reasoning"] = {"effort": self.reasoning_effort}
        return description

    def _payload(self, prompt: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.thinking_mode is not None:
            payload["thinking"] = {"type": self.thinking_mode}
        if self.output_constraint == "json_schema":
            payload["output_config"] = {
                "format": {"type": "json_schema", "schema": RESPONSE_JSON_SCHEMA}
            }
        if self.reasoning_effort is not None:
            payload.setdefault("output_config", {})["effort"] = self.reasoning_effort
        return payload

    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        payload = self._payload(prompt)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
        }

        try:
            body, _ = post_json(self.api_url, payload, headers, timeout=self.timeout)
        except HttpError as exc:
            return ProviderResult(raw_text=None, latency_ms=0.0, model=self.model,
                                  error=redact(str(exc), self.api_key))

        blocks = body.get("content") or []
        text = "".join(
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text:
            return ProviderResult(
                raw_text=None,
                latency_ms=0.0,
                model=self.model,
                error="Anthropic response contained no text block",
            )

        usage_doc = body.get("usage") or {}
        input_tokens = usage_doc.get("input_tokens")
        output_tokens = usage_doc.get("output_tokens")
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": None,
            "estimated": False,
        }
        for name in ("cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens_details"):
            if name in usage_doc:
                usage[name] = usage_doc[name]
        return ProviderResult(
            raw_text=text,
            latency_ms=0.0,
            model=body.get("model", self.model),
            usage=usage,
            metadata={
                "stop_reason": body.get("stop_reason"),
                "api_type": "messages",
                "output_constraint": self.output_constraint,
            },
        )
