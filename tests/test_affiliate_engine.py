"""Tests for the niche-agnostic Affiliate Link Engine."""
from __future__ import annotations

import json
from pathlib import Path

from authority_site_engine.core.project_manager import ProjectManager
from authority_site_engine.modules.affiliate import AffiliateLinkEngine
from tests.factories import FakeWordPressClient, build_sample_project


def _prepare_post_map(project_root: Path, entries: list[dict[str, object]]) -> None:
    outputs = project_root / "outputs" / "content"
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "post_map.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _seed_post_content(client: FakeWordPressClient, post_id: int, content: str) -> None:
    client.post_store[post_id] = {"id": post_id, "link": f"https://example.com/{post_id}", "content": content}


def test_affiliate_engine_replaces_placeholders(tmp_path: Path) -> None:
    project_data = build_sample_project(tmp_path)
    manager = ProjectManager(base_directory=tmp_path)
    project_root = manager.create_project(project_data)
    post_entries = [
        {
            "post_id": 1,
            "post_title": "Heater A Review",
            "post_type": "affiliate_review",
            "post_url": "https://example.com/1",
        },
        {
            "post_id": 2,
            "post_title": "Winter Heating Tips",
            "post_type": "info",
            "post_url": "https://example.com/2",
        },
    ]
    _prepare_post_map(project_root, post_entries)
    category_map = {
        "assignments": [
            {"post_id": 1, "category_name": "Heating Basics"},
            {"post_id": 2, "category_name": "Heating Basics"},
        ]
    }
    (project_root / "outputs" / "content" / "category_map.json").write_text(
        json.dumps(category_map, indent=2), encoding="utf-8"
    )

    client = FakeWordPressClient()
    _seed_post_content(client, 1, "[CTA_TOP]\nGreat review\n[CTA_BOTTOM]")
    _seed_post_content(client, 2, "Helpful article body\n[CTA_BOTTOM]")

    engine = AffiliateLinkEngine(project_data, project_root, client=client)
    results = engine.run()

    assert client.post_store[1]["content"].count("CTA_TOP") == 0
    assert "redirect.example/go?offer=heater-a" in client.post_store[1]["content"]
    assert "Heater A" in client.post_store[1]["content"]
    assert "redirect.example/go?offer=heater-b" in client.post_store[2]["content"]
    assert results and results[0]["replacements"]


def test_affiliate_engine_dry_run_and_fallback(tmp_path: Path) -> None:
    project_data = build_sample_project(tmp_path)
    project_data.affiliate_links.offers = []
    manager = ProjectManager(base_directory=tmp_path)
    project_root = manager.create_project(project_data)
    _prepare_post_map(
        project_root,
        [
            {
                "post_id": 5,
                "post_title": "Generic Roundup",
                "post_type": "amazon_roundup",
                "post_url": "https://example.com/5",
            }
        ],
    )

    client = FakeWordPressClient()
    _seed_post_content(client, 5, "Intro paragraph\n[CTA_TOP]\nClosing")

    engine = AffiliateLinkEngine(project_data, project_root, client=client)
    plan = engine.run(dry_run=True)

    assert not client.updated_posts, "Dry run should not push updates"
    assert plan and plan[0]["replacements"], "Dry run should report replacements"
    assert project_data.affiliate_links.backup_url in plan[0]["replacements"][0]["affiliate_url"]
