"""Anthropic provider (Messages API over HTTPS).

As with the OpenAI provider, the model id is never defaulted: pass ``--model``
and the exact id used is recorded in the result file.

Reads ``ANTHROPIC_API_KEY`` from the environment. Tests never call this provider.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import ENV_ANTHROPIC_KEY
from ._http import HttpError, post_json
from .base import RESPONSE_JSON_SCHEMA, BaseProvider, ProviderError, ProviderResult

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

SYSTEM_PROMPT = (
    "You are a precise code reviewer. Reply with a single JSON object and nothing else."
)


OUTPUT_CONSTRAINTS = ("json_schema", "prompt_only")


class AnthropicProvider(BaseProvider):
    """Review a diff with an Anthropic model."""

    name = "anthropic"

    def __init__(
        self,
        model: Optional[str] = None,
        *,
        output_constraint: str = "json_schema",
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
        super().__init__(model, **kwargs)
        self.output_constraint = output_constraint
        self.api_key = os.environ.get(ENV_ANTHROPIC_KEY)
        if not self.api_key:
            raise ProviderError(
                f"{ENV_ANTHROPIC_KEY} is not set; export it or use --provider mock"
            )
        self.api_url = self.extra.get("api_url", API_URL)
        self.api_version = self.extra.get("api_version", API_VERSION)

    def describe(self) -> Dict[str, Any]:
        description = super().describe()
        description.update(
            {
                "api_type": "messages",
                "endpoint": self.api_url,
                "output_constraint": self.output_constraint,
            }
        )
        return description

    def _payload(self, prompt: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.output_constraint == "json_schema":
            payload["output_config"] = {
                "format": {"type": "json_schema", "schema": RESPONSE_JSON_SCHEMA}
            }
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
            return ProviderResult(raw_text=None, latency_ms=0.0, model=self.model, error=str(exc))

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
        total = None
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            total = input_tokens + output_tokens
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
            "estimated": False,
        }
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
