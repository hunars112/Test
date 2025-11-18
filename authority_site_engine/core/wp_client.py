"""Reusable WordPress REST API client."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import requests

from .http_client import RequestsHttpClient


class WordPressRestClient:
    """Lightweight WordPress REST API helper shared across modules."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        session: requests.Session | None = None,
        logger: logging.Logger | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_root = f"{self.base_url}/wp-json/wp/v2"
        base_session = session or requests.Session()
        base_session.auth = (username, password)
        self.http_client = RequestsHttpClient(timeout=timeout, session=base_session)
        self.logger = logger or logging.getLogger(__name__)

    def _request(self, method: str, endpoint: str, **kwargs):
        url = f"{self.api_root}{endpoint}"
        self.logger.debug("HTTP %s %s", method, url)
        response = self.http_client.request(method, url, **kwargs)
        self.logger.info("REST %s %s -> %s", method, endpoint, response.status_code)
        if not response.ok:
            self.logger.error(
                "Request failed", extra={"status": response.status_code, "body": response.text}
            )
            response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    def test_connection(self) -> Dict[str, object]:
        """Call the WordPress REST index to ensure credentials work."""

        url = f"{self.base_url}/wp-json/"
        response = self.http_client.request("GET", url)
        if not response.ok:
            self.logger.error("WordPress index request failed: %s", response.text)
            response.raise_for_status()
        return response.json()

    def list_categories(self) -> List[Dict[str, object]]:
        return self._request("GET", "/categories")

    def create_category(self, name: str, slug: str | None = None) -> Dict[str, object]:
        payload: Dict[str, object] = {"name": name}
        if slug:
            payload["slug"] = slug
        return self._request("POST", "/categories", json=payload)

    def ensure_category(self, name: str, slug: str | None = None) -> Tuple[int, bool]:
        term = self._find_term("/categories", name)
        if term:
            return int(term["id"]), False
        created = self.create_category(name, slug=slug)
        return int(created["id"]), True

    def list_tags(self) -> List[Dict[str, object]]:
        return self._request("GET", "/tags")

    def create_tag(self, name: str) -> Dict[str, object]:
        return self._request("POST", "/tags", json={"name": name})

    def ensure_tag(self, name: str) -> Tuple[int, bool]:
        term = self._find_term("/tags", name)
        if term:
            return int(term["id"]), False
        created = self.create_tag(name)
        return int(created["id"]), True

    def create_post(self, payload: Dict[str, object]) -> Dict[str, object]:
        return self._request("POST", "/posts", json=payload)

    def update_post(self, post_id: int, payload: Dict[str, object]) -> Dict[str, object]:
        return self._request("POST", f"/posts/{post_id}", json=payload)

    def create_or_update_post(self, payload: Dict[str, object]) -> Dict[str, object]:
        post_id = payload.get("id")
        if isinstance(post_id, int) and post_id > 0:
            return self.update_post(post_id, payload)
        return self.create_post(payload)

    def get_post(self, post_id: int) -> Dict[str, object]:
        return self._request("GET", f"/posts/{post_id}")

    def upload_media(self, filename: str, data: bytes, mime_type: str) -> Dict[str, object]:
        headers = {
            "Content-Disposition": f"attachment; filename={Path(filename).name}",
            "Content-Type": mime_type,
        }
        return self._request("POST", "/media", data=data, headers=headers)

    def update_settings(self, payload: Dict[str, object]) -> Dict[str, object]:
        return self._request("POST", "/settings", json=payload)

    def list_posts(self, **params) -> List[Dict[str, object]]:
        return self._request("GET", "/posts", params=params)

    def delete_post(self, post_id: int) -> Dict[str, object]:
        return self._request("DELETE", f"/posts/{post_id}", params={"force": True})

    def list_menus(self) -> List[Dict[str, object]]:
        try:
            return self._request("GET", "/menus")
        except requests.HTTPError:
            return []

    def create_menu(self, name: str) -> Dict[str, object]:
        return self._request("POST", "/menus", json={"name": name})

    def list_menu_items(self, menu_id: int) -> List[Dict[str, object]]:
        try:
            return self._request("GET", f"/menus/{menu_id}/items")
        except requests.HTTPError:
            return []

    def create_menu_item(
        self,
        menu_id: int,
        *,
        title: str,
        object_id: int,
        order: int,
    ) -> Dict[str, object]:
        payload = {
            "title": title,
            "menu": menu_id,
            "object_id": object_id,
            "object": "category",
            "type": "taxonomy",
            "menu_order": order,
        }
        return self._request("POST", f"/menus/{menu_id}/items", json=payload)

    def _find_term(self, endpoint: str, name: str) -> Dict[str, object] | None:
        params = {"search": name, "per_page": 100}
        try:
            results = self._request("GET", endpoint, params=params)
        except requests.HTTPError:
            return None
        name_lower = name.lower()
        for entry in results or []:
            if isinstance(entry, dict) and entry.get("name", "").lower() == name_lower:
                return entry
        return None


__all__ = ["WordPressRestClient"]
