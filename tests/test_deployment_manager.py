"""Tests for the lightweight WordPress deployment manager."""
from authority_site_engine.core.deployment_manager import (
    DeploymentError,
    DeploymentManager,
)

from tests.factories import FakeWordPressClient, prepare_project


def test_push_categories_creates_terms(tmp_path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    client = FakeWordPressClient()
    manager = DeploymentManager(project_data, project_root, client=client)

    report = manager.push_categories()

    assert report.created >= 1
    assert len(client.categories) >= report.created


def test_publish_posts_from_csv(tmp_path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    client = FakeWordPressClient()
    manager = DeploymentManager(project_data, project_root, client=client)

    report = manager.publish_posts_from_csv("pillar", limit=2, publish_immediately=True)

    assert report.created == 2
    assert len(client.created_posts) == 2


def test_publish_with_unknown_csv(tmp_path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    manager = DeploymentManager(project_data, project_root, client=FakeWordPressClient())

    try:
        manager.publish_posts_from_csv("unknown")
    except DeploymentError as exc:
        assert "Unknown" in str(exc)
    else:  # pragma: no cover - sanity
        raise AssertionError("Expected DeploymentError")
