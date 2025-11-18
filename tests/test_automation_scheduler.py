"""Tests for the daily automation scheduler."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from authority_site_engine.core.http_client import HttpResponse
from authority_site_engine.modules.automation import DailyAutomationScheduler
from tests.factories import FakeWordPressClient, prepare_project


class FakeHttpClient:
    def __init__(self, responses: dict[str, dict[str, object]]):
        self.responses = responses

    def get(self, url: str, *, timeout: int | None = None) -> HttpResponse:  # pragma: no cover - simple helper
        payload = self.responses.get(url)
        if not payload:
            raise RuntimeError(f"No response stub for {url}")
        return HttpResponse(
            url=url,
            status_code=payload.get("status", 200),
            text=payload.get("body", ""),
            elapsed_ms=payload.get("ms", 42.0),
        )


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _prepare_post_assets(project_root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    post_map = [
        {
            "post_id": 1,
            "post_title": "Review",
            "post_type": "affiliate_review",
            "post_url": "https://portableheat.example/review",
        },
        {
            "post_id": 2,
            "post_title": "Info",
            "post_type": "info",
            "post_url": "https://portableheat.example/info",
        },
    ]
    link_map = [
        {"source_post_id": 1, "target_post_id": 2},
        {"source_post_id": 2, "target_post_id": 1},
    ]
    content_dir = project_root / "outputs" / "content"
    _write_json(content_dir / "post_map.json", post_map)
    _write_json(content_dir / "link_map.json", link_map)
    return post_map, link_map


def test_scheduler_runs_due_tasks(tmp_path):
    project_data, project_root = prepare_project(tmp_path)
    project_data.automation.automation_enabled = True
    project_data.automation.health_check.interval_hours = 0
    project_data.automation.affiliate_check.interval_hours = 0
    project_data.automation.sitemap_ping.enabled = True
    project_data.automation.sitemap_ping.interval_hours = 0
    project_data.automation.content_review.interval_hours = 0
    project_data.automation.log_cleanup.enabled = False
    project_data.automation.linking_maintenance.enabled = False
    project_data.automation.cloudflare_stats.enabled = False

    post_map, _ = _prepare_post_assets(project_root)
    wp_client = FakeWordPressClient()
    for entry in post_map:
        wp_client.post_store[entry["post_id"]] = {
            "content": f"Post body [CTA_TOP] for {entry['post_title']}",
            "excerpt": entry["post_title"],
            "link": entry["post_url"],
            "payload": {"title": entry["post_title"]},
            "date": datetime.utcnow().isoformat(),
            "modified": datetime.utcnow().isoformat(),
            "meta": {},
        }

    sitemap_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://portableheat.example/review</loc></url>
    </urlset>
    """
    http_client = FakeHttpClient(
        {
            "https://portableheat.example/": {"status": 200},
            "https://portableheat.example/review": {"status": 200},
            "https://portableheat.example/info": {"status": 200},
            "https://portableheat.example/wp-sitemap.xml": {"status": 200, "body": sitemap_xml},
            "https://portableheat.example/sitemap_index.xml": {"status": 404},
        }
    )

    scheduler = DailyAutomationScheduler(
        project_data,
        project_root,
        http_client=http_client,
        wp_client=wp_client,
        sleep_fn=lambda *_args: None,
    )

    results = scheduler.run(now=datetime.utcnow())
    task_names = {result.task for result in results}

    assert "health_check" in task_names
    assert "affiliate_check" in task_names
    assert "sitemap_ping" in task_names
    assert "content_review" in task_names
    assert (project_root / "outputs" / "content" / "automation_state.json").exists()
    assert (project_root / "outputs" / "content" / "content_audit.json").exists()
    assert wp_client.updated_posts == []  # dry-run only


def test_scheduler_respects_intervals_and_manual_runs(tmp_path):
    project_data, project_root = prepare_project(tmp_path)
    project_data.automation.automation_enabled = True
    project_data.automation.health_check.interval_hours = 24
    project_data.automation.affiliate_check.enabled = False
    project_data.automation.log_cleanup.enabled = False
    project_data.automation.sitemap_ping.enabled = True
    project_data.automation.sitemap_ping.interval_hours = 24

    post_map, _ = _prepare_post_assets(project_root)
    wp_client = FakeWordPressClient()
    for entry in post_map:
        wp_client.post_store[entry["post_id"]] = {
            "content": f"Body with [CTA_TOP] {entry['post_title']}",
            "excerpt": entry["post_title"],
            "link": entry["post_url"],
            "payload": {"title": entry["post_title"]},
            "date": datetime.utcnow().isoformat(),
            "modified": datetime.utcnow().isoformat(),
            "meta": {},
        }

    http_client = FakeHttpClient(
        {
            "https://portableheat.example/": {"status": 200},
            "https://portableheat.example/review": {"status": 200},
            "https://portableheat.example/info": {"status": 200},
            "https://portableheat.example/wp-sitemap.xml": {"status": 200},
            "https://portableheat.example/sitemap_index.xml": {"status": 200},
        }
    )

    scheduler = DailyAutomationScheduler(
        project_data,
        project_root,
        http_client=http_client,
        wp_client=wp_client,
        sleep_fn=lambda *_args: None,
    )

    start = datetime(2024, 1, 1, 0, 0, 0)
    first_results = scheduler.run(now=start)
    assert any(result.task == "health_check" for result in first_results)

    second_results = scheduler.run(now=start + timedelta(hours=1))
    assert second_results == []  # not due yet

    project_data.automation.automation_enabled = False
    manual_results = scheduler.run(tasks=["sitemap_ping"], now=start + timedelta(hours=2))
    assert manual_results and manual_results[0].task == "sitemap_ping"
