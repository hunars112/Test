"""Project migration helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List

from ..version import ENGINE_VERSION

MigrationFunc = Callable[[Dict[str, object]], None]


@dataclass(frozen=True)
class MigrationStep:
    from_version: str
    to_version: str
    func: MigrationFunc


def _ensure_engine_version(payload: Dict[str, object]) -> None:
    payload.setdefault("engine_version", ENGINE_VERSION)


def _add_new_sections(payload: Dict[str, object]) -> None:
    payload.setdefault("automation", {})
    payload.setdefault("health", {})
    payload.setdefault("deployment", {})


MIGRATIONS: List[MigrationStep] = [
    MigrationStep("0.0.0", "1.0.0", _ensure_engine_version),
    MigrationStep("1.0.0", ENGINE_VERSION, _add_new_sections),
]


class MigrationManager:
    """Apply sequential migrations when loading older projects."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root

    def migrate(self, payload: Dict[str, object]) -> Dict[str, object]:
        project_version = payload.get("engine_version") or "0.0.0"
        updated = False
        for step in MIGRATIONS:
            if self._needs(step, project_version):
                step.func(payload)
                payload["engine_version"] = step.to_version
                project_version = step.to_version
                updated = True
        if updated and self.project_root:
            settings_path = self.project_root / "settings.json"
            settings_path.write_text(
                json_dumps(payload),
                encoding="utf-8",
            )
        return payload

    def _needs(self, step: MigrationStep, current: str) -> bool:
        return current < step.to_version


def json_dumps(payload: Dict[str, object]) -> str:
    import json

    return json.dumps(payload, indent=2)


__all__ = ["MigrationManager", "MIGRATIONS"]
