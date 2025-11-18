"""Tests for the Authority Site Engine project creation module."""
from pathlib import Path

from authority_site_engine.core.project_manager import ProjectManager

from tests.factories import build_sample_project


def test_project_saved_to_disk(tmp_path: Path) -> None:
    manager = ProjectManager(base_directory=tmp_path)
    project_data = build_sample_project(tmp_path)
    project_path = manager.create_project(project_data)

    assert (project_path / "settings.json").exists()
    assert (project_path / "project.db").exists()
    assert (project_path / "outputs" / "csv").exists()
    assert (project_path / "outputs" / "content").exists()
    assert (project_path / "outputs" / "logs").exists()

    reloaded = manager.load_project(project_data.basic_info.project_name)
    assert reloaded.basic_info.project_name == project_data.basic_info.project_name
    assert reloaded.categories.categories == project_data.categories.categories
    assert reloaded.product_lists.affiliate_products == project_data.product_lists.affiliate_products
    assert reloaded.automation.health_check.enabled == project_data.automation.health_check.enabled
