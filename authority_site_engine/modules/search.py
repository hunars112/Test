"""Global project search helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class SearchResult:
    project_name: str
    match_context: str
    project_root: str


class GlobalProjectSearch:
    """Scan project directories for quick metadata matches."""

    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir

    def search(self, query: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        normalized = query.lower().strip()
        if not normalized:
            return results
        for settings_path in self.projects_dir.glob("*/settings.json"):
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            project_name = data.get("basic_info", {}).get("project_name", settings_path.parent.name)
            context = self._match(normalized, data)
            if context:
                results.append(
                    SearchResult(
                        project_name=project_name,
                        match_context=context,
                        project_root=str(settings_path.parent),
                    )
                )
        return results

    def _match(self, query: str, data: Dict[str, object]) -> str | None:
        if not query:
            return ""
        searchable = json.dumps(data).lower()
        if query in searchable:
            return f"Found '{query}'"
        return None


__all__ = ["GlobalProjectSearch", "SearchResult"]
