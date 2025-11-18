"""Tests for the HTTP helper utilities."""
from base64 import b64encode
from datetime import timedelta

from authority_site_engine.core.http_client import BasicAuthConfig, RequestsHttpClient


class DummyResponse:
    def __init__(self):
        self.status_code = 201
        self.text = "{}"
        self._json = {"id": 1}
        self.elapsed = timedelta(milliseconds=5)
        self.url = "https://example.com"
        self.ok = True

    def json(self):
        return self._json


class DummySession:
    def __init__(self):
        self.last_kwargs = None

    def request(self, method, url, **kwargs):
        self.last_kwargs = {"method": method, "url": url, **kwargs}
        return DummyResponse()


def test_request_json_includes_basic_auth_and_headers():
    session = DummySession()
    client = RequestsHttpClient(session=session)
    auth = BasicAuthConfig(username="editor", password="pass word")

    client.request_json(
        "POST",
        "https://example.com/wp-json/wp/v2/categories",
        json={"name": "News"},
        auth=auth,
    )

    assert session.last_kwargs is not None
    headers = session.last_kwargs["headers"]
    expected = b64encode(b"editor:pass word").decode("ascii")
    assert headers["Authorization"] == f"Basic {expected}"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert session.last_kwargs["json"] == {"name": "News"}
    assert session.last_kwargs["method"] == "POST"
    assert session.last_kwargs["url"].endswith("/categories")
