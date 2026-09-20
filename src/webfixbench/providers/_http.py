"""Minimal JSON-over-HTTPS helper shared by the vendor providers.

The providers speak the vendors' documented HTTP APIs through the standard
library instead of pulling in SDKs. That keeps the benchmark installable with
no dependencies and keeps a run from silently changing behaviour when an SDK
is upgraded.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


class HttpError(Exception):
    """An HTTP-level failure, carrying the status code and response body."""

    def __init__(self, status: Optional[int], body: str, message: str) -> None:
        self.status = status
        self.body = body
        super().__init__(message)


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

    try:
        return json.loads(body), response_headers
    except json.JSONDecodeError as exc:
        raise HttpError(200, body, f"response was not JSON: {exc}")
