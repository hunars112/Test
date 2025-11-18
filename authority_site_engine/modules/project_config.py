"""Project configuration helpers (Part 1)."""
from __future__ import annotations

from pathlib import Path
from typing import List

from ..core.models import ProjectData, ProjectSummary
from ..core.project_manager import ProjectManager
from ..core.storage import ProjectStorage


class ProjectConfigModule:
    """Wrapper around :class:`ProjectManager` exposing Part 1 behaviors."""

    def __init__(self, base_directory: Path | None = None, manager: ProjectManager | None = None) -> None:
        self.manager = manager or ProjectManager(base_directory=base_directory)

    def create_project(self, project_data: ProjectData) -> Path:
        """Persist a brand new project to disk."""

        return self.manager.create_project(project_data)

    def load_project(self, project_name: str) -> ProjectData:
        return self.manager.load_project(project_name)

    def save_project(self, project_data: ProjectData) -> Path:
        project_root = self.manager.get_project_root(project_data.basic_info.project_name)
        storage = ProjectStorage(project_root)
        storage.save(project_data)
        return project_root

    def list_projects(self) -> List[ProjectSummary]:
        return self.manager.list_projects()


__all__ = ["ProjectConfigModule"]
