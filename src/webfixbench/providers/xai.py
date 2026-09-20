"""xAI Responses API provider using its dedicated endpoint and key."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import ENV_XAI_KEY
from ._http import HttpError, post_json, redact, token_usage
from .base import RESPONSE_JSON_SCHEMA, BaseProvider, ProviderError, ProviderResult

API_URL = "https://api.x.ai/v1/responses"
OUTPUT_CONSTRAINTS = ("json_schema", "json_object", "prompt_only")
REASONING_EFFORTS = ("low", "medium", "high", "xhigh")
SYSTEM_PROMPT = "You are a precise code reviewer. Reply with a single JSON object and nothing else."


class XAIProvider(BaseProvider):
    name = "xai"

    def __init__(self, model: Optional[str] = None, *, output_constraint: str = "json_schema",
                 reasoning_effort: Optional[str] = None, **kwargs: Any) -> None:
        if not model:
            raise ProviderError("the xai provider requires an explicit --model")
        if output_constraint not in OUTPUT_CONSTRAINTS:
            raise ProviderError(f"unsupported xAI output constraint {output_constraint!r}")
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ProviderError(f"unsupported xAI reasoning_effort {reasoning_effort!r}")
        super().__init__(model, **kwargs)
        self.output_constraint = output_constraint
        self.reasoning_effort = reasoning_effort
        self.api_key = os.environ.get(ENV_XAI_KEY)
        if not self.api_key:
            raise ProviderError(f"{ENV_XAI_KEY} is not set; export it or use --provider mock")

    def describe(self) -> Dict[str, Any]:
        result = super().describe()
        result.update({"api_type": "responses", "endpoint": API_URL,
                       "output_constraint": self.output_constraint})
        sent: Dict[str, Any] = {"model": self.model, "max_output_tokens": self.max_output_tokens,
                                "store": False}
        if self.temperature is not None:
            sent["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            sent["reasoning"] = {"effort": self.reasoning_effort}
        result["settings_sent"] = sent
        if self.reasoning_effort is not None:
            result["reasoning"] = {"effort": self.reasoning_effort}
        return result

    def _payload(self, prompt: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "input": [{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}],
            "max_output_tokens": self.max_output_tokens,
            "store": False,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.output_constraint != "prompt_only":
            fmt: Dict[str, Any] = {"type": self.output_constraint}
            if self.output_constraint == "json_schema":
                fmt.update({"name": "webfixbench_review", "strict": True,
                            "schema": RESPONSE_JSON_SCHEMA})
            payload["text"] = {"format": fmt}
        return payload

    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        try:
            body, _ = post_json(API_URL, self._payload(prompt),
                                {"authorization": f"Bearer {self.api_key}"}, timeout=self.timeout)
        except HttpError as exc:
            return ProviderResult(None, 0.0, self.model, error=redact(str(exc), self.api_key))
        text = _response_text(body)
        if not text:
            return ProviderResult(None, 0.0, self.model,
                                  error="xAI Responses API response contained no output text")
        return ProviderResult(text, 0.0, body.get("model", self.model),
                              usage=token_usage(body.get("usage"), style="responses"),
                              metadata={"api_type": "responses", "output_constraint": self.output_constraint,
                                        "status": body.get("status")})


def _response_text(body: Dict[str, Any]) -> Optional[str]:
    for item in body.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "message":
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    return content.get("text")
    return None
