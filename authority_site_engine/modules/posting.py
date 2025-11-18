"""WordPress posting engine for Authority Site Engine projects."""
from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..core.deployment_manager import resolve_wordpress_connection
from ..core.extensions import get_extension_manager
from ..core.models import ProjectData
from ..core.task_state import TaskStateTracker
from ..core.wp_client import WordPressRestClient


DEFAULT_SEQUENCE = [
    "pillar",
    "supporting",
    "affiliate_review",
    "amazon_roundup",
    "info",
]


CSV_LOCATIONS = {
    "pillar": "pillar_posts.csv",
    "supporting": "supporting_posts.csv",
    "info": "info_posts.csv",
    "affiliate_review": "affiliate_product_reviews.csv",
    "amazon_roundup": "amazon_roundups.csv",
}


CTA_POST_TYPES = {"affiliate_review", "amazon_roundup"}


SEQUENCE_ALIASES = {
    "affiliate": "affiliate_review",
    "review": "affiliate_review",
    "reviews": "affiliate_review",
    "product_reviews": "affiliate_review",
    "informational": "info",
    "information": "info",
    "info_posts": "info",
    "amazon": "amazon_roundup",
    "roundup": "amazon_roundup",
}


@dataclass
class PostJob:
    """Representation of a post row extracted from CSV."""

    post_type: str
    title: str
    category_names: List[str]
    tags: List[str] = field(default_factory=list)
    slug: str | None = None
    content: str | None = None
    instructions: str | None = None
    featured_image: str | None = None
    post_id: Optional[int] = None

    @classmethod
    def from_csv(cls, post_type: str, row: Dict[str, str]) -> "PostJob":
        normalized = {k.lower(): (v or "").strip() for k, v in row.items() if k}
        title = normalized.get("title") or normalized.get("keyword")
        if not title:
            raise ValueError("CSV row missing required 'Title' column")
        raw_categories = normalized.get("category") or normalized.get("categories") or ""
        category_tokens = [token.strip() for token in re.split(r"[|,]", raw_categories) if token.strip()]
        categories = [c for c in {token: None for token in category_tokens}.keys()]
        if not categories:
            categories = ["General"]
        tags = normalized.get("tags", "")
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        slug = normalized.get("slug") or None
        content = normalized.get("content") or None
        instructions = normalized.get("instructions") or None
        featured_image = normalized.get("featured_image") or normalized.get("image") or None
        post_id_str = normalized.get("post_id")
        post_id = int(post_id_str) if post_id_str and post_id_str.isdigit() else None
        return cls(
            post_type=post_type,
            title=title,
            category_names=categories,
            tags=tag_list,
            slug=slug,
            content=content,
            instructions=instructions,
            featured_image=featured_image,
            post_id=post_id,
        )


