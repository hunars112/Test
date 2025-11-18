"""Tests for the site health monitor."""
from __future__ import annotations

import json
from pathlib import Path

import requests

from authority_site_engine.core.http_client import HttpResponse
from authority_site_engine.core.project_manager import ProjectManager
from authority_site_engine.modules.health import SiteHealthMonitor
from tests.factories import FakeCloudflareClient, build_sample_project


class FakeHttpClient:
    def __init__(self, responses: dict[str, dict[str, object]]):
        self.responses = responses

    def get(self, url: str, *, timeout: int | None = None) -> HttpResponse:  # pragma: no cover - simple helper
        payload = self.responses.get(url)
        if payload is None:
            raise requests.RequestException(f"No stub for {url}")
        if "exception" in payload:
            raise payload["exception"]
        return HttpResponse(
            url=url,
            status_code=payload.get("status", 200),
            text=payload.get("body", ""),
            elapsed_ms=payload.get("ms", 42.0),
        )


def _prepare_project(tmp_path: Path):
    project_data = build_sample_project(tmp_path)
    manager = ProjectManager(base_directory=tmp_path)
    project_root = manager.create_project(project_data)
    return project_data, project_root


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_health_monitor_generates_status(tmp_path):
    project_data, project_root = _prepare_project(tmp_path)
    content_dir = project_root / "outputs" / "content"
    post_map = [
        {"post_id": 1, "post_title": "Pillar", "post_type": "pillar", "post_url": "https://portableheat.example/pillar"},
        {"post_id": 2, "post_title": "Supporting", "post_type": "supporting", "post_url": "https://portableheat.example/support"},
        {"post_id": 3, "post_title": "Info", "post_type": "info", "post_url": "https://portableheat.example/info"},
    ]
    link_map = [
        {"source_post_id": 2, "target_post_id": 1},
        {"source_post_id": 1, "target_post_id": 2},
        {"source_post_id": 3, "target_post_id": 1},
        {"source_post_id": 1, "target_post_id": 3},
    ]
    _write_json(content_dir / "post_map.json", post_map)
    _write_json(content_dir / "link_map.json", link_map)
    sitemap_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://portableheat.example/pillar</loc></url>
        <url><loc>https://portableheat.example/support</loc></url>
        <url><loc>https://portableheat.example/info</loc></url>
    </urlset>
    """
    http_client = FakeHttpClient(
        {
            "https://portableheat.example/": {"status": 200},
            "https://portableheat.example/pillar": {"status": 200},
            "https://portableheat.example/support": {"status": 200},
            "https://portableheat.example/wp-sitemap.xml": {"status": 200, "body": sitemap_xml},
            "https://portableheat.example/sitemap_index.xml": {"status": 404},
        }
    )
    monitor = SiteHealthMonitor(project_data, project_root, http_client=http_client)
    status = monitor.run()

    assert status["online_status"] == "ok"
    assert status["sitemap_status"] == "present"
    assert status["internal_linking_status"] == "ok"
    assert status["overall_status"] == "ok"
    assert status["known_post_count"] == 3
    assert status["sitemap_coverage_ratio"] == 1.0
    assert (content_dir / "health_status.json").exists()


def test_health_monitor_flags_warnings(tmp_path):
    project_data, project_root = _prepare_project(tmp_path)
    project_data.health.enable_cloudflare_stats = True
    http_client = FakeHttpClient(
        {
            "https://portableheat.example/": {"status": 500},
            "https://portableheat.example/pillar": {"status": 500},
            "https://portableheat.example/wp-sitemap.xml": {"status": 404},
            "https://portableheat.example/sitemap_index.xml": {"status": 404},
        }
    )
    content_dir = project_root / "outputs" / "content"
    post_map = [
        {"post_id": 1, "post_title": "Pillar", "post_type": "pillar", "post_url": "https://portableheat.example/pillar"}
    ]
    _write_json(content_dir / "post_map.json", post_map)
    fake_cloudflare = FakeCloudflareClient()
    fake_cloudflare.analytics_payload = {
        "totals": {
            "requests": {"all": 100, "cached": 40},
            "threats": {"all": 20},
        }
    }
    monitor = SiteHealthMonitor(
        project_data,
        project_root,
        http_client=http_client,
        cloudflare_client=fake_cloudflare,
    )
    status = monitor.run()

    assert status["online_status"] == "error"
    assert status["sitemap_status"] == "missing"
    assert status["internal_linking_status"] == "warning"
    assert status["cloudflare_status"] == "warning"
    assert status["overall_status"] == "error"
    assert any("Cloudflare" in note for note in status["notes"])
