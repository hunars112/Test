"""Project creation logic for the Authority Site Engine."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import List

from .credentials import CredentialVault
from .extensions import get_extension_manager
from .migrations import MigrationManager
from .models import (
    AffiliateLinkSet,
    AffiliateOffer,
    AutomationSettings,
    AutomationTaskConfig,
    BasicSiteInfo,
    CategorySettings,
    CloudflareHostInfo,
    ContentStructureSettings,
    DeploymentSettings,
    HealthMonitoringSettings,
    LinkingRules,
    PostingPreferences,
    ProductLists,
    ProjectData,
    ProjectSummary,
    SchemaSettings,
    ZimmWriterSettings,
    ZimmWriterTemplate,
    default_cta_templates,
    default_placeholder_usage,
    default_schema_post_type_map,
)
from .storage import ProjectStorage
from .version import ENGINE_VERSION


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9-_]+", "-", value)
    return value.strip("-") or "project"


class ProjectManager:
    """Create and manage Authority Site Engine projects."""

    def __init__(
        self,
        base_directory: Path | None = None,
        *,
        credential_vault: CredentialVault | None = None,
    ) -> None:
        self.base_directory = base_directory or Path.cwd()
        self.projects_dir = self.base_directory / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.credential_vault = credential_vault or CredentialVault(
            self.base_directory / "credentials" / "vault.json"
        )

    def suggest_categories(self, niche: str) -> List[str]:
        normalized = niche.strip()
        if not normalized:
            return ["Core Topics", "How-To Guides", "Product Reviews", "Trends"]
        title = normalized.title()
        return [
            f"{title} Pillars",
            f"{title} Guides",
            f"{title} Product Reviews",
            f"{title} News & Trends",
        ]

    def create_project(self, project_data: ProjectData) -> Path:
        slug = slugify(project_data.basic_info.project_name)
        project_root = self.projects_dir / slug
        project_data.engine_version = ENGINE_VERSION
        self._store_credentials(slug, project_data)
        storage = ProjectStorage(project_root)
        storage.save(project_data)
        return project_root

    def _store_credentials(self, slug: str, project_data: ProjectData) -> None:
        info = project_data.basic_info
        if info.wp_password:
            identifier = self.credential_vault.store_secret(
                slug,
                "wordpress",
                {"username": info.wp_username, "password": info.wp_password},
            )
            info.wp_credential_id = identifier
        cf = project_data.cloudflare
        if cf.cloudflare_api_key:
            identifier = self.credential_vault.store_secret(
                slug,
                "cloudflare",
                {"api_key": cf.cloudflare_api_key, "email": cf.cloudflare_email},
            )
            cf.credential_id = identifier

    def get_project_root(self, project_name: str) -> Path:
        """Return the root path for a project without touching disk."""

        slug = slugify(project_name)
        return self.projects_dir / slug

    def load_project(self, project_name: str) -> ProjectData:
        slug = slugify(project_name)
        project_root = self.projects_dir / slug
        json_path = project_root / "settings.json"
        if not json_path.exists():
            raise FileNotFoundError(f"Project '{project_name}' does not exist.")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data = MigrationManager(project_root).migrate(data)
        basic_payload = data.get("basic_info", {})
        cloudflare_payload = data.get("cloudflare", {})
        wp_secret = self.credential_vault.retrieve_secret(
            basic_payload.get("wp_credential_id")
        )
        if wp_secret:
            basic_payload["wp_password"] = wp_secret.get("password", "")
        cf_secret = self.credential_vault.retrieve_secret(
            cloudflare_payload.get("credential_id")
        )
        if cf_secret:
            cloudflare_payload["cloudflare_api_key"] = cf_secret.get("api_key", "")
        affiliate_data = data.get("affiliate_links", {})
        schema_data = data.get("schema", {})
        deployment_data = data.get("deployment", {})
        health_data = data.get("health", {})
        offers = [AffiliateOffer(**offer) for offer in affiliate_data.get("offers", [])]
        templates = affiliate_data.get("cta_templates") or default_cta_templates()
        placeholder_usage = affiliate_data.get("placeholder_post_types") or default_placeholder_usage()
        schema_defaults = SchemaSettings()
        schema_mapping = schema_data.get("post_type_schema") or default_schema_post_type_map()
        automation_data = data.get("automation", {})
        automation_defaults = AutomationSettings()

        def _task(name: str, default: AutomationTaskConfig) -> AutomationTaskConfig:
            payload = automation_data.get(name, {}) or {}
            return AutomationTaskConfig(
                enabled=payload.get("enabled", default.enabled),
                interval_hours=payload.get("interval_hours", default.interval_hours),
            )

        automation = AutomationSettings(
            automation_enabled=automation_data.get(
                "automation_enabled", automation_defaults.automation_enabled
            ),
            throttle_seconds=automation_data.get(
                "throttle_seconds", automation_defaults.throttle_seconds
            ),
            log_retention_days=automation_data.get(
                "log_retention_days", automation_defaults.log_retention_days
            ),
            health_check=_task("health_check", automation_defaults.health_check),
            affiliate_check=_task("affiliate_check", automation_defaults.affiliate_check),
            sitemap_ping=_task("sitemap_ping", automation_defaults.sitemap_ping),
            linking_maintenance=_task(
                "linking_maintenance", automation_defaults.linking_maintenance
            ),
            content_review=_task("content_review", automation_defaults.content_review),
            cloudflare_stats=_task("cloudflare_stats", automation_defaults.cloudflare_stats),
            log_cleanup=_task("log_cleanup", automation_defaults.log_cleanup),
        )

        project = ProjectData(
            basic_info=BasicSiteInfo(**basic_payload),
            cloudflare=CloudflareHostInfo(**cloudflare_payload),
            content_structure=ContentStructureSettings(**data["content_structure"]),
            categories=CategorySettings(**data["categories"]),
            product_lists=ProductLists(**data["product_lists"]),
            affiliate_links=AffiliateLinkSet(
                cpa_links=affiliate_data.get("cpa_links", []),
                amazon_links=affiliate_data.get("amazon_links", []),
                custom_links=affiliate_data.get("custom_links", []),
                geo_targeted=affiliate_data.get("geo_targeted", {}),
                backup_url=affiliate_data.get("backup_url", ""),
                offers=offers,
                cta_templates=templates,
                placeholder_post_types=placeholder_usage,
                max_ctas_per_post=affiliate_data.get("max_ctas_per_post", 3),
                rotation_enabled=affiliate_data.get("rotation_enabled", True),
                geo_redirector_url=affiliate_data.get("geo_redirector_url", ""),
            ),
            posting_preferences=PostingPreferences(**data["posting_preferences"]),
            zimmwriter=ZimmWriterSettings(
                templates=[ZimmWriterTemplate(**tpl) for tpl in data["zimmwriter"]["templates"]]
            ),
            linking_rules=LinkingRules(**data["linking_rules"]),
            schema=SchemaSettings(
                inject_method=schema_data.get("inject_method", schema_defaults.inject_method),
                prefer_existing_schema=schema_data.get(
                    "prefer_existing_schema", schema_defaults.prefer_existing_schema
                ),
                site_name=schema_data.get("site_name", schema_defaults.site_name),
                site_url=schema_data.get("site_url", schema_defaults.site_url),
                publisher_logo_url=schema_data.get(
                    "publisher_logo_url", schema_defaults.publisher_logo_url
                ),
                default_author_name=schema_data.get(
                    "default_author_name", schema_defaults.default_author_name
                ),
                default_author_type=schema_data.get(
                    "default_author_type", schema_defaults.default_author_type
                ),
                breadcrumb_enabled=schema_data.get(
                    "breadcrumb_enabled", schema_defaults.breadcrumb_enabled
                ),
                faq_detection_enabled=schema_data.get(
                    "faq_detection_enabled", schema_defaults.faq_detection_enabled
                ),
                schema_meta_key=schema_data.get(
                    "schema_meta_key", schema_defaults.schema_meta_key
                ),
                post_type_schema=schema_mapping,
                marker_start=schema_data.get("marker_start", schema_defaults.marker_start),
                marker_end=schema_data.get("marker_end", schema_defaults.marker_end),
            ),
            deployment=DeploymentSettings(**deployment_data) if deployment_data else DeploymentSettings(),
            health=HealthMonitoringSettings(**health_data) if health_data else HealthMonitoringSettings(),
            automation=automation,
            engine_version=data.get("engine_version", ENGINE_VERSION),
        )
        get_extension_manager(self.base_directory).emit(
            "on_project_load", project=project, project_root=project_root
        )
        return project

    def list_projects(self) -> List[ProjectSummary]:
        """Return lightweight summaries for each saved project."""

        summaries: List[ProjectSummary] = []
        for settings_path in sorted(self.projects_dir.glob("*/settings.json")):
            try:
                payload = json.loads(settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            basic = payload.get("basic_info", {})
            project_name = basic.get("project_name", settings_path.parent.name)
            domain = basic.get("domain_name", "")
            niche = basic.get("niche", "")
            automation_data = payload.get("automation", {})
            automation_enabled = bool(automation_data.get("automation_enabled", False))
            project_root = settings_path.parent
            outputs = project_root / "outputs" / "content"
            status = "Not deployed"
            deployment_path = outputs / "deployment_status.json"
            if deployment_path.exists():
                try:
                    deployment_data = json.loads(deployment_path.read_text(encoding="utf-8"))
                    status = deployment_data.get("overall_status") or deployment_data.get("status", "Deployed")
                except json.JSONDecodeError:
                    status = "Deployment data error"
            health_status = ""
            last_health = ""
            health_path = outputs / "health_status.json"
            if health_path.exists():
                try:
                    health_data = json.loads(health_path.read_text(encoding="utf-8"))
                    health_status = str(health_data.get("overall_status", ""))
                    last_health = str(health_data.get("checked_at", ""))
                except json.JSONDecodeError:
                    health_status = "Error"
            summaries.append(
                ProjectSummary(
                    project_name=project_name,
                    domain=domain,
                    niche=niche,
                    status=status,
                    last_health_check=last_health,
                    automation_enabled=automation_enabled,
                    health_status=health_status,
                    project_root=str(project_root),
                )
            )
        return summaries

    def delete_project(self, project_name: str) -> None:
        """Remove a project directory from disk."""

        project_root = self.get_project_root(project_name)
        if not project_root.exists():
            raise FileNotFoundError(f"Project '{project_name}' does not exist.")
        shutil.rmtree(project_root)
