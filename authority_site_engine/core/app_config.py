"""Global application configuration helpers for Authority Site Engine."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG_FILENAME = "app_config.json"


@dataclass
class AppConfig:
    """Simple representation of global settings for the desktop app."""

    projects_root: Path
    logs_root: Path
    http_timeout: int = 30
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["projects_root"] = str(self.projects_root)
        payload["logs_root"] = str(self.logs_root)
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        return cls(
            projects_root=Path(data.get("projects_root", "projects")),
            logs_root=Path(data.get("logs_root", "logs")),
            http_timeout=int(data.get("http_timeout", 30)),
            extra=data.get("extra", {}),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def get_default_data_root() -> Path:
    """Return the OS-specific data root for Authority Site Engine."""

    if os.name == "nt":  # pragma: no cover - Windows only branch
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "AuthoritySiteEngine"
        return Path.home() / "AppData" / "Roaming" / "AuthoritySiteEngine"
    return Path.home() / ".authority_site_engine"


def get_default_config_path() -> Path:
    """Return the default location for the app config file."""

    config_dir = get_default_data_root() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / DEFAULT_CONFIG_FILENAME


def ensure_data_roots(config: AppConfig) -> None:
    """Guarantee that project and log directories exist."""

    for path in {config.projects_root.parent, config.projects_root, config.logs_root}:
        path.mkdir(parents=True, exist_ok=True)


def load_app_config(path: Path | None = None) -> AppConfig:
    """Load the application config file or create a sensible default."""

    config_path = path or get_default_config_path()
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        config = AppConfig.from_dict(data)
        ensure_data_roots(config)
        return config
    data_root = get_default_data_root()
    config = AppConfig(
        projects_root=data_root / "projects",
        logs_root=data_root / "logs",
    )
    ensure_data_roots(config)
    config.save(config_path)
    return config


__all__ = [
    "AppConfig",
    "ensure_data_roots",
    "get_default_config_path",
    "get_default_data_root",
    "load_app_config",
]
