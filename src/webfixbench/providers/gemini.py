"""Google Gemini GenerateContent provider with no tools or grounding."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from ..config import ENV_GEMINI_KEY
from ._http import HttpError, post_json, redact
from .base import RESPONSE_JSON_SCHEMA, BaseProvider, ProviderError, ProviderResult

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
OUTPUT_CONSTRAINTS = ("json_schema", "json_object", "prompt_only")
REASONING_EFFORTS = ("low", "medium", "high")
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SYSTEM_PROMPT = "You are a precise code reviewer. Reply with a single JSON object and nothing else."


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, model: Optional[str] = None, *, output_constraint: str = "json_schema",
                 reasoning_effort: Optional[str] = None, **kwargs: Any) -> None:
        if not model:
            raise ProviderError("the gemini provider requires an explicit --model")
        if not MODEL_ID.fullmatch(model):
            raise ProviderError("Gemini model id contains unsupported path characters")
        if output_constraint not in OUTPUT_CONSTRAINTS:
            raise ProviderError(f"unsupported Gemini output constraint {output_constraint!r}")
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
            raise ProviderError(f"unsupported Gemini reasoning_effort {reasoning_effort!r}")
        super().__init__(model, **kwargs)
        self.output_constraint = output_constraint
        self.reasoning_effort = reasoning_effort
        self.api_key = os.environ.get(ENV_GEMINI_KEY)
        if not self.api_key:
            raise ProviderError(f"{ENV_GEMINI_KEY} is not set; export it or use --provider mock")
        self.api_url = f"{API_ROOT}/{self.model}:generateContent"

    def describe(self) -> Dict[str, Any]:
        result = super().describe()
        result.update({"api_type": "generateContent", "endpoint": self.api_url,
                       "output_constraint": self.output_constraint,
                       "tools_enabled": False, "grounding_enabled": False})
        sent: Dict[str, Any] = {"model": self.model, "maxOutputTokens": self.max_output_tokens}
        if self.temperature is not None:
            sent["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            sent["thinkingConfig"] = {"thinkingLevel": self.reasoning_effort}
        result["settings_sent"] = sent
        if self.reasoning_effort is not None:
            result["reasoning"] = {"effort": self.reasoning_effort}
        return result

    def _payload(self, prompt: str) -> Dict[str, Any]:
        generation: Dict[str, Any] = {"maxOutputTokens": self.max_output_tokens}
        if self.temperature is not None:
            generation["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            generation["thinkingConfig"] = {"thinkingLevel": self.reasoning_effort}
        if self.output_constraint != "prompt_only":
            generation["responseMimeType"] = "application/json"
            if self.output_constraint == "json_schema":
                generation["responseJsonSchema"] = RESPONSE_JSON_SCHEMA
        return {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation,
        }

    def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
        try:
            body, _ = post_json(self.api_url, self._payload(prompt),
                                {"x-goog-api-key": self.api_key}, timeout=self.timeout)
        except HttpError as exc:
            return ProviderResult(None, 0.0, self.model, error=redact(str(exc), self.api_key))
        text, finish_reason = _response_text(body)
        returned_model = body.get("modelVersion") or self.model
        if not text:
            reason = (body.get("promptFeedback") or {}).get("blockReason")
            suffix = f" (prompt blocked: {reason})" if reason else ""
            return ProviderResult(None, 0.0, returned_model,
                                  error="Gemini GenerateContent response contained no text" + suffix)
        return ProviderResult(text, 0.0, returned_model, usage=_usage(body.get("usageMetadata")),
                              metadata={"api_type": "generateContent",
                                        "output_constraint": self.output_constraint,
                                        "finish_reason": finish_reason,
                                        "response_id": body.get("responseId"),
                                        "model_status": body.get("modelStatus")})


def _response_text(body: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    candidates = body.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        return None, None
    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts
                   if isinstance(part, dict) and not part.get("thought"))
    return (text or None), candidate.get("finishReason")


def _usage(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        return None
    usage: Dict[str, Any] = {
        "input_tokens": value.get("promptTokenCount"),
        "output_tokens": value.get("candidatesTokenCount"),
        "total_tokens": value.get("totalTokenCount"),
        "estimated": False,
    }
    mappings = {"cachedContentTokenCount": "cached_input_tokens",
                "thoughtsTokenCount": "reasoning_tokens",
                "toolUsePromptTokenCount": "tool_input_tokens",
                "serviceTier": "service_tier"}
    for source, target in mappings.items():
        if source in value:
            usage[target] = value[source]
    for name in ("promptTokensDetails", "cacheTokensDetails", "candidatesTokensDetails"):
        if name in value:
            usage[name] = value[name]
    return usage
