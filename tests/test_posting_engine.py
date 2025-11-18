"""Tests for the WordPress posting engine."""
from authority_site_engine.modules.posting import WordPressPostingEngine

from tests.factories import FakeWordPressClient, prepare_project


def test_posting_engine_creates_posts_and_map(tmp_path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    client = FakeWordPressClient()
    engine = WordPressPostingEngine(project_data, project_root, client=client)

    post_map = engine.run()

    assert post_map, "Expected posts to be created"
    assert (project_root / "outputs" / "content" / "post_map.json").exists()
    assert client.created_posts, "Client should receive create requests"

    # Affiliate and Amazon posts should contain CTA placeholders
    affiliate_payloads = [
        payload["payload"]
        for payload in client.created_posts
        if "[CTA_TOP]" in payload["payload"].get("content", "")
    ]
    assert affiliate_payloads, "CTA placeholders should be injected"

    # Log file should record actions
    log_path = project_root / "outputs" / "logs" / "posting_engine.log"
    assert log_path.exists()
    assert "Starting WordPress posting engine" in log_path.read_text()


def test_posting_engine_respects_custom_sequence(tmp_path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    project_data.posting_preferences.publish_sequence = [
        "informational",
        "affiliate",
        "supporting",
    ]
    client = FakeWordPressClient()
    engine = WordPressPostingEngine(project_data, project_root, client=client)

    post_map = engine.run()

    assert post_map[0]["post_type"] == "info"
    assert "affiliate_review" in {entry["post_type"] for entry in post_map}
