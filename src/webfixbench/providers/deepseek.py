"""DeepSeek Chat Completions provider using documented DeepSeek parameters."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import ENV_DEEPSEEK_KEY
from ._http import HttpError, post_json, redact, token_usage
from .base import BaseProvider, ProviderError, ProviderResult

API_URL = "https://api.deepseek.com/chat/completions"
OUTPUT_CONSTRAINTS = ("json_object", "prompt_only")
REASONING_EFFORTS = ("none", "low", "high", "max")
SYSTEM_PROMPT = "You are a precise code reviewer. Return one valid JSON object and nothing else."


class DeepSeekProvider(BaseProvider):
    name = "deepseek"

    def __init__(self, model: Optional[str] = None, *, output_constraint: str = "json_object",
                 reasoning_effort: Optional[str] = None, **kwargs: Any) -> None:
        if not model:
            raise ProviderError("the deepseek provider requires an explicit --model")
        if output_constraint not in OUTPUT_CONSTRAINTS:
            raise ProviderError("DeepSeek supports json_object or prompt_only, not json_schema")
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ProviderError(f"unsupported DeepSeek reasoning_effort {reasoning_effort!r}")
        temperature = kwargs.get("temperature")
        if reasoning_effort not in (None, "none") and temperature is not None:
            raise ProviderError("DeepSeek temperature is unsupported in thinking mode")
        super().__init__(model, **kwargs)
        self.output_constraint = output_constraint
        self.reasoning_effort = reasoning_effort
        self.api_key = os.environ.get(ENV_DEEPSEEK_KEY)
        if not self.api_key:
            raise ProviderError(f"{ENV_DEEPSEEK_KEY} is not set; export it or use --provider mock")

    def describe(self) -> Dict[str, Any]:
        result = super().describe()
        result.update({"api_type": "chat.completions", "endpoint": API_URL,
                       "output_constraint": self.output_constraint})
        sent: Dict[str, Any] = {"model": self.model, "max_tokens": self.max_output_tokens,
                                "stream": False}
        if self.reasoning_effort is not None:
            sent.update({"reasoning_effort": self.reasoning_effort,
                         "thinking": {"type": "disabled" if self.reasoning_effort == "none" else "enabled"}})
        if self.reasoning_effort == "none" and self.temperature is not None:
            sent["temperature"] = self.temperature
        result["settings_sent"] = sent
        if self.reasoning_effort is not None:
            result["reasoning"] = {"effort": self.reasoning_effort}
        return result

    def _payload(self, prompt: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": prompt}],
            "max_tokens": self.max_output_tokens,
            "stream": False,
        }
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
            payload["thinking"] = {"type": "disabled" if self.reasoning_effort == "none" else "enabled"}
        if self.reasoning_effort == "none" and self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.output_constraint == "json_object":
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        try:
            body, _ = post_json(API_URL, self._payload(prompt),
                                {"authorization": f"Bearer {self.api_key}"}, timeout=self.timeout)
        except HttpError as exc:
            return ProviderResult(None, 0.0, self.model, error=redact(str(exc), self.api_key))
        try:
            message = body["choices"][0]["message"]
            text = message["content"]
        except (KeyError, IndexError, TypeError):
            text = None
            message = {}
        if not isinstance(text, str) or not text:
            return ProviderResult(None, 0.0, self.model,
                                  error="DeepSeek Chat Completions response contained no text")
        metadata: Dict[str, Any] = {"api_type": "chat.completions",
                                    "output_constraint": self.output_constraint,
                                    "finish_reason": (body.get("choices") or [{}])[0].get("finish_reason")}
        if message.get("reasoning_content") is not None:
            metadata["reasoning_content_available"] = True
        return ProviderResult(text, 0.0, body.get("model", self.model),
                              usage=token_usage(body.get("usage"), style="chat"), metadata=metadata)
