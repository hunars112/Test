from __future__ import annotations

import json
import os
import random
import string
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import paramiko
import requests


class PluginDeploymentError(Exception):
    """Raised when deploying the ASE Connector plugin fails."""


class JobUploadError(Exception):
    """Raised when an ASE job file cannot be uploaded."""


@dataclass
class SiteConfig:
    host: str
    port: int
    username: str
    password: str
    web_root: str
    wp_content: str

    @property
    def https_base_url(self) -> str:
        return f"https://{self.host}".rstrip("/")


class SFTPClient(AbstractContextManager):
    """Thin wrapper around paramiko for easier uploads."""

    def __init__(self, site: SiteConfig):
        self._site = site
        self._transport: Optional[paramiko.Transport] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    def __enter__(self) -> "SFTPClient":
        transport = paramiko.Transport((self._site.host, self._site.port))
        transport.connect(username=self._site.username, password=self._site.password)
        self._transport = transport
        self._sftp = paramiko.SFTPClient.from_transport(transport)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._sftp:
            self._sftp.close()
        if self._transport:
            self._transport.close()

    def mkdir_p(self, path: str) -> None:
        parts = path.split("/")
        current = ""
        for part in parts:
            if not part:
                continue
            current = f"{current}/{part}" if current else part
            try:
                self._sftp.stat(current)
            except IOError:
                self._sftp.mkdir(current)

    def upload_bytes(self, remote_path: str, data: bytes) -> None:
        assert self._sftp
        directory = os.path.dirname(remote_path)
        if directory:
            self.mkdir_p(directory)
        with self._sftp.open(remote_path, "wb") as remote_file:
            remote_file.write(data)

    def upload_file(self, local_path: str, remote_path: str) -> None:
        assert self._sftp
        directory = os.path.dirname(remote_path)
        if directory:
            self.mkdir_p(directory)
        self._sftp.put(local_path, remote_path)

    def file_exists(self, remote_path: str) -> bool:
        try:
            assert self._sftp
            self._sftp.stat(remote_path)
            return True
        except IOError:
            return False


def _random_suffix(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def deploy_ase_connector_plugin(site: SiteConfig, local_plugin_zip: str) -> None:
    """Upload and install the ASE Connector plugin on the remote site."""

    remote_zip = os.path.join(site.web_root or "", "ase-connector-install.zip")
    remote_installer = os.path.join(site.web_root or "", "ase-connector-install.php")

    installer_script = """<?php
error_reporting(E_ALL);
ini_set('display_errors', 0);

$zipPath = __DIR__ . '/ase-connector-install.zip';
if (!file_exists($zipPath)) {
    die('Missing ASE connector zip.');
}

require_once __DIR__ . '/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
require_once ABSPATH . 'wp-admin/includes/file.php';

$zip = new ZipArchive();
if ($zip->open($zipPath) !== TRUE) {
    die('Failed to open ASE connector zip.');
}

$dest = WP_CONTENT_DIR . '/plugins/';
if (!is_dir($dest)) {
    wp_mkdir_p($dest);
}

if (!$zip->extractTo($dest)) {
    $zip->close();
    die('Failed to extract ASE connector zip.');
}
$zip->close();

$plugin_file = $dest . 'ase-connector/ase-connector.php';
if (!file_exists($plugin_file)) {
    die('ASE connector plugin file missing after extraction.');
}

$active = get_option('active_plugins', array());
if (!in_array('ase-connector/ase-connector.php', $active)) {
    $active[] = 'ase-connector/ase-connector.php';
    update_option('active_plugins', $active);
}

if (function_exists('activate_plugin')) {
    activate_plugin('ase-connector/ase-connector.php', '', false, false);
}

echo 'ASE connector installed.';

@unlink($zipPath);
@unlink(__FILE__);
"""

    try:
        with SFTPClient(site) as sftp:
            sftp.upload_file(local_plugin_zip, remote_zip)
            sftp.upload_bytes(remote_installer, installer_script.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise PluginDeploymentError(f"SFTP upload failed for {site.host}: {exc}") from exc

    installer_url = f"{site.https_base_url}/ase-connector-install.php"
    try:
        response = requests.get(installer_url, timeout=30)
        response.raise_for_status()
        if "installed" not in response.text.lower():
            raise PluginDeploymentError(
                f"Installer did not report success for {site.host}: {response.text}"
            )
    except requests.RequestException as exc:  # pragma: no cover - network
        raise PluginDeploymentError(f"Installer request failed for {site.host}: {exc}") from exc


class ASEJobClient:
    """Upload job files that the ASE Connector plugin will process."""

    def __init__(self, site: SiteConfig):
        self.site = site

    def _job_path(self, job_type: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        suffix = _random_suffix()
        filename = f"job-{job_type}-{timestamp}-{suffix}.json"
        base = self.site.wp_content or "wp-content"
        return os.path.join(base, "ase-jobs", filename)

    def _queue_job(self, job_type: str, payload: dict[str, Any]) -> str:
        job = {
            "job_type": job_type,
            "created_at": _utc_now(),
            "site_id": self.site.host,
            "payload": payload,
        }
        data = json.dumps(job, ensure_ascii=False, indent=2).encode("utf-8")
        remote_path = self._job_path(job_type)
        try:
            with SFTPClient(self.site) as sftp:
                sftp.upload_bytes(remote_path, data)
        except Exception as exc:  # noqa: BLE001
            raise JobUploadError(f"Failed to upload job to {self.site.host}: {exc}") from exc
        return remote_path

    def queue_category_job(self, categories: list[dict[str, Any]]) -> str:
        if not categories:
            raise ValueError("categories list cannot be empty")
        payload = {"categories": categories}
        return self._queue_job("create_categories", payload)

    def queue_post_job(self, posts: list[dict[str, Any]]) -> str:
        if not posts:
            raise ValueError("posts list cannot be empty")
        payload = {"posts": posts}
        return self._queue_job("create_posts", payload)

    def queue_menu_rebuild_job(self, menu_location: str, items: list[dict[str, Any]]) -> str:
        if not menu_location:
            raise ValueError("menu_location is required")
        payload = {"menu_location": menu_location, "items": items}
        return self._queue_job("rebuild_main_menu", payload)
