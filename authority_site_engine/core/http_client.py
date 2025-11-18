"""Reusable HTTP helper classes for Authority Site Engine modules."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Iterable, Sequence

import requests


@dataclass
class HttpResponse:
    """Lightweight HTTP response representation."""

    url: str
    status_code: int
    text: str
    elapsed_ms: float


class RequestsHttpClient:
    """Simple requests-backed HTTP helper with retry/backoff."""

    def __init__(
        self,
        *,
        timeout: int = 15,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        retry_status_codes: Sequence[int] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.retry_status_codes: Iterable[int] = retry_status_codes or (408, 429, 500, 502, 503, 504)

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout)
        allow_redirects = kwargs.pop("allow_redirects", True)
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=timeout,
                    allow_redirects=allow_redirects,
                    **kwargs,
                )
            except requests.RequestException:
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.base_backoff_seconds * (2**attempt))
                continue
            if response.status_code in self.retry_status_codes and attempt < self.max_retries:
                time.sleep(self.base_backoff_seconds * (2**attempt))
                continue
            return response
        return response  # pragma: no cover - logically unreachable

    def get(self, url: str, *, timeout: int | None = None) -> HttpResponse:
        response = self.request("GET", url, timeout=timeout or self.timeout)
        elapsed = response.elapsed.total_seconds() * 1000 if response.elapsed else 0.0
        return HttpResponse(
            url=str(response.url),
            status_code=response.status_code,
            text=response.text,
            elapsed_ms=elapsed,
        )

    def post(self, url: str, **kwargs) -> HttpResponse:
        response = self.request("POST", url, **kwargs)
        elapsed = response.elapsed.total_seconds() * 1000 if response.elapsed else 0.0
        return HttpResponse(
            url=str(response.url),
            status_code=response.status_code,
            text=response.text,
            elapsed_ms=elapsed,
        )


__all__ = ["HttpResponse", "RequestsHttpClient"]
