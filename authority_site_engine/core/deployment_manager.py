"""Utilities for pushing Authority Site Engine artifacts into WordPress."""
from __future__ import annotations

import csv
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlparse

from ase_connector_client import ASEJobClient, JobUploadError, SiteConfig

from .models import ProjectData
from .wp_client import WordPressRestClient, WordPressRestError


CSV_LOCATIONS = {
    "pillar": "pillar_posts.csv",
    "supporting": "supporting_posts.csv",
    "info": "info_posts.csv",
    "affiliate_review": "affiliate_product_reviews.csv",
    "amazon_roundup": "amazon_roundups.csv",
}


TYPE_ALIASES = {
    "affiliate": "affiliate_review",
    "reviews": "affiliate_review",
    "informational": "info",
    "information": "info",
    "roundups": "amazon_roundup",
    "amazon": "amazon_roundup",
}


class DeploymentError(RuntimeError):
    """Raised when WordPress deployment prerequisites are missing."""


def _normalize_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.rstrip("/")
    if "/wp-admin" in cleaned:
        cleaned = cleaned.split("/wp-admin", 1)[0]
    return cleaned


def _url_from_domain(domain: str) -> str:
    domain = (domain or "").strip()
    if not domain:
        return ""
    if domain.startswith("http://") or domain.startswith("https://"):
        return _normalize_url(domain)
    return _normalize_url(f"https://{domain}")


@dataclass
class WordPressConnectionInfo:
    site_url: str
    api_base_url: str
    username: str
    password: str


def resolve_wordpress_connection(project: ProjectData) -> WordPressConnectionInfo:
    """Return normalized WordPress REST credentials for the project."""

    deployment = project.deployment
    info = project.basic_info
    site_url = _normalize_url(deployment.site_url) or _normalize_url(info.wp_admin_url)
    if not site_url:
        site_url = _url_from_domain(info.domain_name)
    username = deployment.wp_rest_username or info.wp_username
    password = deployment.wp_app_password or info.wp_password
    api_root = (deployment.wp_api_base_url or "").strip()
    if api_root:
        api_root = api_root.rstrip("/")
    elif site_url:
        api_root = f"{site_url.rstrip('/')}/wp-json/wp/v2"
    if not site_url:
        raise DeploymentError("WordPress site URL is not configured.")
    if not username or not password:
        raise DeploymentError("WordPress username or application password is missing.")
    return WordPressConnectionInfo(
        site_url=site_url,
        api_base_url=api_root,
        username=username,
        password=password,
    )


@dataclass
class DeploymentReport:
    """Simple summary returned after pushing categories or posts."""

    created: int
    reused: int = 0
    skipped: int = 0
    total_rows: int = 0
    errors: List[str] | None = None
    details: Dict[str, object] | None = None


