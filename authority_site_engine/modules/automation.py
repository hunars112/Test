"""Daily automation scheduler for Authority Site Engine projects."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Sequence

from .affiliate import AffiliateLinkEngine
from .health import SiteHealthMonitor
from .internal_linking import InternalLinkingEngine
from .storage_cleanup import StorageCleanup
from ..core.cloudflare_client import CloudflareClient
from ..core.extensions import get_extension_manager
from ..core.http_client import RequestsHttpClient
from ..core.models import AutomationTaskConfig, ProjectData, default_sitemap_paths
from ..core.wp_client import WordPressRestClient


@dataclass
class TaskResult:
    """Simple structure describing an automation task run."""

    task: str
    status: str
    message: str


class DailyAutomationScheduler:
    """Evaluate and run recurring maintenance tasks per project."""

    TASK_METHODS = {
        "health_check": "_run_health_monitor",
        "affiliate_check": "_run_affiliate_check",
        "sitemap_ping": "_run_sitemap_ping",
        "linking_maintenance": "_run_linking_maintenance",
        "content_review": "_run_content_review",
        "cloudflare_stats": "_run_cloudflare_stats",
        "log_cleanup": "_run_log_cleanup",
    }

    def __init__(
        self,
        project_data: ProjectData,
        project_root: Path,
        *,
        http_client: RequestsHttpClient | None = None,
        cloudflare_client: CloudflareClient | None = None,
        wp_client: WordPressRestClient | None = None,
        logger: logging.Logger | None = None,
        sleep_fn=None,
    ) -> None:
        self.project_data = project_data
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.content_dir / "automation_state.json"
        self.log_file = self.logs_dir / "automation.log"
        self.logger = logger or self._configure_logger()
        self.settings = project_data.automation
        timeout = max(5, project_data.health.http_timeout)
        self.http_client = http_client or RequestsHttpClient(timeout=timeout)
        info = project_data.basic_info
        self.wp_client = wp_client or WordPressRestClient(
            info.wp_admin_url,
            info.wp_username,
            info.wp_password,
            logger=self.logger,
        )
        if cloudflare_client is None and project_data.cloudflare.cloudflare_email:
            cf = project_data.cloudflare
            if cf.cloudflare_email and cf.cloudflare_api_key:
                cloudflare_client = CloudflareClient(
                    cf.cloudflare_email,
                    cf.cloudflare_api_key,
                    logger=self.logger,
                )
        self.cloudflare_client = cloudflare_client
        self.sleep_fn = sleep_fn or time.sleep
        self.state = self._load_state()

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(
            f"automation.{self.project_data.basic_info.project_name}"
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

    # ------------------------------------------------------------------
    def run(
        self,
        *,
        force: bool = False,
        tasks: Sequence[str] | None = None,
        now: datetime | None = None,
    ) -> List[TaskResult]:
        """Run due automation tasks and persist their state."""

        now = now or datetime.utcnow()
        manual_selection = bool(tasks)
        task_filter = set(tasks or [])
        if (
            not self.settings.automation_enabled
            and not force
            and not manual_selection
        ):
            self.logger.info("Automation disabled; skipping run")
            return []

        results: List[TaskResult] = []
        for task_name, method in self.TASK_METHODS.items():
            if task_filter and task_name not in task_filter:
                continue
            config: AutomationTaskConfig = getattr(self.settings, task_name)
            if not config.enabled and not force and not manual_selection:
                continue
            if not (force or manual_selection) and not self._is_due(task_name, config, now):
                continue
            handler = getattr(self, method)
            status = "success"
            message = ""
            try:
                message = handler()
            except Exception as exc:  # pragma: no cover - defensive logging
                status = "error"
                message = str(exc)
                self.logger.exception("Automation task %s failed", task_name)
            self._record_task(task_name, config, status, message, now)
            results.append(TaskResult(task=task_name, status=status, message=message))
            if self.settings.throttle_seconds > 0:
                self.sleep_fn(self.settings.throttle_seconds)
        self._save_state()
        get_extension_manager(self.project_root).emit(
            "on_daily_automation",
            project=self.project_data,
            results=[result.__dict__ for result in results],
        )
        return results

    # ------------------------------------------------------------------
    def _load_state(self) -> Dict[str, object]:
        if not self.state_path.exists():
            return {"tasks": {}}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"tasks": {}}

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _record_task(
        self,
        name: str,
        config: AutomationTaskConfig,
        status: str,
        message: str,
        now: datetime,
    ) -> None:
        tasks = self.state.setdefault("tasks", {})
        next_run = now + timedelta(hours=max(0, config.interval_hours))
        tasks[name] = {
            "last_run": now.isoformat(),
            "next_run": next_run.isoformat(),
            "status": status,
            "message": message,
        }
        self.logger.info("%s -> %s (%s)", name, status, message)

    def _is_due(
        self, name: str, config: AutomationTaskConfig, now: datetime
    ) -> bool:
        tasks = self.state.get("tasks", {})
        record = tasks.get(name)
        if not record:
            return True
        last_run = record.get("last_run")
        if not last_run:
            return True
        try:
            last_dt = datetime.fromisoformat(last_run)
        except ValueError:
            return True
        interval = timedelta(hours=max(0, config.interval_hours))
        return now >= last_dt + interval

    # ------------------------------------------------------------------
    def _run_health_monitor(self) -> str:
        monitor = SiteHealthMonitor(
            self.project_data,
            self.project_root,
            http_client=self.http_client,
            cloudflare_client=self.cloudflare_client,
        )
        status = monitor.run()
        return f"overall={status.get('overall_status', 'unknown')}"

    def _run_affiliate_check(self) -> str:
        engine = AffiliateLinkEngine(
            self.project_data,
            self.project_root,
            client=self.wp_client,
            logger=self.logger,
        )
        results = engine.run(dry_run=True)
        return f"planned_posts={len(results)}"

    def _run_sitemap_ping(self) -> str:
        base = self._base_site_url()
        paths = self.project_data.deployment.sitemap_paths or default_sitemap_paths()
        successes = 0
        for path in paths:
            url = f"{base}{path}"
            try:
                response = self.http_client.get(url)
                if 200 <= response.status_code < 400:
                    successes += 1
            except Exception as exc:  # pragma: no cover - network safety
                self.logger.warning("Sitemap ping failed for %s: %s", url, exc)
        return f"reachable_sitemaps={successes}/{len(paths)}"

    def _run_linking_maintenance(self) -> str:
        engine = InternalLinkingEngine(
            self.project_data,
            self.project_root,
            client=self.wp_client,
            logger=self.logger,
        )
        plan = engine.run(dry_run=True)
        return f"planned_links={len(plan)}"

    def _run_content_review(self) -> str:
        post_map_path = self.content_dir / "post_map.json"
        if not post_map_path.exists():
            raise FileNotFoundError("post_map.json missing")
        entries = json.loads(post_map_path.read_text(encoding="utf-8"))
        counts: Dict[str, int] = {}
        for entry in entries:
            post_type = entry.get("post_type", "unknown")
            counts[post_type] = counts.get(post_type, 0) + 1
        plan = self.project_data.content_structure
        targets = {
            "pillar": plan.pillar_posts,
            "supporting": plan.pillar_posts * plan.supporting_posts_per_pillar,
            "info": plan.informational_posts,
            "affiliate_review": plan.affiliate_product_posts,
            "amazon_roundup": plan.amazon_roundup_posts,
        }
        lagging = []
        for key, expected in targets.items():
            if expected <= 0:
                continue
            actual = counts.get(key, 0)
            if actual < expected:
                lagging.append(f"{key}:{actual}/{expected}")
        summary = ", ".join(lagging) if lagging else "on_track"
        audit_path = self.content_dir / "content_audit.json"
        audit_path.write_text(json.dumps({"counts": counts, "lagging": lagging}, indent=2), encoding="utf-8")
        return summary

    def _run_cloudflare_stats(self) -> str:
        if not self.cloudflare_client:
            return "cloudflare_disabled"
        domain = self.project_data.basic_info.domain_name
        payload = self.cloudflare_client.fetch_analytics(
            domain,
            since_hours=max(1, self.project_data.health.cloudflare_hours),
        )
        stats_path = self.content_dir / "cloudflare_stats.json"
        stats_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return "stats_updated"

    def _run_log_cleanup(self) -> str:
        retention_days = max(1, int(self.settings.log_retention_days or 1))
        cleanup = StorageCleanup(
            self.project_root,
            max_log_age_days=retention_days,
            delete_old_csv_after_posting=not self.project_data.posting_preferences.drip_posting,
        )
        results = cleanup.run()
        return f"logs={results['logs_deleted']};csvs={results['csvs_deleted']}"

    # ------------------------------------------------------------------
    def _base_site_url(self) -> str:
        site_url = self.project_data.schema.site_url.strip()
        if site_url:
            return site_url.rstrip("/")
        domain = self.project_data.basic_info.domain_name or self.project_data.basic_info.wp_admin_url
        domain = domain.replace("https://", "").replace("http://", "")
        return f"https://{domain}".rstrip("/")
