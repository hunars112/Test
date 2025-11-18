"""Full site deployment engine that orchestrates DNS, WordPress, and content automation."""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

import requests

from .affiliate import AffiliateLinkEngine
from .category_menu import CategoryMenuBuilder
from .internal_linking import InternalLinkingEngine
from .schema import SchemaEngine
from ..core.cloudflare_client import CloudflareClient
from ..core.deployment_manager import resolve_wordpress_connection
from ..core.models import ProjectData
from ..core.wp_client import WordPressRestClient
from .posting import WordPressPostingEngine


DEFAULT_STEPS = [
    "cloudflare",
    "wordpress",
    "theme",
    "plugins",
    "configuration",
    "content",
    "sitemaps",
]


class CommandRunner:
    """Wrapper around subprocess.run so it can be mocked in tests."""

    def run(self, command: Sequence[str]) -> bool:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result.returncode == 0


class DeploymentEngine:
    """Coordinate DNS, WordPress provisioning, and content deployment."""

    def __init__(
        self,
        project_data: ProjectData,
        project_root: Path,
        *,
        client: WordPressRestClient | None = None,
        cloudflare_client: CloudflareClient | None = None,
        command_runner: CommandRunner | None = None,
        logger: logging.Logger | None = None,
        posting_engine_cls=WordPressPostingEngine,
        category_builder_cls=CategoryMenuBuilder,
        linking_engine_cls=InternalLinkingEngine,
        affiliate_engine_cls=AffiliateLinkEngine,
        schema_engine_cls=SchemaEngine,
    ) -> None:
        self.project_data = project_data
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.log_file = self.logs_dir / "deployment_engine.log"
        self.status_path = self.content_dir / "deployment_status.json"
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
        self.cloudflare_client = cloudflare_client
        self.command_runner = command_runner or CommandRunner()
        self.posting_engine_cls = posting_engine_cls
        self.category_builder_cls = category_builder_cls
        self.linking_engine_cls = linking_engine_cls
        self.affiliate_engine_cls = affiliate_engine_cls
        self.schema_engine_cls = schema_engine_cls

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"deployment_engine.{self.project_data.basic_info.project_name}")
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
    def run(self, *, steps: Sequence[str] | None = None, dry_run: bool = False) -> Dict[str, Dict[str, object]]:
        selected = [step for step in (steps or DEFAULT_STEPS) if step in DEFAULT_STEPS]
        if not selected:
            selected = list(DEFAULT_STEPS)
        summary: Dict[str, Dict[str, object]] = {}
        for step in selected:
            handler = getattr(self, f"_step_{step}")
            summary[step] = self._execute_step(step, handler, dry_run=dry_run)
            if not summary[step]["success"] and self.project_data.deployment.strict_mode:
                self.logger.error("Stopping deployment due to strict mode failure on %s", step)
                break
        payload = {
            "project": self.project_data.basic_info.project_name,
            "ran_at": datetime.utcnow().isoformat(),
            "steps": summary,
        }
        self.status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return summary

    def _execute_step(self, name: str, handler, *, dry_run: bool) -> Dict[str, object]:
        try:
            result = handler(dry_run=dry_run)
            if isinstance(result, tuple):
                success, message = result
            else:
                success = bool(result)
                message = ""
            if success:
                self.logger.info("Step %s completed", name)
            else:
                self.logger.info("Step %s skipped or incomplete: %s", name, message)
            return {"success": bool(success), "message": message}
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Step %s failed", name)
            return {"success": False, "message": str(exc)}

    # Individual steps -------------------------------------------------
    def _step_cloudflare(self, *, dry_run: bool):
        settings = self.project_data.deployment
        domain = self.project_data.basic_info.domain_name
        if not settings.configure_cloudflare:
            return True, "Cloudflare configuration disabled"
        records = self.project_data.cloudflare.dns_records
        if not records:
            return False, "No DNS records configured"
        if dry_run:
            return True, f"Would configure {len(records)} DNS records"
        if self.cloudflare_client is None:
            cf = self.project_data.cloudflare
            if not (cf.cloudflare_email and cf.cloudflare_api_key):
                return False, "Missing Cloudflare credentials"
            self.cloudflare_client = CloudflareClient(cf.cloudflare_email, cf.cloudflare_api_key, logger=self.logger)
        self.cloudflare_client.ensure_dns_records(domain, records)
        if settings.enforce_https:
            self.cloudflare_client.set_ssl_mode(domain, settings.cloudflare_ssl_mode or "full")
        return True, f"Configured {len(records)} DNS records"

    def _step_wordpress(self, *, dry_run: bool):
        settings = self.project_data.deployment
        if not settings.install_wordpress:
            return True, "WordPress installation disabled"
        command = self._build_wp_install_command()
        success = self._run_command(command, dry_run=dry_run)
        return success, "Ran wp core install" if success else "wp core install failed"

    def _build_wp_install_command(self) -> List[str]:
        info = self.project_data.basic_info
        settings = self.project_data.deployment
        site_url = info.wp_admin_url.split("/wp-admin", 1)[0]
        admin_email = settings.admin_email or self.project_data.cloudflare.cloudflare_email or "admin@example.com"
        return [
            settings.wp_cli_path,
            "core",
            "install",
            f"--url={site_url}",
            f"--title={settings.site_title or info.project_name}",
            f"--admin_user={info.wp_username}",
            f"--admin_password={info.wp_password}",
            f"--admin_email={admin_email}",
            "--skip-email",
        ]

    def _step_theme(self, *, dry_run: bool):
        settings = self.project_data.deployment
        if not settings.install_theme:
            return True, "Theme installation disabled"
        target = settings.theme_zip_url or settings.theme_slug
        if not target:
            return False, "No theme configured"
        command = [settings.wp_cli_path, "theme", "install", target, "--activate"]
        success = self._run_command(command, dry_run=dry_run)
        return success, f"Installed theme {target}" if success else "Theme install failed"

    def _step_plugins(self, *, dry_run: bool):
        settings = self.project_data.deployment
        plugins = list(settings.plugin_slugs) + list(settings.plugin_zip_urls)
        if not settings.install_plugins or not plugins:
            return True, "Plugin installation disabled"
        all_success = True
        for plugin in plugins:
            command = [settings.wp_cli_path, "plugin", "install", plugin, "--activate"]
            result = self._run_command(command, dry_run=dry_run)
            all_success = all_success and result
        return all_success, f"Processed {len(plugins)} plugins"

    def _step_configuration(self, *, dry_run: bool):
        settings = self.project_data.deployment
        payload = {
            "title": settings.site_title or self.project_data.basic_info.project_name,
            "timezone_string": settings.timezone,
            "permalink_structure": settings.permalink_structure,
            "description": self.project_data.basic_info.niche,
        }
        if settings.admin_email:
            payload["email"] = settings.admin_email
        if dry_run:
            return True, "Would update WordPress settings"
        self.client.update_settings(payload)
        self._cleanup_sample_content()
        return True, "Updated WordPress settings"

    def _cleanup_sample_content(self) -> None:
        posts = self.client.list_posts(per_page=20) or []
        for post in posts:
            title = (post.get("title", {}) or {}).get("rendered", "").lower()
            if title in {"hello world!", "sample page"}:
                post_id = post.get("id")
                if post_id:
                    self.client.delete_post(post_id)
                    self.logger.info("Removed default WordPress content: %s", title)

    def _step_content(self, *, dry_run: bool):
        settings = self.project_data.deployment
        if not settings.deploy_content:
            return True, "Content deployment disabled"
        if dry_run:
            return True, "Would trigger posting and automation"
        posting_engine = self.posting_engine_cls(self.project_data, self.project_root, client=self.client)
        post_map = posting_engine.run()
        details = [f"Published {len(post_map)} posts"]
        if settings.run_category_builder:
            builder = self.category_builder_cls(self.project_data, self.project_root, client=self.client)
            builder.run()
            details.append("synced categories")
        if settings.run_internal_linking:
            linking_engine = self.linking_engine_cls(self.project_data, self.project_root, client=self.client)
            linking_engine.run()
            details.append("applied internal links")
        if settings.run_affiliate:
            affiliate_engine = self.affiliate_engine_cls(self.project_data, self.project_root, client=self.client)
            affiliate_engine.run()
            details.append("injected CTAs")
        if settings.run_schema:
            schema_engine = self.schema_engine_cls(self.project_data, self.project_root, client=self.client)
            schema_engine.run()
            details.append("added schema")
        return True, ", ".join(details)

    def _step_sitemaps(self, *, dry_run: bool):
        settings = self.project_data.deployment
        if not settings.ping_sitemaps:
            return True, "Sitemap pings disabled"
        base_url = self.project_data.schema.site_url or self.project_data.basic_info.wp_admin_url.split("/wp-admin", 1)[0]
        paths = settings.sitemap_paths or ["/wp-sitemap.xml"]
        successes = 0
        for path in paths:
            url = f"{base_url.rstrip('/')}{path}"
            if dry_run:
                self.logger.info("Dry-run sitemap ping: %s", url)
                successes += 1
                continue
            response = requests.get(url, timeout=15)
            if response.ok:
                successes += 1
                self.logger.info("Pinged sitemap %s", url)
            else:
                self.logger.warning("Failed to ping sitemap %s", url)
        return True, f"Pinged {successes} sitemap endpoints"

    # Helpers ----------------------------------------------------------
    def _run_command(self, command: Sequence[str], *, dry_run: bool) -> bool:
        readable = " ".join(command)
        if dry_run:
            self.logger.info("Dry-run command: %s", readable)
            return True
        if self.command_runner is None:
            self.logger.warning("No command runner available for %s", readable)
            return False
        success = self.command_runner.run(command)
        if not success:
            self.logger.warning("Command failed: %s", readable)
        return success


__all__ = ["DeploymentEngine", "CommandRunner"]