class DeploymentManager:
    """High-level helper that bridges project data with the WordPress REST API."""

    def __init__(
        self,
        project: ProjectData,
        project_root: Path,
        *,
        client: WordPressRestClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project = project
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"
        self.csv_dir = self.outputs_dir / "csv"
        self.logs_dir = self.outputs_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.logs_dir / "deployment_manager.log"
        self.logger = logger or self._configure_logger()
        self.client = client or self._build_client()

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"deployment_manager.{self.project.basic_info.project_name}")
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

    def _build_client(self) -> WordPressRestClient:
        connection = resolve_wordpress_connection(self.project)
        return WordPressRestClient(
            connection.site_url,
            connection.username,
            connection.password,
            api_root=connection.api_base_url,
            logger=self.logger,
        )

    def _build_site_config(self) -> SiteConfig:
        cf = self.project.cloudflare
        host_field = (cf.ssh_host or "").strip()
        host, port = self._parse_host_port(host_field) if host_field else (self._host_from_project(), 22)
        username = cf.ssh_username.strip()
        password = cf.ssh_password.strip()
        if not host or not username or not password:
            raise DeploymentError(
                "SSH host, username, or password is missing. Update the Cloudflare & Host tab first."
            )
        web_root = self._determine_web_root()
        wp_content = self._determine_wp_content(web_root)
        return SiteConfig(
            host=host,
            port=port,
            username=username,
            password=password,
            web_root=web_root,
            wp_content=wp_content,
        )

    def _parse_host_port(self, value: str) -> tuple[str, int]:
        cleaned = value.strip()
        for prefix in ("sftp://", "ssh://", "ftp://"):
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix) :]
                break
        if ":" in cleaned:
            candidate_host, maybe_port = cleaned.rsplit(":", 1)
            if maybe_port.isdigit():
                return candidate_host, int(maybe_port)
        return cleaned, 22

    def _host_from_project(self) -> str:
        for candidate in (
            self.project.deployment.site_url,
            self.project.basic_info.wp_admin_url,
            self.project.basic_info.domain_name,
        ):
            host = self._extract_host(candidate)
            if host:
                return host
        return ""

    def _extract_host(self, url_or_domain: str) -> str:
        if not url_or_domain:
            return ""
        parsed = urlparse(url_or_domain)
        if parsed.scheme:
            return parsed.netloc
        return url_or_domain.split("/", 1)[0]

    def _determine_web_root(self) -> str:
        hint = (self.project.deployment.wp_cli_path or "").strip()
        if not hint or hint.lower() == "wp":
            return ""
        if "/" not in hint and "\\" not in hint:
            return ""
        if hint.endswith("/wp") or hint.endswith("\\wp"):
            hint = hint[:-3]
        return hint.rstrip("/\\")

    def _determine_wp_content(self, web_root: str) -> str:
        if web_root:
            return os.path.join(web_root, "wp-content").replace("\\", "/")
        subdir = self._site_subdir()
        if subdir:
            return f"{subdir}/wp-content"
        return "wp-content"

    def _site_subdir(self) -> str:
        url = self.project.deployment.site_url or self.project.basic_info.wp_admin_url or ""
        if not url:
            return ""
        parsed = urlparse(url)
        return parsed.path.strip("/")

    # ------------------------------------------------------------------
    def test_connection(self) -> Dict[str, object]:
        """Verify that WordPress credentials are valid."""

        try:
            result = self.client.test_connection()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("WordPress connection failed: %s", exc)
            raise DeploymentError(str(exc)) from exc
        return result

    # ------------------------------------------------------------------
    def push_categories(self) -> DeploymentReport:
        categories = [cat.strip() for cat in self.project.categories.categories if cat.strip()]
        if not categories:
            categories = [cat.strip() for cat in self.project.categories.suggestions if cat.strip()]
        if not categories:
            raise DeploymentError("No categories configured for this project.")

        payload = [
            {
                "name": name,
                "slug": self._slugify(name),
                "parent": 0,
            }
            for name in categories
        ]

        site_config = self._build_site_config()
        client = ASEJobClient(site_config)
        try:
            job_path = client.queue_category_job(payload)
        except JobUploadError as exc:
            message = f"Failed to queue category job: {exc}"
            self.logger.error(message)
            raise DeploymentError(message) from exc
        except Exception as exc:  # noqa: BLE001
            message = f"Unexpected ASE Connector error: {exc}"
            self.logger.error(message)
            raise DeploymentError(message) from exc

        self.logger.info("Queued category job via ASE Connector at %s", job_path)
        return DeploymentReport(
            created=0,
            reused=0,
            total_rows=len(payload),
            details={"job_path": job_path},
        )

    # ------------------------------------------------------------------
    def publish_posts_from_csv(
        self,
        csv_type: str,
        *,
        publish_immediately: bool | None = None,
        limit: int | None = None,
    ) -> DeploymentReport:
        post_type = self._normalize_type(csv_type)
        filename = CSV_LOCATIONS.get(post_type)
        if not filename:
            raise DeploymentError(f"Unknown CSV type: {csv_type}")
        csv_path = self.csv_dir / filename
        if not csv_path.exists():
            raise DeploymentError(f"CSV file {filename} is missing. Generate the blueprint first.")
        rows = self._load_csv_rows(csv_path)
        if not rows:
            raise DeploymentError(f"CSV file {filename} is empty.")
        publish_flag = publish_immediately
        if publish_flag is None:
            publish_flag = self.project.posting_preferences.post_immediately
        status = "publish" if publish_flag else "draft"
        category_cache: Dict[str, int] = {}
        created = skipped = 0
        errors: List[str] = []
        tag_cache: Dict[str, int] = {}
        processed_jobs = rows if limit is None else rows[:limit]
        for job in processed_jobs:
            try:
                payload = self._build_post_payload(job, status, category_cache, tag_cache)
                self.client.create_or_update_post(payload)
                created += 1
            except WordPressRestError as exc:
                skipped += 1
                errors.append(f"{job['title']}: {exc}")
                self.logger.error("Failed to create %s: %s", job.get("title"), exc)
            except Exception as exc:  # noqa: BLE001
                skipped += 1
                errors.append(f"{job['title']}: {exc}")
                self.logger.error("Failed to create %s: %s", job.get("title"), exc)
        return DeploymentReport(
            created=created,
            skipped=skipped,
            total_rows=len(rows),
            errors=errors or None,
        )

    # ------------------------------------------------------------------
    def _build_post_payload(
        self,
        job: Dict[str, object],
        status: str,
        category_cache: Dict[str, int],
        tag_cache: Dict[str, int],
    ) -> Dict[str, object]:
        categories = self._ensure_terms(job.get("categories", []), category_cache, self.client.ensure_category)
        tags = self._ensure_terms(job.get("tags", []), tag_cache, self.client.ensure_tag)
        content = job.get("content") or job.get("instructions") or f"<p>{job['title']}</p>"
        payload: Dict[str, object] = {
            "title": job["title"],
            "content": content,
            "status": status,
            "categories": categories,
            "tags": tags,
        }
        if job.get("slug"):
            payload["slug"] = job["slug"]
        return payload

    def _ensure_terms(
        self,
        names: Iterable[str],
        cache: Dict[str, int],
        resolver,
    ) -> List[int]:
        ids: List[int] = []
        for name in names:
            normalized = name.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key not in cache:
                term_id, _ = resolver(normalized)
                cache[key] = term_id
            ids.append(cache[key])
        return ids

    def _slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        return slug or "category"

    def _normalize_type(self, csv_type: str) -> str:
        key = csv_type.strip().lower()
        key = TYPE_ALIASES.get(key, key)
        return key

    def _load_csv_rows(self, csv_path: Path) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        with csv_path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for raw_row in reader:
                job = self._parse_row(raw_row)
                rows.append(job)
        return rows

    def _parse_row(self, row: Dict[str, str]) -> Dict[str, object]:
        normalized = {k.lower(): (v or "").strip() for k, v in row.items() if k}
        title = normalized.get("title") or normalized.get("keyword")
        if not title:
            raise DeploymentError("CSV row is missing a Title or Keyword column.")
        categories_field = normalized.get("category") or normalized.get("categories") or ""
        categories = [token.strip() for token in re.split(r"[|,]", categories_field) if token.strip()]
        if not categories:
            categories = ["General"]
        tags_field = normalized.get("tags", "")
        tags = [tag.strip() for tag in tags_field.split(",") if tag.strip()]
        return {
            "title": title,
            "categories": categories,
            "tags": tags,
            "slug": normalized.get("slug") or None,
            "content": normalized.get("content") or normalized.get("body"),
            "instructions": normalized.get("instructions") or normalized.get("outline"),
        }


__all__ = [
    "DeploymentError",
    "DeploymentManager",
    "DeploymentReport",
    "WordPressConnectionInfo",
    "resolve_wordpress_connection",
]
