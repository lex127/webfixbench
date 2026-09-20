"""Provider registry.

Vendor modules are imported lazily so that constructing the mock provider never
touches vendor code paths and a missing API key can only fail the provider the
user actually asked for.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseProvider, ProviderError, ProviderResult
from .mock import MockProvider

PROVIDERS = ("mock", "openai", "anthropic")

__all__ = [
    "BaseProvider",
    "ProviderError",
    "ProviderResult",
    "MockProvider",
    "PROVIDERS",
    "available_providers",
    "get_provider",
]


def available_providers() -> List[str]:
    return list(PROVIDERS)


def get_provider(name: str, **kwargs: Any) -> BaseProvider:
    """Instantiate a provider by name.

    Raises :class:`ProviderError` for unknown names or missing configuration.
    """
    key = (name or "").strip().lower()
    if key == "mock":
        return MockProvider(**kwargs)
    if key == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(**_without_mock_args(kwargs))
    if key == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(**_without_mock_args(kwargs))
    raise ProviderError(f"unknown provider {name!r}; expected one of {list(PROVIDERS)}")


def _without_mock_args(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Drop mock-only arguments so the CLI can pass one uniform argument set."""
    return {k: v for k, v in kwargs.items() if k != "mode"}
