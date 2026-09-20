"""Provider contract, mock determinism, and the no-network guarantee.

No test in this file performs a network call. The vendor providers are only
exercised up to the point where they refuse to run without an API key.
"""

import os
import unittest
from pathlib import Path
from unittest import mock

from webfixbench.cases import load_suite
from webfixbench.config import load_prompt
from webfixbench.providers import ProviderError, get_provider
from webfixbench.providers.base import BaseProvider, ProviderResult
from webfixbench.providers.mock import MockProvider
from webfixbench.runner import build_prompt_text
from webfixbench.schemas import parse_model_response

ROOT = Path(__file__).resolve().parents[1]


class MockProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = load_suite("php-web-v0.1", root=ROOT)
        self.prompt = load_prompt("review_v2", root=ROOT)

    def _prompt_for(self, case_id: str) -> str:
        return build_prompt_text(self.prompt, self.suite.get(case_id))

    def test_output_validates_against_the_response_schema(self) -> None:
        provider = MockProvider()
        for case in self.suite.cases:
            with self.subTest(case=case.id):
                result = provider.review(build_prompt_text(self.prompt, case), case_id=case.id)
                self.assertTrue(result.ok)
                parse_model_response(result.raw_text)

    def test_output_is_deterministic(self) -> None:
        text = self._prompt_for("laravel-authz-001")
        first = MockProvider().review(text, case_id="laravel-authz-001").raw_text
        second = MockProvider().review(text, case_id="laravel-authz-001").raw_text
        self.assertEqual(first, second)

    def test_it_detects_a_removed_authorization_call(self) -> None:
        result = MockProvider().review(
            self._prompt_for("laravel-authz-001"), case_id="laravel-authz-001"
        )
        categories = [f.normalized_category for f in parse_model_response(result.raw_text).findings]
        self.assertIn("authorization", categories)

    def test_it_detects_interpolated_sql(self) -> None:
        result = MockProvider().review(
            self._prompt_for("php-injection-001"), case_id="php-injection-001"
        )
        categories = [f.normalized_category for f in parse_model_response(result.raw_text).findings]
        self.assertIn("injection", categories)

    def test_empty_mode_reports_nothing(self) -> None:
        result = MockProvider(mode="empty").review(
            self._prompt_for("laravel-authz-001"), case_id="laravel-authz-001"
        )
        self.assertEqual(parse_model_response(result.raw_text).findings, [])

    def test_malformed_mode_produces_unparseable_output(self) -> None:
        result = MockProvider(mode="malformed").review(
            self._prompt_for("laravel-authz-001"), case_id="laravel-authz-001"
        )
        self.assertTrue(result.ok)  # the provider call succeeded ...
        with self.assertRaises(Exception):  # ... but the payload is not a review
            parse_model_response(result.raw_text)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ProviderError):
            MockProvider(mode="clairvoyant")

    def test_describe_records_run_settings(self) -> None:
        description = MockProvider(temperature=0.0).describe()
        self.assertEqual(description["provider"], "mock")
        self.assertEqual(description["api_type"], "offline")
        self.assertEqual(description["output_constraint"], "native_json")
        self.assertEqual(description["mock_mode"], "heuristic")
        self.assertIn("Not a language model", description["note"])

    def test_usage_is_reported_and_flagged_as_estimated(self) -> None:
        result = MockProvider().review(
            self._prompt_for("laravel-authz-001"), case_id="laravel-authz-001"
        )
        self.assertTrue(result.usage["estimated"])
        self.assertGreater(result.usage["total_tokens"], 0)


class BaseProviderTests(unittest.TestCase):
    def test_provider_exceptions_become_recorded_errors(self) -> None:
        class ExplodingProvider(BaseProvider):
            name = "exploding"

            def _review(self, prompt: str, *, case_id: str) -> ProviderResult:
                raise RuntimeError("boom")

        result = ExplodingProvider().review("prompt", case_id="c1")
        self.assertFalse(result.ok)
        self.assertIn("boom", result.error)
        self.assertGreaterEqual(result.latency_ms, 0.0)

    def test_latency_is_measured(self) -> None:
        result = MockProvider().review("BEGIN DIFF\n+x\nEND DIFF", case_id="c1")
        self.assertGreater(result.latency_ms, 0.0)


