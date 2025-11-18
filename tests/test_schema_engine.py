"""Tests for the schema engine."""
import json

from authority_site_engine.modules.category_menu import CategoryMenuBuilder
from authority_site_engine.modules.posting import WordPressPostingEngine
from authority_site_engine.modules.schema import SchemaEngine

from tests.factories import FakeWordPressClient, prepare_project


def _prepare_site(tmp_path):
    project_data, project_root = prepare_project(tmp_path)
    client = FakeWordPressClient()
    posting_engine = WordPressPostingEngine(project_data, project_root, client=client)
    posting_engine.run()
    CategoryMenuBuilder(project_data, project_root, client=client).run()
    return project_data, project_root, client


def test_schema_engine_injects_schema_blocks(tmp_path) -> None:
    project_data, project_root, client = _prepare_site(tmp_path)
    engine = SchemaEngine(project_data, project_root, client=client)

    summaries = engine.run()

    assert summaries, "Schema engine should update posts"
    schema_map_path = project_root / "outputs" / "content" / "schema_map.json"
    assert schema_map_path.exists(), "Schema map should be recorded"
    schema_data = json.loads(schema_map_path.read_text())
    assert schema_data.get("entries"), "Schema entries should be captured"

    sample_post = summaries[0]["post_id"]
    content = client.post_store[sample_post]["content"]
    assert content.count("ASE_SCHEMA_START") == 1
    assert "BlogPosting" in content

    log_path = project_root / "outputs" / "logs" / "schema_engine.log"
    assert log_path.exists()
    assert "Schema engine" in log_path.read_text()


def test_schema_engine_meta_injection(tmp_path) -> None:
    project_data, project_root, client = _prepare_site(tmp_path)
    project_data.schema.inject_method = "meta"
    engine = SchemaEngine(project_data, project_root, client=client)

    summaries = engine.run()

    assert summaries, "Schema engine should update posts via meta"
    sample_post = summaries[0]["post_id"]
    meta_store = client.post_store[sample_post]["meta"]
    assert project_data.schema.schema_meta_key in meta_store
    assert meta_store[project_data.schema.schema_meta_key]
