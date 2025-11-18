"""Helpers for storing checkpoint/resume task state."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


@dataclass
class TaskState:
    task_name: str
    status: str = "idle"
    total_items: int = 0
    last_processed_index: int = -1
    started_at: str = ""
    updated_at: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "task_name": self.task_name,
            "status": self.status,
            "total_items": self.total_items,
            "last_processed_index": self.last_processed_index,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "error_message": self.error_message,
        }


class TaskStateTracker:
    """Persist progress for long-running modules so they can resume."""

    def __init__(self, project_root: Path, task_name: str) -> None:
        self.content_dir = project_root / "outputs" / "content"
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.content_dir / f"task_state_{task_name}.json"
        self.state = TaskState(task_name=task_name)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.state = TaskState(**data)

    def _persist(self) -> None:
        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        self.path.write_text(json.dumps(self.state.to_dict(), indent=2), encoding="utf-8")

    def start(self, total_items: int, *, resume: bool = True) -> TaskState:
        if resume and self.state.status in {"running", "paused", "error"}:
            return self.state
        self.state.status = "running"
        self.state.total_items = total_items
        self.state.last_processed_index = -1
        self.state.started_at = datetime.now(timezone.utc).isoformat()
        self.state.error_message = ""
        self._persist()
        return self.state

    def resume_index(self) -> int:
        if self.state.status in {"running", "paused", "error"}:
            return max(self.state.last_processed_index + 1, 0)
        return 0

    def advance(self, index: int) -> None:
        self.state.last_processed_index = index
        self._persist()

    def mark_error(self, message: str) -> None:
        self.state.status = "error"
        self.state.error_message = message
        self._persist()

    def complete(self) -> None:
        self.state.status = "completed"
        self._persist()

    def reset(self) -> None:
        self.state = TaskState(task_name=self.state.task_name)
        self._persist()


__all__ = ["TaskState", "TaskStateTracker"]
