"""Reusable HTTP helper classes for Authority Site Engine modules."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import time
from typing import Iterable, Mapping, MutableMapping, Sequence

import requests


@dataclass
class HttpResponse:
    """Lightweight HTTP response representation."""

    url: str
    status_code: int
    text: str
    elapsed_ms: float


@dataclass
class BasicAuthConfig:
    """Configuration for HTTP basic authentication (WordPress app passwords)."""

    username: str
    password: str

    def as_header(self) -> str:
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"


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
        auth_config: BasicAuthConfig | None = kwargs.pop("auth_config", None)
        headers: MutableMapping[str, str]
        raw_headers = kwargs.pop("headers", {})
        headers = dict(raw_headers or {})
        if auth_config:
            headers["Authorization"] = auth_config.as_header()
        if headers:
            kwargs["headers"] = headers
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

    def request_json(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, object] | None = None,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: BasicAuthConfig | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        merged_headers = {"Accept": "application/json"}
        if json is not None:
            merged_headers["Content-Type"] = "application/json"
        if headers:
            merged_headers.update(headers)
        return self.request(
            method,
            url,
            json=json,
            params=params,
            headers=merged_headers,
            auth_config=auth,
            timeout=timeout or self.timeout,
        )

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: BasicAuthConfig | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        return self.request_json(
            "GET",
            url,
            params=params,
            headers=headers,
            auth=auth,
            timeout=timeout,
        )

    def post_json(
        self,
        url: str,
        *,
        json: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: BasicAuthConfig | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        return self.request_json(
            "POST",
            url,
            json=json,
            headers=headers,
            auth=auth,
            timeout=timeout,
        )


__all__ = ["BasicAuthConfig", "HttpResponse", "RequestsHttpClient"]
