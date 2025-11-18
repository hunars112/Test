"""Site health and index monitoring for Authority Site Engine projects."""
from __future__ import annotations

import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence
from xml.etree import ElementTree

from ..core.cloudflare_client import CloudflareClient
from ..core.http_client import HttpResponse, RequestsHttpClient
from ..core.models import HealthMonitoringSettings, ProjectData


class SiteHealthMonitor:
    """Run lightweight, niche-agnostic health checks for a project."""

    def __init__(
        self,
        project_data: ProjectData,
        project_root: Path,
        *,
        http_client: RequestsHttpClient | None = None,
        cloudflare_client: CloudflareClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project_data = project_data
        self.project_root = project_root
        self.outputs_dir = project_root / "outputs"
        self.content_dir = self.outputs_dir / "content"
        self.logs_dir = self.outputs_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.post_map_path = self.content_dir / "post_map.json"
        self.link_map_path = self.content_dir / "link_map.json"
        self.deployment_status_path = self.content_dir / "deployment_status.json"
        self.status_path = self.content_dir / "health_status.json"
        self.log_file = self.logs_dir / "health_monitor.log"
        self.logger = logger or self._configure_logger()
        self.settings: HealthMonitoringSettings = project_data.health
        timeout = max(1, self.settings.http_timeout)
        self.http_client = http_client or RequestsHttpClient(timeout=timeout)
        self.cloudflare_client = cloudflare_client

    # ------------------------------------------------------------------
    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"health_monitor.{self.project_data.basic_info.project_name}")
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
    def run(self) -> Dict[str, object]:
        """Execute the configured health checks and persist a status file."""

        post_map = self._load_json(self.post_map_path, default=[])
        link_map = self._load_json(self.link_map_path, default=[])
        deployment_status = self._load_dict(self.deployment_status_path)
        status: Dict[str, object] = {
            "project": self.project_data.basic_info.project_name,
            "checked_at": datetime.utcnow().isoformat(),
            "notes": [],
        }
        if deployment_status:
            status["deployment_status"] = deployment_status
        http_results: List[Dict[str, object]] = []
        if self.settings.enable_http_checks:
            http_results = self._run_http_checks(post_map)
        status["http_checks"] = http_results
        self._evaluate_http_results(status, http_results)
        if self.settings.enable_sitemap_check:
            self._evaluate_sitemaps(status, post_map)
        else:
            status["sitemap_status"] = "not_configured"
        if self.settings.enable_linking_check:
            self._evaluate_linking(status, post_map, link_map)
        else:
            status["internal_linking_status"] = "not_configured"
        if self.settings.enable_content_stats:
            self._summarize_content(status, post_map)
        if self.settings.enable_cloudflare_stats:
            self._evaluate_cloudflare(status)
        else:
            status["cloudflare_status"] = "not_configured"
        self._derive_overall_status(status)
        self.status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
        self.logger.info("Health monitor completed with status %s", status.get("overall_status"))
        return status

    # ------------------------------------------------------------------
    def _load_json(self, path: Path, *, default: Sequence[object]) -> List[Dict[str, object]]:
        if not path.exists():
            return list(default)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse %s", path)
            return list(default)

    def _load_dict(self, path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse %s", path)
            return {}
        return payload if isinstance(payload, dict) else {}

    # ------------------------------------------------------------------
    def _base_site_url(self) -> str:
        site_url = self.project_data.schema.site_url.strip()
        if site_url:
            return site_url.rstrip("/")
        domain = self.project_data.basic_info.domain_name or self.project_data.basic_info.wp_admin_url
        domain = domain.replace("https://", "").replace("http://", "")
        return f"https://{domain}".rstrip("/")

    # ------------------------------------------------------------------
    def _run_http_checks(self, post_map: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
        base_url = self._base_site_url()
        urls = [f"{base_url}/"]
        samples = sorted((entry for entry in post_map if entry.get("post_url")), key=lambda item: item.get("post_id", 0))
        sample_size = max(0, self.settings.http_sample_size)
        for entry in samples[:sample_size]:
            url = str(entry.get("post_url"))
            if url:
                urls.append(url)
        results: List[Dict[str, object]] = []
        for url in urls:
            results.append(self._check_url(url))
        return results

    def _check_url(self, url: str) -> Dict[str, object]:
        try:
            response = self.http_client.get(url, timeout=self.settings.http_timeout)
            self.logger.info("HTTP %s -> %s", url, response.status_code)
            return {
                "url": url,
                "status_code": response.status_code,
                "response_ms": response.elapsed_ms,
                "final_url": response.url,
                "ok": 200 <= response.status_code < 400,
                "error": "",
                "body": response.text,
            }
        except requests.exceptions.SSLError as exc:
            self.logger.warning("SSL error fetching %s: %s", url, exc)
            return {
                "url": url,
                "status_code": 0,
                "response_ms": 0,
                "final_url": url,
                "ok": False,
                "error": "ssl_error",
                "body": "",
            }
        except requests.RequestException as exc:
            self.logger.warning("Request failure for %s: %s", url, exc)
            return {
                "url": url,
                "status_code": 0,
                "response_ms": 0,
                "final_url": url,
                "ok": False,
                "error": str(exc),
                "body": "",
            }

    # ------------------------------------------------------------------
    def _evaluate_http_results(self, status: Dict[str, object], results: List[Dict[str, object]]) -> None:
        if not results:
            status.setdefault("notes", []).append("HTTP checks disabled or unavailable")
            status["online_status"] = "not_checked"
            status["ssl_status"] = "not_configured" if not self.settings.enable_ssl_check else "not_checked"
            status["avg_response_time_ms"] = 0
            return
        status_codes = [entry.get("status_code", 0) for entry in results if entry.get("status_code")]
        avg = 0
        if status_codes:
            total_ms = sum(entry.get("response_ms", 0) for entry in results if entry.get("response_ms"))
            count = len([entry for entry in results if entry.get("response_ms")]) or 1
            avg = round(total_ms / count, 2)
        status["avg_response_time_ms"] = avg
        status["most_recent_http_status"] = results[0].get("status_code")
        if self.settings.enable_ssl_check:
            if any(entry.get("error") == "ssl_error" for entry in results):
                status["ssl_status"] = "error"
                status.setdefault("notes", []).append("SSL error detected on homepage")
            elif results and str(results[0].get("final_url", "")).startswith("https://"):
                status["ssl_status"] = "ok"
            else:
                status["ssl_status"] = "warning"
        else:
            status["ssl_status"] = "not_configured"
        if any(entry.get("status_code", 0) >= 500 or (entry.get("error") and entry.get("error") != "") for entry in results):
            status["online_status"] = "error"
        elif any(entry.get("status_code", 0) >= 400 for entry in results):
            status["online_status"] = "warning"
        else:
            status["online_status"] = "ok"

    # ------------------------------------------------------------------
    def _evaluate_sitemaps(self, status: Dict[str, object], post_map: Sequence[Dict[str, object]]) -> None:
        base_url = self._base_site_url()
        sitemap_paths = self.project_data.deployment.sitemap_paths or ["/wp-sitemap.xml", "/sitemap_index.xml"]
        total_urls = 0
        found = False
        for path in sitemap_paths:
            path = path.strip() or "/wp-sitemap.xml"
            url = f"{base_url}{path if path.startswith('/') else '/' + path}"
            result = self._check_url(url)
            if result.get("status_code") in {200, 201}:
                found = True
                count = self._count_sitemap_urls(result.get("body", ""))
                total_urls += count
            elif result.get("status_code") == 404:
                continue
            else:
                status.setdefault("notes", []).append(f"Sitemap {path} not reachable (status {result.get('status_code')})")
        status["sitemap_url_count"] = total_urls
        if found:
            status["sitemap_status"] = "present"
        else:
            status["sitemap_status"] = "missing"
            status.setdefault("notes", []).append("No sitemap discovered")
        known_posts = len(post_map)
        if known_posts:
            ratio = total_urls / known_posts if known_posts else 0
            status["sitemap_coverage_ratio"] = round(min(ratio, 1.0), 2)
            status["coverage_status"] = "ok" if ratio >= 0.6 else "warning"
            if ratio < 0.6:
                status.setdefault("notes", []).append("Sitemap coverage below 60% of known posts")
        else:
            status["coverage_status"] = "unknown"
            status["sitemap_coverage_ratio"] = 0.0

    def _count_sitemap_urls(self, xml_text: str) -> int:
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return 0
        urls = root.findall(".//{*}url")
        if urls:
            return len(urls)
        sitemap_locs = root.findall(".//{*}loc")
        return len(sitemap_locs)

    # ------------------------------------------------------------------
    def _evaluate_linking(
        self,
        status: Dict[str, object],
        post_map: Sequence[Dict[str, object]],
        link_map: Sequence[Dict[str, object]],
    ) -> None:
        if not post_map:
            status["internal_linking_status"] = "unknown"
            return
        if not link_map:
            status["internal_linking_status"] = "warning"
            status.setdefault("notes", []).append("Link map missing or empty")
            return
        outbound: Dict[int, int] = {}
        inbound: Dict[int, int] = {}
        for entry in link_map:
            source = entry.get("source_post_id")
            target = entry.get("target_post_id")
            if source:
                outbound[source] = outbound.get(source, 0) + 1
            if target:
                inbound[target] = inbound.get(target, 0) + 1
        post_ids = [entry.get("post_id") for entry in post_map if entry.get("post_id")]
        total_links = sum(outbound.values())
        avg_outbound = total_links / len(post_ids) if post_ids else 0
        orphan_count = len([pid for pid in post_ids if inbound.get(pid, 0) == 0])
        zero_outbound = len([pid for pid in post_ids if outbound.get(pid, 0) == 0])
        status["internal_link_avg_outbound"] = round(avg_outbound, 2)
        status["internal_link_orphan_count"] = orphan_count
        status["internal_link_zero_outbound"] = zero_outbound
        status["internal_link_total_links"] = total_links
        if orphan_count / max(1, len(post_ids)) > 0.25 or zero_outbound / max(1, len(post_ids)) > 0.25:
            status["internal_linking_status"] = "poor"
            status.setdefault("notes", []).append("Significant number of orphan or unlinked posts")
        elif orphan_count or zero_outbound:
            status["internal_linking_status"] = "warning"
            status.setdefault("notes", []).append("Some posts missing inbound or outbound links")
        else:
            status["internal_linking_status"] = "ok"

    # ------------------------------------------------------------------
    def _summarize_content(self, status: Dict[str, object], post_map: Sequence[Dict[str, object]]) -> None:
        breakdown: Dict[str, int] = {}
        for entry in post_map:
            post_type = entry.get("post_type", "unknown")
            breakdown[post_type] = breakdown.get(post_type, 0) + 1
        status["known_post_count"] = len(post_map)
        status["post_type_breakdown"] = breakdown

    # ------------------------------------------------------------------
    def _evaluate_cloudflare(self, status: Dict[str, object]) -> None:
        credentials = self.project_data.cloudflare
        if not credentials.cloudflare_email or not credentials.cloudflare_api_key or not self.cloudflare_client:
            status["cloudflare_status"] = "not_configured"
            return
        domain = self.project_data.basic_info.domain_name
        try:
            result = self.cloudflare_client.fetch_analytics(domain, since_hours=self.settings.cloudflare_hours)
        except Exception as exc:  # pragma: no cover - network failure path
            self.logger.error("Cloudflare analytics failed: %s", exc)
            status["cloudflare_status"] = "error"
            status.setdefault("notes", []).append("Cloudflare analytics unavailable")
            return
        totals = result.get("totals", {}) if isinstance(result, dict) else {}
        requests_block = totals.get("requests", {}) if isinstance(totals, dict) else {}
        threats_block = totals.get("threats", {}) if isinstance(totals, dict) else {}
        total_requests = float(requests_block.get("all", 0) or 0)
        cached = float(requests_block.get("cached", 0) or 0)
        threats = float(threats_block.get("all", 0) or 0)
        status["cloudflare_metrics"] = {
            "requests": total_requests,
            "cached": cached,
            "threats": threats,
        }
        if total_requests and threats / total_requests > 0.1:
            status["cloudflare_status"] = "warning"
            status.setdefault("notes", []).append("Cloudflare reports elevated threat traffic")
        else:
            status["cloudflare_status"] = "ok"

    # ------------------------------------------------------------------
    def _derive_overall_status(self, status: Dict[str, object]) -> None:
        priorities = {"error": 3, "poor": 3, "warning": 2, "missing": 2, "ok": 1}
        signals = [
            status.get("online_status"),
            status.get("ssl_status"),
            status.get("sitemap_status"),
            status.get("coverage_status"),
            status.get("internal_linking_status"),
            status.get("cloudflare_status"),
        ]
        highest = 0
        for value in signals:
            highest = max(highest, priorities.get(str(value), 0))
        overall = "ok"
        if highest >= 3:
            overall = "error"
        elif highest == 2:
            overall = "warning"
        status["overall_status"] = overall


__all__ = ["SiteHealthMonitor", "RequestsHttpClient", "HttpResponse"]
