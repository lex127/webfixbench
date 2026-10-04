"""Minimal JSON-over-HTTPS helper shared by the vendor providers.

The providers speak the vendors' documented HTTP APIs through the standard
library instead of pulling in SDKs. Transient transport failures are retried
with bounded backoff; model/schema failures are never retried here.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 1.0


class HttpError(Exception):
    """An HTTP-level failure, carrying the status code and response body."""

    def __init__(self, status: Optional[int], body: str, message: str) -> None:
        self.status = status
        self.body = body
        super().__init__(message)


def redact(text: str, *secrets: Optional[str]) -> str:
    """Remove configured credential values from text destined for results."""
    cleaned = str(text)
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def token_usage(usage: Any, *, style: str) -> Optional[Dict[str, Any]]:
    """Normalize token totals while retaining documented vendor breakdowns."""
    if not isinstance(usage, dict) or not usage:
        return None
    if style == "responses":
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        input_details = usage.get("input_tokens_details")
        output_details = usage.get("output_tokens_details")
    else:
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        input_details = usage.get("prompt_tokens_details")
        output_details = usage.get("completion_tokens_details")
    normalized = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": usage.get("total_tokens"),
        "estimated": False,
    }
    if isinstance(input_details, dict):
        normalized["input_token_details"] = dict(input_details)
    if isinstance(output_details, dict):
        normalized["output_token_details"] = dict(output_details)
    for name in ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "num_sources_used",
                 "num_server_side_tools_used", "cost_in_usd_ticks"):
        if name in usage:
            normalized[name] = usage[name]
    return normalized


def _retry_after_seconds(headers: Any) -> Optional[float]:
    """Parse the numeric Retry-After form; HTTP-date support is unnecessary here."""
    if headers is None:
        return None
    value = headers.get("Retry-After") or headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(seconds, 60.0))


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    *,
    timeout: float = 120.0,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """POST JSON and retry only transient transport failures.

    HTTP 408/429/5xx and connection/timeout failures are retried up to
    max_attempts. Successful-but-malformed JSON is not retried because that is
    observable provider behaviour. The returned headers include an internal
    attempt-count header for auditability.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    data = json.dumps(payload).encode("utf-8")
    last_error: Optional[HttpError] = None

    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("content-type", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            error = HttpError(exc.code, detail, f"HTTP {exc.code}: {detail[:500]}")
            retryable = exc.code in RETRYABLE_STATUSES
            retry_after = _retry_after_seconds(exc.headers)
        except urllib.error.URLError as exc:
            error = HttpError(None, "", f"request failed: {exc.reason}")
            retryable = True
            retry_after = None
        except (TimeoutError, socket.timeout):
            error = HttpError(None, "", "request timed out")
            retryable = True
            retry_after = None
        else:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                raise HttpError(200, body, f"response was not JSON: {exc}")
            response_headers["x-webfixbench-attempts"] = str(attempt)
            return parsed, response_headers

        last_error = error
        if not retryable or attempt >= max_attempts:
            raise error
        delay = retry_after if retry_after is not None else backoff_seconds * (2 ** (attempt - 1))
        time.sleep(min(delay, 60.0))

    assert last_error is not None
    raise last_error
