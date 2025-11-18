"""Reusable WordPress REST API client."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import requests

from .http_client import BasicAuthConfig, RequestsHttpClient


class WordPressRestError(RuntimeError):
    """Raised when the WordPress REST API responds with an error."""

    def __init__(self, status_code: int, message: str, body: str | None = None) -> None:
        super().__init__(f"WordPress REST error ({status_code}): {message}")
        self.status_code = status_code
        self.body = body or ""


class WordPressRestClient:
    """Lightweight WordPress REST API helper shared across modules."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        api_root: str | None = None,
        session: requests.Session | None = None,
        logger: logging.Logger | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_root = (api_root or f"{self.base_url}/wp-json/wp/v2").rstrip("/")
        if not self.api_root.endswith("/wp-json") and not self.api_root.endswith("/wp-json/wp/v2"):
            # Ensure endpoints continue to be appended correctly.
            self.api_root = self.api_root.rstrip("/")
        self.http_client = RequestsHttpClient(timeout=timeout, session=session or requests.Session())
        self.auth = BasicAuthConfig(username=username, password=password)
        self.logger = logger or logging.getLogger(__name__)

    def _request(self, method: str, endpoint: str, *, params=None, json=None, headers=None):
        url = f"{self.api_root}{endpoint}"
        self.logger.debug("HTTP %s %s", method, url)
        response = self.http_client.request_json(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
            auth=self.auth,
        )
        self.logger.info("REST %s %s -> %s", method, endpoint, response.status_code)
        if not response.ok:
            message = self._extract_error_message(response)
            self.logger.error(
                "Request failed", extra={"status": response.status_code, "body": message}
            )
            raise WordPressRestError(response.status_code, message, response.text)
        if response.status_code == 204:
            return None
        return response.json()

    def test_connection(self) -> Dict[str, object]:
        """Call the WordPress REST index to ensure credentials work."""

        url = f"{self.base_url}/wp-json/"
        response = self.http_client.request_json("GET", url, auth=self.auth)
        if not response.ok:
            message = self._extract_error_message(response)
            self.logger.error("WordPress index request failed: %s", message)
            raise WordPressRestError(response.status_code, message, response.text)
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
        except WordPressRestError:
            return []

    def create_menu(self, name: str) -> Dict[str, object]:
        return self._request("POST", "/menus", json={"name": name})

    def list_menu_items(self, menu_id: int) -> List[Dict[str, object]]:
        try:
            return self._request("GET", f"/menus/{menu_id}/items")
        except WordPressRestError:
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
        except WordPressRestError:
            return None
        name_lower = name.lower()
        for entry in results or []:
            if isinstance(entry, dict) and entry.get("name", "").lower() == name_lower:
                return entry
        return None


    def _extract_error_message(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip() or f"HTTP {response.status_code}"
        if isinstance(payload, dict):
            message = payload.get("message")
            if message:
                return str(message)
        return response.text.strip() or f"HTTP {response.status_code}"


__all__ = ["WordPressRestClient", "WordPressRestError"]
