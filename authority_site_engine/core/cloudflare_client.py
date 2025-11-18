"""Reusable Cloudflare API helper."""
from __future__ import annotations

import logging
from typing import Dict, Iterable

import requests


class CloudflareClient:
    """Minimal Cloudflare API helper for DNS + SSL automation."""

    api_root = "https://api.cloudflare.com/client/v4"

    def __init__(
        self,
        email: str,
        api_key: str,
        *,
        session: requests.Session | None = None,
        logger: logging.Logger | None = None,
        timeout: int = 30,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "X-Auth-Email": email,
                "X-Auth-Key": api_key,
                "Content-Type": "application/json",
            }
        )
        self.logger = logger or logging.getLogger(__name__)
        self.timeout = timeout
        self._zone_cache: Dict[str, str] = {}

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.api_root}{path}"
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        if not response.ok:
            self.logger.error(
                "Cloudflare API call failed", extra={"status": response.status_code, "body": response.text}
            )
            response.raise_for_status()
        payload = response.json()
        if not payload.get("success", True):
            raise RuntimeError(payload.get("errors", "Cloudflare API failure"))
        return payload.get("result")

    def get_zone_id(self, domain: str) -> str:
        if domain in self._zone_cache:
            return self._zone_cache[domain]
        zones = self._request("GET", "/zones", params={"name": domain}) or []
        if not zones:
            raise RuntimeError(f"Cloudflare zone for {domain} not found")
        zone_id = zones[0]["id"]
        self._zone_cache[domain] = zone_id
        return zone_id

    def ensure_dns_records(self, domain: str, records: Iterable[Dict[str, object]]):
        zone_id = self.get_zone_id(domain)
        existing = self._request("GET", f"/zones/{zone_id}/dns_records", params={"per_page": 100}) or []
        lookup = {(record["type"], record["name"]): record for record in existing}
        for record in records:
            record_type = record.get("type")
            name = self._normalize_record_name(domain, str(record.get("name", "")))
            payload = {
                "type": record_type,
                "name": name,
                "content": record.get("content"),
                "proxied": record.get("proxied", True),
                "ttl": record.get("ttl", 1),
            }
            key = (record_type, name)
            current = lookup.get(key)
            if current:
                if current.get("content") != payload["content"] or bool(current.get("proxied")) != bool(payload["proxied"]):
                    self._request("PUT", f"/zones/{zone_id}/dns_records/{current['id']}", json=payload)
                    self.logger.info("Updated Cloudflare record %s %s", record_type, name)
            else:
                self._request("POST", f"/zones/{zone_id}/dns_records", json=payload)
                self.logger.info("Created Cloudflare record %s %s", record_type, name)

    def set_ssl_mode(self, domain: str, mode: str) -> None:
        zone_id = self.get_zone_id(domain)
        self._request("PATCH", f"/zones/{zone_id}/settings/ssl", json={"value": mode})
        self.logger.info("Set Cloudflare SSL mode to %s", mode)

    def fetch_analytics(self, domain: str, *, since_hours: int = 24):
        zone_id = self.get_zone_id(domain)
        params = {"since": f"-{int(since_hours) * 3600}", "continuous": True}
        return self._request("GET", f"/zones/{zone_id}/analytics/dashboard", params=params)

    def _normalize_record_name(self, domain: str, name: str) -> str:
        if name in {"@", ""}:
            return domain
        if name.endswith(domain):
            return name
        return f"{name}.{domain}".rstrip(".")


__all__ = ["CloudflareClient"]
