"""OpenAI provider supporting Responses and explicit Chat Completions."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import ENV_OPENAI_KEY
from ._http import HttpError, post_json, redact, token_usage
from .base import RESPONSE_JSON_SCHEMA, BaseProvider, ProviderError, ProviderResult

API_URLS = {
    "responses": "https://api.openai.com/v1/responses",
    "chat.completions": "https://api.openai.com/v1/chat/completions",
}
API_TYPES = tuple(API_URLS)
OUTPUT_CONSTRAINTS = ("json_schema", "json_object", "prompt_only")
REASONING_EFFORTS = ("low", "medium", "high", "xhigh", "max")
SYSTEM_PROMPT = "You are a precise code reviewer. Reply with a single JSON object and nothing else."


class OpenAIProvider(BaseProvider):
    """Review through Responses by default, without guessing model support."""

    name = "openai"

    def __init__(
        self,
        model: Optional[str] = None,
        *,
        api_type: str = "responses",
        output_constraint: str = "json_schema",
        reasoning_effort: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if not model:
            raise ProviderError("the openai provider requires an explicit --model")
        if api_type not in API_TYPES:
            raise ProviderError(f"unknown OpenAI API type {api_type!r}; expected {list(API_TYPES)}")
        if output_constraint not in OUTPUT_CONSTRAINTS:
            raise ProviderError(
                f"unknown output constraint {output_constraint!r}; expected {list(OUTPUT_CONSTRAINTS)}"
            )
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ProviderError(f"unsupported OpenAI reasoning_effort {reasoning_effort!r}")
        if reasoning_effort is not None and kwargs.get("temperature", 0.0) != 0.0:
            raise ProviderError("OpenAI temperature is not sent with explicit reasoning_effort")
        super().__init__(model, **kwargs)
        self.api_type = api_type
        self.output_constraint = output_constraint
        self.reasoning_effort = reasoning_effort
        self.api_key = os.environ.get(ENV_OPENAI_KEY)
        if not self.api_key:
            raise ProviderError(f"{ENV_OPENAI_KEY} is not set; export it or use --provider mock")
        self.api_url = API_URLS[api_type]

    def describe(self) -> Dict[str, Any]:
        description = super().describe()
        description.update(
            {"api_type": self.api_type, "endpoint": self.api_url, "output_constraint": self.output_constraint}
        )
        sent: Dict[str, Any] = {"model": self.model,
            "max_output_tokens" if self.api_type == "responses" else "max_completion_tokens": self.max_output_tokens}
        if self.temperature != 0.0:
            sent["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            sent["reasoning" if self.api_type == "responses" else "reasoning_effort"] = (
                {"effort": self.reasoning_effort} if self.api_type == "responses" else self.reasoning_effort)
        description["settings_sent"] = sent
        if self.reasoning_effort is not None:
            description["reasoning"] = {"effort": self.reasoning_effort}
        return description

    def _payload(self, prompt: str) -> Dict[str, Any]:
        if self.api_type == "responses":
            payload: Dict[str, Any] = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_output_tokens": self.max_output_tokens,
            }
            if self.temperature != 0.0:
                payload["temperature"] = self.temperature
            if self.reasoning_effort is not None:
                payload["reasoning"] = {"effort": self.reasoning_effort}
            if self.output_constraint == "json_schema":
                payload["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": "webfixbench_review",
                        "strict": True,
                        "schema": RESPONSE_JSON_SCHEMA,
                    }
                }
            elif self.output_constraint == "json_object":
                payload["text"] = {"format": {"type": "json_object"}}
            return payload

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": self.max_output_tokens,
        }
        if self.temperature != 0.0:
            payload["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        if self.output_constraint == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "webfixbench_review",
                    "strict": True,
                    "schema": RESPONSE_JSON_SCHEMA,
                },
            }
        elif self.output_constraint == "json_object":
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        payload = self._payload(prompt)
        try:
            body, _ = post_json(
                self.api_url,
                payload,
                {"authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        except HttpError as exc:
            return ProviderResult(raw_text=None, latency_ms=0.0, model=self.model,
                                  error=redact(str(exc), self.api_key))

        text = self._extract_text(body)
        if not text:
            return ProviderResult(
                raw_text=None,
                latency_ms=0.0,
                model=self.model,
                error=f"unexpected response shape from OpenAI {self.api_type} API",
            )
        return ProviderResult(
            raw_text=text,
            latency_ms=0.0,
            model=body.get("model", self.model),
            usage=token_usage(body.get("usage"), style=("responses" if self.api_type == "responses" else "chat")),
            metadata={"api_type": self.api_type, "output_constraint": self.output_constraint},
        )

    def _extract_text(self, body: Dict[str, Any]) -> Optional[str]:
        if self.api_type == "chat.completions":
            try:
                return body["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                return None
        if isinstance(body.get("output_text"), str):
            return body["output_text"]
        for item in body.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    return content.get("text")
        return None
