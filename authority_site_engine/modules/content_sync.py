"""WordPress content sync helpers."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

from ..core.models import ProjectData
from ..core.wp_client import WordPressRestClient


class ContentSyncModule:
    """Pull posts from WordPress to refresh local post_map.json."""

    def __init__(
        self,
        project_data: ProjectData,
        project_root: Path,
        *,
        client: WordPressRestClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project_data = project_data
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.post_map_path = self.content_dir / "post_map.json"
        self.log_file = self.logs_dir / "content_sync.log"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(
            f"content_sync.{project_data.basic_info.project_name}"
        )
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        if client is None:
            info = project_data.basic_info
            client = WordPressRestClient(
                info.wp_admin_url,
                info.wp_username,
                info.wp_password,
                logger=self.logger,
            )
        self.client = client

    def sync(self, *, status: str = "publish") -> List[Dict[str, object]]:
        posts: List[Dict[str, object]] = []
        page = 1
        while True:
            batch = self.client.list_posts(per_page=100, page=page, context="edit", status=status)
            if not batch:
                break
            posts.extend(batch)
            page += 1
        normalized = [
            {
                "post_id": item.get("id"),
                "post_title": item.get("title", {}).get("rendered", item.get("title")),
                "post_type": item.get("ase_post_type", "info"),
                "post_url": item.get("link"),
                "category_ids": item.get("categories", []),
                "tag_ids": item.get("tags", []),
                "scheduled_date": item.get("date"),
            }
            for item in posts
        ]
        if normalized:
            self.post_map_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        self.logger.info("Content sync captured %s posts", len(normalized))
        return normalized


__all__ = ["ContentSyncModule"]
