"""Minimal JSON-over-HTTPS helper shared by the vendor providers.

The providers speak the vendors' documented HTTP APIs through the standard
library instead of pulling in SDKs. That keeps the benchmark installable with
no dependencies and keeps a run from silently changing behaviour when an SDK
is upgraded.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


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


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    *,
    timeout: float = 120.0,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """POST ``payload`` as JSON and return ``(parsed_body, response_headers)``."""
    data = json.dumps(payload).encode("utf-8")
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
        raise HttpError(exc.code, detail, f"HTTP {exc.code}: {detail[:500]}")
    except urllib.error.URLError as exc:
        raise HttpError(None, "", f"request failed: {exc.reason}")
    except (TimeoutError, socket.timeout):
        raise HttpError(None, "", "request timed out")

    try:
        return json.loads(body), response_headers
    except json.JSONDecodeError as exc:
        raise HttpError(200, body, f"response was not JSON: {exc}")
