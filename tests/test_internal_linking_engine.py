"""Tests for the internal linking engine."""

from authority_site_engine.modules.internal_linking import InternalLinkingEngine
from authority_site_engine.modules.posting import WordPressPostingEngine

from tests.factories import FakeWordPressClient, prepare_project


def test_internal_linking_engine_creates_link_map(tmp_path):
    project_data, project_root = prepare_project(tmp_path)
    posting_client = FakeWordPressClient()
    posting_engine = WordPressPostingEngine(project_data, project_root, client=posting_client)
    posting_engine.run()

    linking_engine = InternalLinkingEngine(project_data, project_root, client=posting_client)
    link_map = linking_engine.run()

    assert link_map, "Links should be applied"
    assert posting_client.updated_posts, "Posts should be updated with new content"
    link_map_path = project_root / "outputs" / "content" / "link_map.json"
    assert link_map_path.exists()
    log_path = project_root / "outputs" / "logs" / "internal_linking.log"
    assert log_path.exists()
    assert "Applied" in log_path.read_text()


def test_internal_linking_dry_run(tmp_path):
    project_data, project_root = prepare_project(tmp_path)
    posting_client = FakeWordPressClient()
    posting_engine = WordPressPostingEngine(project_data, project_root, client=posting_client)
    posting_engine.run()

    linking_engine = InternalLinkingEngine(project_data, project_root, client=posting_client)
    link_map = linking_engine.run(dry_run=True)

    assert link_map, "Dry-run should still plan links"
    assert not posting_client.updated_posts, "No posts should be updated in dry-run"
    assert all(entry["link_position_type"] == "planned" for entry in link_map)
