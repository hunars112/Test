"""Tests for the topical blueprint generator."""
from authority_site_engine.core.project_manager import ProjectManager
from authority_site_engine.modules.blueprint import TopicalBlueprintGenerator

from tests.factories import build_sample_project


def test_blueprint_generation_creates_artifacts(tmp_path):
    project_data = build_sample_project(tmp_path)
    manager = ProjectManager(base_directory=tmp_path)
    project_root = manager.create_project(project_data)

    generator = TopicalBlueprintGenerator(project_data, project_root)
    blueprint = generator.generate()

    expected_csvs = [
        "pillar_posts.csv",
        "supporting_posts.csv",
        "info_posts.csv",
        "affiliate_product_reviews.csv",
        "amazon_roundups.csv",
    ]
    for filename in expected_csvs:
        assert (project_root / "outputs" / "csv" / filename).exists()

    assert blueprint.pillars
    assert blueprint.supporting_topics
    assert blueprint.informational_topics
    assert (
        len(blueprint.affiliate_reviews)
        == project_data.content_structure.affiliate_product_posts
    )
    assert len(blueprint.amazon_roundups) == project_data.content_structure.amazon_roundup_posts

    topic_graph_path = project_root / "outputs" / "topic_graph.json"
    assert topic_graph_path.exists()
    assert len(blueprint.topic_graph["pillars"]) == project_data.content_structure.pillar_posts