class WordPressPostingEngine:
    """Create or update WordPress posts from project CSV artifacts."""

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
        self.csv_dir = self.outputs_dir / "csv"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.post_map_path = self.content_dir / "post_map.json"
        self.log_file = self.logs_dir / "posting_engine.log"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or self._configure_logger()
        self.task_state = TaskStateTracker(project_root, "posting")
        if client is None:
            site_url, username, password = resolve_wordpress_connection(project_data)
            client = WordPressRestClient(
                site_url,
                username,
                password,
                logger=self.logger,
            )
        self.client = client
        self.post_map: List[Dict[str, object]] = []

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"posting_engine.{self.project_data.basic_info.project_name}")
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

    # ------------------------------------------------------------------
    def run(
        self,
        *,
        zimmwriter_managed: bool = False,
        resume: bool = True,
    ) -> List[Dict[str, object]]:
        """Execute the posting flow and return the generated post map."""

        self.logger.info("Starting WordPress posting engine")
        posts = self._load_posts_from_csvs()
        topic_graph = self._load_topic_graph()
        category_cache = self._sync_categories(posts, topic_graph)
        tag_cache = self._sync_tags(posts)
        scheduler = self._build_scheduler()
        total_jobs = sum(len(items) for items in posts.values())
        self.task_state.start(total_jobs, resume=resume)
        start_index = self.task_state.resume_index() if resume else 0
        current_index = -1

        user_sequence = self.project_data.posting_preferences.publish_sequence or DEFAULT_SEQUENCE
        sequence = [self._normalize_post_type(ptype) for ptype in user_sequence]
        sequence = [ptype for ptype in sequence if ptype]
        ordered_types = [ptype for ptype in sequence if ptype in posts]
        for fallback in DEFAULT_SEQUENCE:
            if fallback not in ordered_types:
                ordered_types.append(fallback)

        try:
            for post_type in ordered_types:
                for job in posts.get(post_type, []):
                    current_index += 1
                    if current_index < start_index:
                        continue
                    scheduled_date, status = scheduler()
                    payload = self._build_post_payload(
                        job, category_cache, tag_cache, scheduled_date, status
                    )
                    response = self._dispatch_post(job, payload, zimmwriter_managed)
                    self._record_post(job, response, scheduled_date)
                    self.task_state.advance(current_index)
        except Exception as exc:
            self.task_state.mark_error(str(exc))
            raise

        self.task_state.complete()
        self.post_map_path.write_text(json.dumps(self.post_map, indent=2), encoding="utf-8")
        self.logger.info("Posting engine completed %s posts", len(self.post_map))
        get_extension_manager(self.project_root).emit(
            "on_posting_completed", project=self.project_data, post_map=self.post_map
        )
        return self.post_map

    # ------------------------------------------------------------------
    def _load_topic_graph(self) -> Dict[str, object]:
        path = self.outputs_dir / "topic_graph.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _load_posts_from_csvs(self) -> Dict[str, List[PostJob]]:
        jobs: Dict[str, List[PostJob]] = {}
        for post_type, filename in CSV_LOCATIONS.items():
            path = self.csv_dir / filename
            if not path.exists():
                jobs[post_type] = []
                continue
            with path.open(encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = [PostJob.from_csv(post_type, row) for row in reader]
                jobs[post_type] = rows
        return jobs

    def _normalize_post_type(self, value: str | None) -> Optional[str]:
        if not value:
            return None
        value = value.strip().lower()
        if value in CSV_LOCATIONS:
            return value
        return SEQUENCE_ALIASES.get(value)

    def _sync_categories(
        self,
        posts: Dict[str, List[PostJob]],
        topic_graph: Dict[str, object],
    ) -> Dict[str, int]:
        existing = {cat["name"].lower(): cat["id"] for cat in self.client.list_categories() or []}
        category_cache: Dict[str, int] = dict(existing)
        requested_names = set()
        for job_list in posts.values():
            for job in job_list:
                requested_names.update({name.strip() for name in job.category_names if name.strip()})
        if topic_graph.get("categories"):
            requested_names.update(topic_graph["categories"])
        requested_names.update(self.project_data.categories.categories)
        for name in requested_names:
            lower = name.lower()
            if lower in category_cache:
                continue
            created = self.client.create_category(name)
            category_cache[lower] = created["id"]
        return category_cache

    def _sync_tags(self, posts: Dict[str, List[PostJob]]) -> Dict[str, int]:
        existing = {tag["name"].lower(): tag["id"] for tag in self.client.list_tags() or []}
        tag_cache = dict(existing)
        requested: Dict[str, str] = {}
        for job_list in posts.values():
            for job in job_list:
                for tag in job.tags:
                    lower = tag.lower()
                    requested.setdefault(lower, tag)
        for lower, original in requested.items():
            if lower in tag_cache:
                continue
            created = self.client.create_tag(original)
            tag_cache[lower] = created["id"]
        return tag_cache

    def _build_scheduler(self):
        prefs = self.project_data.posting_preferences
        start = datetime.now(timezone.utc)
        interval = timedelta(hours=max(1, prefs.scheduling_interval_hours or 1))

        def next_schedule():
            nonlocal start
            if prefs.post_immediately:
                return None, "publish"
            scheduled = start
            if prefs.drip_posting:
                start = start + interval
            return scheduled.isoformat(), "future"

        return next_schedule

    def _build_post_payload(
        self,
        job: PostJob,
        categories: Dict[str, int],
        tags: Dict[str, int],
        scheduled_date: Optional[str],
        status: str,
    ) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "title": job.title,
            "status": status,
            "content": self._compose_content(job),
            "categories": [categories[name.lower()] for name in job.category_names if name.lower() in categories],
            "tags": [tags[tag.lower()] for tag in job.tags if tag.lower() in tags],
        }
        if not payload["categories"] and categories:
            payload["categories"] = [next(iter(categories.values()))]
        if scheduled_date:
            payload["date_gmt"] = scheduled_date
        if job.slug:
            payload["slug"] = job.slug
        if job.instructions:
            payload.setdefault("meta", {})["instructions"] = job.instructions
        if job.featured_image:
            media_id = self._upload_featured_image(job.featured_image)
            if media_id:
                payload["featured_media"] = media_id
        return payload

    def _compose_content(self, job: PostJob) -> str:
        body = job.content or f"Placeholder content for {job.title}."
        if job.post_type in CTA_POST_TYPES:
            return f"[CTA_TOP]\n\n{body}\n\n[CTA_BOTTOM]"
        return body

    def _upload_featured_image(self, reference: str) -> Optional[int]:
        path = Path(reference)
        if path.exists():
            data = path.read_bytes()
            response = self.client.upload_media(path.name, data, "image/jpeg")
            return response.get("id")
        return None

    def _dispatch_post(self, job: PostJob, payload: Dict[str, object], zimmwriter: bool):
        if zimmwriter and job.post_id:
            self.logger.info("Updating existing post %s", job.post_id)
            return self.client.update_post(job.post_id, payload)
        self.logger.info("Creating %s post '%s'", job.post_type, job.title)
        return self.client.create_post(payload)

    def _record_post(self, job: PostJob, response: Dict[str, object], scheduled_date: Optional[str]) -> None:
        record = {
            "post_id": response.get("id"),
            "post_type": job.post_type,
            "post_title": job.title,
            "post_url": response.get("link"),
            "scheduled_date": scheduled_date,
        }
        if "categories" in response:
            record["category_ids"] = response["categories"]
        if "tags" in response:
            record["tag_ids"] = response["tags"]
        self.post_map.append(record)


__all__ = ["WordPressPostingEngine", "PostJob"]
