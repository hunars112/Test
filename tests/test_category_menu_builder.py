"""Tests for the category and menu builder."""

from authority_site_engine.modules.category_menu import CategoryMenuBuilder
from authority_site_engine.modules.posting import WordPressPostingEngine

from tests.factories import FakeWordPressClient, prepare_project


def test_category_menu_builder_creates_categories_and_menu(tmp_path):
    project_data, project_root = prepare_project(tmp_path)
    client = FakeWordPressClient()
    posting_engine = WordPressPostingEngine(project_data, project_root, client=client)
    posting_engine.run()

    builder = CategoryMenuBuilder(project_data, project_root, client=client)
    category_map = builder.run()

    assert category_map["categories"], "Categories should be generated"
    assert len(category_map["categories"]) <= 4
    assert category_map["assignments"], "Posts must be assigned to categories"
    assert category_map["menu"]["items"], "Menu items should be created"

    log_path = project_root / "outputs" / "logs" / "category_menu_builder.log"
    assert log_path.exists()
    assert "Category + menu builder" in log_path.read_text()

    category_map_path = project_root / "outputs" / "content" / "category_map.json"
    assert category_map_path.exists()
