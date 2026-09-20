"""OpenAI provider (Chat Completions API over HTTPS).

The model id is never defaulted: vendor line-ups change, and a stale hardcoded
default would silently misreport what was benchmarked. Pass ``--model`` and the
exact id is recorded in the result file.

Reads ``OPENAI_API_KEY`` from the environment. Tests never call this provider.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import ENV_OPENAI_KEY
from ._http import HttpError, post_json
from .base import BaseProvider, ProviderError, ProviderResult

API_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a precise code reviewer. Reply with a single JSON object and nothing else."
)


class OpenAIProvider(BaseProvider):
    """Review a diff with an OpenAI chat model."""

    name = "openai"

    def __init__(self, model: Optional[str] = None, **kwargs: Any) -> None:
        if not model:
            raise ProviderError(
                "the openai provider requires an explicit --model "
                "(WebFixBench does not pin vendor model ids)"
            )
        super().__init__(model, **kwargs)
        self.api_key = os.environ.get(ENV_OPENAI_KEY)
        if not self.api_key:
            raise ProviderError(
                f"{ENV_OPENAI_KEY} is not set; export it or use --provider mock"
            )
        self.api_url = self.extra.get("api_url", API_URL)

    def _payload(self, prompt: str) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_completion_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
        }

    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        payload = self._payload(prompt)
        headers = {"authorization": f"Bearer {self.api_key}"}

        try:
            body, _ = post_json(self.api_url, payload, headers, timeout=self.timeout)
        except HttpError as exc:
            retry_payload = _drop_unsupported_params(payload, exc)
            if retry_payload is None:
                return ProviderResult(
                    raw_text=None, latency_ms=0.0, model=self.model, error=str(exc)
                )
            try:
                body, _ = post_json(self.api_url, retry_payload, headers, timeout=self.timeout)
            except HttpError as retry_exc:
                return ProviderResult(
                    raw_text=None, latency_ms=0.0, model=self.model, error=str(retry_exc)
                )

        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ProviderResult(
                raw_text=None,
                latency_ms=0.0,
                model=self.model,
                error="unexpected response shape from OpenAI API",
            )

        usage_doc = body.get("usage") or {}
        usage = {
            "input_tokens": usage_doc.get("prompt_tokens"),
            "output_tokens": usage_doc.get("completion_tokens"),
            "total_tokens": usage_doc.get("total_tokens"),
            "estimated": False,
        }
        return ProviderResult(
            raw_text=text,
            latency_ms=0.0,
            model=body.get("model", self.model),
            usage=usage,
            metadata={"finish_reason": body["choices"][0].get("finish_reason")},
        )


def _drop_unsupported_params(
    payload: Dict[str, Any], error: HttpError
) -> Optional[Dict[str, Any]]:
    """Retry helper for model-specific parameter support.

    Some models reject ``temperature`` or expect ``max_tokens`` rather than
    ``max_completion_tokens``. When the API says a parameter is unsupported,
    retry once with that parameter adjusted instead of losing the whole run.
    """
    if error.status != 400:
        return None
    detail = error.body.lower()
    retry = dict(payload)
    changed = False

    if "temperature" in detail and "temperature" in retry:
        retry.pop("temperature")
        changed = True
    if "max_completion_tokens" in detail and "max_completion_tokens" in retry:
        retry["max_tokens"] = retry.pop("max_completion_tokens")
        changed = True
    if "response_format" in detail and "response_format" in retry:
        retry.pop("response_format")
        changed = True

    return retry if changed else None
