"""Tests for the lightweight WordPress deployment manager."""
from unittest.mock import patch

from authority_site_engine.core.deployment_manager import (
    DeploymentError,
    DeploymentManager,
)

from tests.factories import FakeWordPressClient, prepare_project


def test_push_categories_creates_job(tmp_path) -> None:
    project_data, project_root = prepare_project(tmp_path)
    project_data.categories.categories = ["One", "Two"]
    project_data.cloudflare.ssh_host = "deploy.example.com"
    project_data.cloudflare.ssh_username = "user"
    project_data.cloudflare.ssh_password = "pass"
    manager = DeploymentManager(project_data, project_root, client=FakeWordPressClient())

    with patch("authority_site_engine.core.deployment_manager.ASEJobClient") as job_client:
        instance = job_client.return_value
        instance.queue_category_job.return_value = (
            "/home/user/wp-content/ase-jobs/example.json"
        )

        report = manager.push_categories()

        instance.queue_category_job.assert_called_once()
        assert report.total_rows == 2
        assert report.details and "job_path" in report.details


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
