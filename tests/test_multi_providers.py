"""Offline request/response tests for xAI and DeepSeek providers."""

import os
import socket
import unittest
from unittest import mock

from webfixbench.providers import available_providers, get_provider
from webfixbench.providers._http import HttpError
from webfixbench.providers.base import ProviderError


class RegistrationTests(unittest.TestCase):
    def test_new_providers_are_registered(self):
        self.assertIn("xai", available_providers())
        self.assertIn("deepseek", available_providers())

    def test_dedicated_keys_are_required(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for name, key in (("xai", "XAI_API_KEY"), ("deepseek", "DEEPSEEK_API_KEY")):
                with self.subTest(name=name), self.assertRaisesRegex(ProviderError, key):
                    get_provider(name, model="explicit-model",
                                 output_constraint="json_object",
                                 reasoning_effort="none" if name == "deepseek" else None)

    def test_unexpected_errors_cannot_serialize_a_configured_key(self):
        from webfixbench.providers.base import BaseProvider, ProviderResult
        class Broken(BaseProvider):
            def _review(self, prompt, *, case_id):
                raise RuntimeError("leaked-key")
        with mock.patch.dict(os.environ, {"XAI_API_KEY": "leaked-key"}, clear=True):
            result = Broken().review("x", case_id="c")
        self.assertNotIn("leaked-key", result.error)

    def test_transport_timeout_is_normalized(self):
        from webfixbench.providers._http import post_json
        with mock.patch("urllib.request.urlopen", side_effect=socket.timeout()):
            with self.assertRaisesRegex(HttpError, "timed out"):
                post_json("https://example.invalid", {}, {}, timeout=0.1)


class XAITests(unittest.TestCase):
    def provider(self, **kwargs):
        from webfixbench.providers.xai import XAIProvider
        with mock.patch.dict(os.environ, {"XAI_API_KEY": "xai-secret"}, clear=True):
            return XAIProvider(model="grok-explicit", max_output_tokens=123,
                               reasoning_effort="high", **kwargs)

    def test_payload_is_responses_specific(self):
        payload = self.provider()._payload("review")
        self.assertEqual(payload["max_output_tokens"], 123)
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(payload["reasoning"], {"effort": "high"})
        self.assertFalse(payload["store"])
        self.assertNotIn("messages", payload)

    def test_response_and_usage_breakdowns(self):
        provider = self.provider()
        body = {"model": "returned-grok", "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "{\"findings\":[],\"overall_confidence\":0.5}"}]}],
                "usage": {"input_tokens": 10, "output_tokens": 7, "total_tokens": 17,
                          "input_tokens_details": {"cached_tokens": 4},
                          "output_tokens_details": {"reasoning_tokens": 3}}}
        with mock.patch("webfixbench.providers.xai.post_json", return_value=(body, {})) as post:
            result = provider.review("review", case_id="c")
        self.assertEqual(post.call_args.args[0], "https://api.x.ai/v1/responses")
        self.assertEqual(result.model, "returned-grok")
        self.assertEqual(result.usage["output_token_details"]["reasoning_tokens"], 3)
        self.assertEqual(result.usage["total_tokens"], 17)

    def test_http_errors_are_redacted(self):
        provider = self.provider()
        with mock.patch("webfixbench.providers.xai.post_json",
                        side_effect=HttpError(401, "xai-secret", "HTTP 401 xai-secret")):
            result = provider.review("review", case_id="c")
        self.assertIn("[REDACTED]", result.error)
        self.assertNotIn("xai-secret", result.error)

    def test_malformed_api_shape_is_an_error(self):
        provider = self.provider()
        with mock.patch("webfixbench.providers.xai.post_json", return_value=({}, {})):
            self.assertIn("no output text", provider.review("x", case_id="c").error)


class DeepSeekTests(unittest.TestCase):
    def provider(self, **kwargs):
        from webfixbench.providers.deepseek import DeepSeekProvider
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "ds-secret"}, clear=True):
            return DeepSeekProvider(model="deepseek-explicit", output_constraint="json_object",
                                    reasoning_effort="high", **kwargs)

    def test_payload_differs_from_xai(self):
        payload = self.provider()._payload("review")
        self.assertEqual(payload["max_tokens"], 2048)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertNotIn("temperature", payload)
        self.assertNotIn("input", payload)

    def test_temperature_is_rejected_for_thinking(self):
        with self.assertRaises(ProviderError):
            self.provider(temperature=0.2)

    def test_response_preserves_cache_and_reasoning_usage(self):
        provider = self.provider()
        body = {"model": "returned-deepseek", "choices": [{"finish_reason": "stop",
                "message": {"content": "{\"findings\":[],\"overall_confidence\":0.5}",
                            "reasoning_content": "private"}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 8, "total_tokens": 17,
                          "prompt_cache_hit_tokens": 5, "prompt_cache_miss_tokens": 4,
                          "completion_tokens_details": {"reasoning_tokens": 6}}}
        with mock.patch("webfixbench.providers.deepseek.post_json", return_value=(body, {})) as post:
            result = provider.review("review", case_id="c")
        self.assertEqual(post.call_args.args[0], "https://api.deepseek.com/chat/completions")
        self.assertEqual(result.usage["prompt_cache_hit_tokens"], 5)
        self.assertEqual(result.usage["output_token_details"]["reasoning_tokens"], 6)
        self.assertNotIn("private", repr(result.metadata))

    def test_unsupported_schema_is_rejected(self):
        from webfixbench.providers.deepseek import DeepSeekProvider
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "x"}, clear=True):
            with self.assertRaises(ProviderError):
                DeepSeekProvider(model="m", output_constraint="json_schema")


if __name__ == "__main__":
    unittest.main()