class RegistryTests(unittest.TestCase):
    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(ProviderError):
            get_provider("gpt-oracle")

    def test_mock_provider_is_constructible_without_any_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(get_provider("mock"), MockProvider)

    def test_openai_requires_a_model(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-used"}, clear=True):
            with self.assertRaises(ProviderError):
                get_provider("openai")

    def test_openai_requires_a_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError) as ctx:
                get_provider("openai", model="some-model")
            self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    def test_anthropic_requires_a_model(self) -> None:
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-not-used"}, clear=True):
            with self.assertRaises(ProviderError):
                get_provider("anthropic")

    def test_anthropic_requires_a_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError) as ctx:
                get_provider("anthropic", model="some-model")
            self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))


class VendorProviderOfflineTests(unittest.TestCase):
    """Payload shaping only — the HTTP layer is never reached."""

    def test_openai_payload_shape(self) -> None:
        from webfixbench.providers.openai import OpenAIProvider

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-used"}, clear=True):
            provider = OpenAIProvider(model="some-model", max_output_tokens=256)
        payload = provider._payload("review this")
        self.assertEqual(payload["model"], "some-model")
        self.assertEqual(payload["max_output_tokens"], 256)
        self.assertEqual(payload["input"][-1]["content"], "review this")
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(provider.describe()["api_type"], "responses")
        self.assertNotIn("temperature", payload)

    def test_openai_accepts_none_reasoning_and_rejects_sampling_with_reasoning(self) -> None:
        from webfixbench.providers.openai import OpenAIProvider
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-used"}, clear=True):
            provider = OpenAIProvider(model="gpt-5.6-terra", reasoning_effort="none")
            with self.assertRaises(ProviderError):
                OpenAIProvider(model="gpt-5.6-terra", reasoning_effort="none", temperature=0.0)
        self.assertEqual(provider._payload("review")["reasoning"], {"effort": "none"})

    def test_openai_chat_completions_is_explicit(self) -> None:
        from webfixbench.providers.openai import OpenAIProvider

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-used"}, clear=True):
            provider = OpenAIProvider(
                model="some-model", api_type="chat.completions", output_constraint="json_object"
            )
        payload = provider._payload("review this")
        self.assertIn("messages", payload)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(provider.describe()["api_type"], "chat.completions")

    def test_anthropic_json_schema_payload_and_metadata(self) -> None:
        from webfixbench.providers.anthropic import AnthropicProvider

        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-not-used"}, clear=True):
            provider = AnthropicProvider(model="claude-sonnet-example")
        payload = provider._payload("review this")
        self.assertEqual(payload["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(provider.describe()["api_type"], "messages")
        self.assertEqual(provider.describe()["output_constraint"], "json_schema")
        self.assertNotIn("temperature", payload)

    def test_sonnet_5_disabled_thinking_and_no_sampling(self) -> None:
        from webfixbench.providers.anthropic import AnthropicProvider
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-not-used"}, clear=True):
            provider = AnthropicProvider(model="claude-sonnet-5", thinking_mode="disabled")
            with self.assertRaises(ProviderError):
                AnthropicProvider(model="claude-sonnet-5", temperature=0.0)
            with self.assertRaises(ProviderError):
                AnthropicProvider(model="claude-sonnet-5", reasoning_effort="low")
        self.assertEqual(provider._payload("review")["thinking"], {"type": "disabled"})
        self.assertEqual(provider.describe()["settings_sent"]["thinking"], {"type": "disabled"})

    def test_anthropic_rejects_fable_models(self) -> None:
        from webfixbench.providers.anthropic import AnthropicProvider

        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-not-used"}, clear=True):
            with self.assertRaises(ProviderError):
                AnthropicProvider(model="claude-fable-5")

    def test_api_keys_never_appear_in_provider_metadata(self) -> None:
        from webfixbench.providers.anthropic import AnthropicProvider

        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret-value"}, clear=True):
            provider = AnthropicProvider(model="some-model")
        self.assertNotIn("secret-value", repr(provider.describe()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
