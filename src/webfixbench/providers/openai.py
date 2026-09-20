"""OpenAI provider supporting Responses and explicit Chat Completions."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..config import ENV_OPENAI_KEY
from ._http import HttpError, post_json
from .base import RESPONSE_JSON_SCHEMA, BaseProvider, ProviderError, ProviderResult

API_URLS = {
    "responses": "https://api.openai.com/v1/responses",
    "chat.completions": "https://api.openai.com/v1/chat/completions",
}
API_TYPES = tuple(API_URLS)
OUTPUT_CONSTRAINTS = ("json_schema", "json_object", "prompt_only")
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
        super().__init__(model, **kwargs)
        self.api_type = api_type
        self.output_constraint = output_constraint
        self.api_key = os.environ.get(ENV_OPENAI_KEY)
        if not self.api_key:
            raise ProviderError(f"{ENV_OPENAI_KEY} is not set; export it or use --provider mock")
        self.api_url = self.extra.get("api_url", API_URLS[api_type])

    def describe(self) -> Dict[str, Any]:
        description = super().describe()
        description.update(
            {"api_type": self.api_type, "endpoint": self.api_url, "output_constraint": self.output_constraint}
        )
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
            return ProviderResult(raw_text=None, latency_ms=0.0, model=self.model, error=str(exc))

        text = self._extract_text(body)
        if not text:
            return ProviderResult(
                raw_text=None,
                latency_ms=0.0,
                model=self.model,
                error=f"unexpected response shape from OpenAI {self.api_type} API",
            )
        usage_doc = body.get("usage") or {}
        if self.api_type == "responses":
            input_tokens = usage_doc.get("input_tokens")
            output_tokens = usage_doc.get("output_tokens")
        else:
            input_tokens = usage_doc.get("prompt_tokens")
            output_tokens = usage_doc.get("completion_tokens")
        return ProviderResult(
            raw_text=text,
            latency_ms=0.0,
            model=body.get("model", self.model),
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": usage_doc.get("total_tokens"),
                "estimated": False,
            },
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
