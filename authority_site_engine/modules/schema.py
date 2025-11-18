"""JSON-LD schema engine for Authority Site Engine projects."""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

from ..core.extensions import get_extension_manager
from ..core.deployment_manager import resolve_wordpress_connection
from ..core.models import ProjectData
from ..core.task_state import TaskStateTracker
from ..core.wp_client import WordPressRestClient


class SchemaEngine:
    """Generate and inject JSON-LD schema for each WordPress post."""

    def __init__(
        self,
        project_data: ProjectData,
        project_root: Path,
        *,
        client: WordPressRestClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project_data = project_data
        self.schema = project_data.schema
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.post_map_path = self.content_dir / "post_map.json"
        self.category_map_path = self.content_dir / "category_map.json"
        self.schema_map_path = self.content_dir / "schema_map.json"
        self.log_file = self.logs_dir / "schema_engine.log"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or self._configure_logger()
        self.task_state = TaskStateTracker(project_root, "schema")
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
    def run(
        self,
        *,
        dry_run: bool = False,
        partial: bool = False,
        resume: bool = True,
    ) -> List[Dict[str, object]]:
        """Generate schema for each post and inject it via the configured method."""

        post_map = self._load_post_map()
        assignments = self._load_category_assignments()
        existing_map = self._load_schema_map()
        if partial and existing_map:
            processed_ids = {entry.get("post_id") for entry in existing_map}
            post_map = [entry for entry in post_map if entry.get("post_id") not in processed_ids]
        self.task_state.start(len(post_map), resume=resume)
        start_index = self.task_state.resume_index() if resume else 0
        summaries: List[Dict[str, object]] = []
        try:
            for index, entry in enumerate(post_map):
                if index < start_index:
                    continue
                post_id = entry.get("post_id")
                post_type = entry.get("post_type", "")
                if not post_id or not post_type:
                    self.task_state.advance(index)
                    continue
                types = self.schema.post_type_schema.get(post_type, {})
                if not any(types.values()) and not self.schema.breadcrumb_enabled:
                    self.task_state.advance(index)
                    continue
                post_id_int = int(post_id)
                wp_post = self.client.get_post(post_id_int)
                schema_objects = self._build_schema_components(
                    entry, wp_post, assignments.get(post_id_int, {})
                )
                if not schema_objects:
                    self.task_state.advance(index)
                    continue
                schema_json = json.dumps(schema_objects, indent=2)
                summary = {
                    "post_id": post_id_int,
                    "post_title": entry.get("post_title"),
                    "post_type": post_type,
                    "schema_types": [obj.get("@type") for obj in schema_objects],
                }
                if dry_run:
                    summaries.append(summary)
                    self.logger.info(
                        "Planned schema update for post %s with %s blocks",
                        post_id_int,
                        len(schema_objects),
                    )
                    self.task_state.advance(index)
                    continue
                method = (self.schema.inject_method or "content").lower()
                if method not in {"content", "meta"}:
                    method = "content"
                if method == "meta":
                    if self._inject_meta(post_id_int, schema_json, wp_post):
                        summaries.append(summary)
                else:
                    content = wp_post.get("content", {}).get("rendered", "")
                    updated = self._inject_content(content, schema_json)
                    if updated != content:
                        self.client.update_post(post_id_int, {"content": updated})
                        summaries.append(summary)
                        self.logger.info(
                            "Updated post %s with schema via content", post_id_int
                        )
                self.task_state.advance(index)
        except Exception as exc:
            self.task_state.mark_error(str(exc))
            raise
        self.task_state.complete()
        replace = not partial and start_index == 0
        self._write_schema_map(summaries, replace=replace)
        if summaries:
            self.logger.info("Schema engine updated %s posts", len(summaries))
        else:
            self.logger.info("Schema engine completed with no changes")
        get_extension_manager(self.project_root).emit(
            "on_schema_completed",
            project=self.project_data,
            schema_updates=summaries,
        )
        return summaries

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(
            f"schema_engine.{self.project_data.basic_info.project_name}"
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

    def _load_post_map(self) -> List[Dict[str, object]]:
        if not self.post_map_path.exists():
            raise FileNotFoundError("post_map.json not found. Run the posting engine first.")
        return json.loads(self.post_map_path.read_text(encoding="utf-8"))

    def _load_category_assignments(self) -> Dict[int, Dict[str, object]]:
        if not self.category_map_path.exists():
            return {}
        data = json.loads(self.category_map_path.read_text(encoding="utf-8"))
        assignments: Dict[int, Dict[str, object]] = {}
        for entry in data.get("assignments", []):
            post_id = entry.get("post_id")
            if not post_id:
                continue
            assignments[int(post_id)] = entry
        return assignments

    # ------------------------------------------------------------------
    def _build_schema_components(
        self,
        entry: Dict[str, object],
        wp_post: Dict[str, object],
        assignment: Dict[str, object],
    ) -> List[Dict[str, object]]:
        types = self.schema.post_type_schema.get(entry.get("post_type", ""), {})
        components: List[Dict[str, object]] = []
        description = self._extract_description(wp_post, entry)
        category_name = assignment.get("category_name") or entry.get("category") or "Insights"
        if types.get("article"):
            components.append(self._build_article_schema(entry, wp_post, description, category_name))
        if types.get("product"):
            product = self._build_product_schema(entry, description)
            if product:
                components.append(product)
        if types.get("review"):
            review = self._build_review_schema(entry, description)
            if review:
                components.append(review)
        if types.get("faq"):
            faq = self._build_faq_schema(entry)
            if faq:
                components.append(faq)
        if self.schema.breadcrumb_enabled:
            breadcrumb = self._build_breadcrumb_schema(entry, category_name)
            if breadcrumb:
                components.append(breadcrumb)
        return components

    def _build_article_schema(
        self,
        entry: Dict[str, object],
        wp_post: Dict[str, object],
        description: str,
        category_name: str,
    ) -> Dict[str, object]:
        headline = entry.get("post_title") or "Authority Article"
        url = entry.get("post_url") or wp_post.get("link") or self._site_url()
        published = self._normalize_date(wp_post.get("date"))
        modified = self._normalize_date(wp_post.get("modified")) or published
        author_name = self.schema.default_author_name or self.project_data.basic_info.wp_username
        author_type = self.schema.default_author_type or "Person"
        publisher_name = self.schema.site_name or self.project_data.basic_info.project_name
        article: Dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": headline,
            "description": description,
            "articleSection": category_name,
            "author": {"@type": author_type, "name": author_name},
            "datePublished": published,
            "dateModified": modified,
            "mainEntityOfPage": {"@type": "WebPage", "@id": url},
            "publisher": {"@type": "Organization", "name": publisher_name},
        }
        if self.schema.publisher_logo_url:
            article["publisher"]["logo"] = {
                "@type": "ImageObject",
                "url": self.schema.publisher_logo_url,
            }
        return article

    def _build_product_schema(
        self, entry: Dict[str, object], description: str
    ) -> Dict[str, object] | None:
        name = entry.get("post_title")
        if not name:
            return None
        offer_url = self._default_offer_url()
        product: Dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": name,
            "description": description,
        }
        if offer_url:
            product["offers"] = [
                {
                    "@type": "Offer",
                    "url": offer_url,
                    "availability": "https://schema.org/InStock",
                }
            ]
        return product

    def _build_review_schema(
        self, entry: Dict[str, object], description: str
    ) -> Dict[str, object] | None:
        name = entry.get("post_title")
        if not name:
            return None
        author_name = self.schema.default_author_name or "Editorial Team"
        review: Dict[str, object] = {
            "@context": "https://schema.org",
            "@type": "Review",
            "author": {"@type": "Person", "name": author_name},
            "itemReviewed": {"@type": "Product", "name": name},
            "reviewBody": description,
        }
        return review

    def _build_faq_schema(self, entry: Dict[str, object]) -> Dict[str, object] | None:
        faqs: Sequence[Dict[str, str]] = entry.get("faqs") or []
        formatted = []
        for faq in faqs:
            question = faq.get("question")
            answer = faq.get("answer")
            if not question or not answer:
                continue
            formatted.append(
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {"@type": "Answer", "text": answer},
                }
            )
        if not formatted:
            return None
        return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": formatted}

    def _build_breadcrumb_schema(
        self, entry: Dict[str, object], category_name: str
    ) -> Dict[str, object] | None:
        site_url = self._site_url()
        post_url = entry.get("post_url") or site_url
        category_url = f"{site_url}/category/{self._slugify(category_name)}/"
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Home",
                    "item": site_url,
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": category_name,
                    "item": category_url,
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": entry.get("post_title", "Post"),
                    "item": post_url,
                },
            ],
        }

    # ------------------------------------------------------------------
    def _inject_content(self, content: str, schema_json: str) -> str:
        pattern = self._schema_block_pattern()
        block = (
            f"{self.schema.marker_start}\n"
            f"<script type=\"application/ld+json\">\n{schema_json}\n</script>\n"
            f"{self.schema.marker_end}"
        )
        if self.schema.prefer_existing_schema and pattern.search(content):
            return content
        if pattern.search(content):
            return pattern.sub(block, content, count=1)
        if content and not content.endswith("\n"):
            content = f"{content}\n"
        return f"{content}\n{block}\n"

    def _inject_meta(self, post_id: int, schema_json: str, wp_post: Dict[str, object]) -> bool:
        meta = wp_post.get("meta") or {}
        existing = meta.get(self.schema.schema_meta_key)
        if existing == schema_json:
            return False
        self.client.update_post(
            post_id,
            {"meta": {self.schema.schema_meta_key: schema_json}},
        )
        self.logger.info("Updated post %s schema via meta", post_id)
        return True

    def _write_schema_map(
        self,
        summaries: List[Dict[str, object]],
        *,
        replace: bool,
    ) -> None:
        existing = []
        if not replace and self.schema_map_path.exists():
            existing = json.loads(self.schema_map_path.read_text(encoding="utf-8")).get(
                "entries", []
            )
        combined = existing if not replace else []
        combined.extend(summaries)
        payload = {"entries": combined, "updated_at": datetime.utcnow().isoformat()}
        self.schema_map_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_schema_map(self) -> List[Dict[str, object]]:
        if not self.schema_map_path.exists():
            return []
        data = json.loads(self.schema_map_path.read_text(encoding="utf-8"))
        return data.get("entries", [])

    # ------------------------------------------------------------------
    def _extract_description(self, wp_post: Dict[str, object], entry: Dict[str, object]) -> str:
        content = wp_post.get("excerpt", {}).get("rendered") or wp_post.get("content", {}).get("rendered", "")
        text = html.unescape(re.sub(r"<[^>]+>", " ", content or ""))
        if not text.strip():
            text = entry.get("post_title", "")
        normalized = " ".join(text.split())
        return normalized[:320]

    def _default_offer_url(self) -> str:
        affiliates = self.project_data.affiliate_links
        for collection in [affiliates.cpa_links, affiliates.custom_links, affiliates.amazon_links]:
            if collection:
                return collection[0]
        return affiliates.backup_url

    def _site_url(self) -> str:
        if self.schema.site_url:
            return self.schema.site_url.rstrip("/")
        domain = self.project_data.basic_info.domain_name
        if domain.startswith("http"):
            return domain.rstrip("/")
        return f"https://{domain}".rstrip("/")

    def _normalize_date(self, value) -> str:
        if isinstance(value, str) and value:
            return value
        return datetime.utcnow().isoformat()

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
        return cleaned.strip("-") or "category"

    def _schema_block_pattern(self) -> re.Pattern[str]:
        return re.compile(
            rf"{re.escape(self.schema.marker_start)}.*?{re.escape(self.schema.marker_end)}",
            re.DOTALL,
        )


__all__ = ["SchemaEngine"]
