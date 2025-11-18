"""Storage layer for Authority Site Engine projects."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict

from .models import ProjectData


class ProjectStorage:
    """Persist project data to disk in JSON and SQLite formats."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.db_path = self.project_root / "project.db"
        self.json_path = self.project_root / "settings.json"
        self.outputs_dir = self.project_root / "outputs"
        self.csv_dir = self.outputs_dir / "csv"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"

    def prepare_directories(self) -> None:
        for directory in [
            self.project_root,
            self.outputs_dir,
            self.csv_dir,
            self.content_dir,
            self.logs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def save_json(self, project_data: ProjectData) -> None:
        self.json_path.write_text(json.dumps(project_data.to_dict(), indent=2), encoding="utf-8")

    def save_sqlite(self, project_data: ProjectData) -> None:
        payload: Dict[str, object] = project_data.to_dict()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sections (
                    name TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )
            cursor.execute("DELETE FROM sections")
            for name, data in payload.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO sections (name, data) VALUES (?, ?)",
                    (name, json.dumps(data)),
                )
            conn.commit()

    def save(self, project_data: ProjectData) -> None:
        self.prepare_directories()
        self.save_json(project_data)
        self.save_sqlite(project_data)
