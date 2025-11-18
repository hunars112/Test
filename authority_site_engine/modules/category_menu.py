"""Category and menu builder for Authority Site Engine projects."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from ..core.deployment_manager import resolve_wordpress_connection
from ..core.models import ProjectData
from ..core.wp_client import WordPressRestClient


class CategoryMenuBuilder:
    """Generate WordPress categories and menus based on the topic graph."""

    def __init__(
        self,
        project_data: ProjectData,
        project_root: Path,
        *,
        client: WordPressRestClient | None = None,
        logger: logging.Logger | None = None,
        menu_name: str = "Main Menu",
    ) -> None:
        self.project_data = project_data
        self.project_root = project_root
        self.menu_name = menu_name
        self.outputs_dir = project_root / "outputs"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.topic_graph_path = self.outputs_dir / "topic_graph.json"
        self.post_map_path = self.content_dir / "post_map.json"
        self.category_map_path = self.content_dir / "category_map.json"
        self.log_file = self.logs_dir / "category_menu_builder.log"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or self._configure_logger()
        if client is None:
            connection = resolve_wordpress_connection(project_data)
            client = WordPressRestClient(
                connection.site_url,
                connection.username,
                connection.password,
                api_root=connection.api_base_url,
                logger=self.logger,
            )
        self.client = client

    # ------------------------------------------------------------------
    def run(self) -> Dict[str, object]:
        topic_graph = self._load_topic_graph()
        post_map = self._load_post_map()
        categories = self._determine_categories(topic_graph)
        category_ids = self._ensure_categories(categories)
        assignments = self._assign_posts(topic_graph, post_map, categories, category_ids)
        menu_details = self._build_menu(categories, category_ids)
        category_map = {
            "categories": [
                {"name": name, "id": category_ids[name.lower()]}
                for name in categories
            ],
            "assignments": assignments,
            "menu": menu_details,
        }
        self.category_map_path.write_text(json.dumps(category_map, indent=2), encoding="utf-8")
        self.logger.info("Category + menu builder complete: %s posts updated", len(assignments))
        return category_map

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(
            f"category_menu_builder.{self.project_data.basic_info.project_name}"
        )
        logger.setLevel(logging.INFO)
        if logger.handlers:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _load_topic_graph(self) -> Dict[str, object]:
        if not self.topic_graph_path.exists():
            raise FileNotFoundError("topic_graph.json not found. Run the blueprint generator first.")
        return json.loads(self.topic_graph_path.read_text(encoding="utf-8"))

    def _load_post_map(self) -> List[Dict[str, object]]:
        if not self.post_map_path.exists():
            raise FileNotFoundError("post_map.json not found. Run the posting engine first.")
        return json.loads(self.post_map_path.read_text(encoding="utf-8"))

    def _determine_categories(self, topic_graph: Dict[str, object]) -> List[str]:
        manual = [c.strip() for c in self.project_data.categories.categories if c.strip()]
        if manual:
            base = manual
        elif topic_graph.get("categories"):
            base = [c.strip() for c in topic_graph.get("categories", []) if c.strip()]
        else:
            base = self._categories_from_pillars(topic_graph)
        cleaned: List[str] = []
        for name in base:
            normalized = self._clean_category_name(name)
            if normalized.lower() not in {c.lower() for c in cleaned}:
                cleaned.append(normalized)
            if len(cleaned) == 4:
                break
        if not cleaned:
            cleaned = [self._clean_category_name(self.project_data.basic_info.niche or "Authority Site")]
        return cleaned[:4]

    def _categories_from_pillars(self, topic_graph: Dict[str, object]) -> List[str]:
        result: List[str] = []
        for pillar in topic_graph.get("pillars", []):
            base = pillar.get("category") or pillar.get("title", "")
            if base:
                result.append(base)
        return result or [self.project_data.basic_info.niche]

    def _clean_category_name(self, name: str) -> str:
        words = [word for word in name.split() if word]
        if not words:
            return "Insights"
        limited = words[:3]
        return " ".join(limited).title()

    def _ensure_categories(self, categories: List[str]) -> Dict[str, int]:
        existing = {cat["name"].lower(): cat["id"] for cat in (self.client.list_categories() or [])}
        cat_ids: Dict[str, int] = {}
        for name in categories:
            lower = name.lower()
            if lower not in existing:
                created = self.client.create_category(name)
                existing[lower] = created["id"]
                self.logger.info("Created category '%s'", name)
            else:
                self.logger.info("Category '%s' already exists", name)
            cat_ids[lower] = existing[lower]
        return cat_ids

    def _assign_posts(
        self,
        topic_graph: Dict[str, object],
        post_map: List[Dict[str, object]],
        categories: List[str],
        category_ids: Dict[str, int],
    ) -> List[Dict[str, object]]:
        lookup: Dict[Tuple[str, str], Dict[str, object]] = {}
        for entry in post_map:
            key = (entry.get("post_type", ""), entry.get("post_title", "").lower())
            lookup[key] = entry
        assignments: List[Dict[str, object]] = []
        seen_posts: set[int] = set()
        for pillar in topic_graph.get("pillars", []):
            pillar_cat = self._resolve_category_for_pillar(pillar, categories)
            cat_id = category_ids.get(pillar_cat.lower()) or next(iter(category_ids.values()))
            titles = [("pillar", pillar.get("title"))]
            titles += [("supporting", title) for title in pillar.get("supporting", [])]
            titles += [("info", title) for title in pillar.get("informational", [])]
            titles += [("affiliate_review", title) for title in pillar.get("affiliate_reviews", [])]
            titles += [("amazon_roundup", title) for title in pillar.get("amazon_roundups", [])]
            for post_type, title in titles:
                if not title:
                    continue
                record = lookup.get((post_type, title.lower()))
                if not record:
                    self.logger.warning("No post found for %s '%s'", post_type, title)
                    continue
                post_id = record.get("post_id")
                if not post_id:
                    continue
                self._update_post_category(post_id, cat_id)
                seen_posts.add(post_id)
                assignments.append(
                    {
                        "post_id": post_id,
                        "post_title": record.get("post_title"),
                        "post_type": post_type,
                        "category_id": cat_id,
                        "category_name": pillar_cat,
                    }
                )
        # Assign any remaining posts to the first category to keep structure clean
        default_name = categories[0]
        default_id = category_ids[default_name.lower()]
        for entry in post_map:
            post_id = entry.get("post_id")
            if not post_id or post_id in seen_posts:
                continue
            self._update_post_category(post_id, default_id)
            assignments.append(
                {
                    "post_id": post_id,
                    "post_title": entry.get("post_title"),
                    "post_type": entry.get("post_type"),
                    "category_id": default_id,
                    "category_name": default_name,
                }
            )
        return assignments

    def _resolve_category_for_pillar(self, pillar: Dict[str, object], categories: List[str]) -> str:
        name = pillar.get("category")
        if name and name.lower() in {c.lower() for c in categories}:
            return next(cat for cat in categories if cat.lower() == name.lower())
        return categories[0]

    def _update_post_category(self, post_id: int, category_id: int) -> None:
        self.client.update_post(post_id, {"categories": [category_id]})
        self.logger.info("Assigned post %s to category %s", post_id, category_id)

    def _build_menu(
        self,
        categories: List[str],
        category_ids: Dict[str, int],
    ) -> Dict[str, object]:
        menus = self.client.list_menus() or []
        menu_id = None
        for menu in menus:
            if menu.get("name", "").lower() == self.menu_name.lower():
                menu_id = menu.get("id")
                break
        if menu_id is None:
            created = self.client.create_menu(self.menu_name)
            menu_id = created.get("id")
            self.logger.info("Created menu '%s'", self.menu_name)
        existing_items = self.client.list_menu_items(menu_id) or []
        linked_category_ids = {
            item.get("object_id") for item in existing_items if item.get("object") == "category"
        }
        menu_items = list(existing_items)
        order = len(existing_items) + 1
        for idx, name in enumerate(categories, start=1):
            cat_id = category_ids[name.lower()]
            if cat_id in linked_category_ids:
                continue
            item = self.client.create_menu_item(
                menu_id,
                title=name,
                object_id=cat_id,
                order=order + idx,
            )
            menu_items.append(item)
        return {"menu_id": menu_id, "items": menu_items}


__all__ = ["CategoryMenuBuilder"]
