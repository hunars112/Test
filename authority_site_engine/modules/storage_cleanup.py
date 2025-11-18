"""Housekeeping utilities for Authority Site Engine projects."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


class StorageCleanup:
    """Delete or archive logs and CSVs based on retention policies."""

    def __init__(
        self,
        project_root: Path,
        *,
        max_log_age_days: int = 30,
        delete_old_csv_after_posting: bool = False,
    ) -> None:
        self.project_root = project_root
        self.max_log_age_days = max_log_age_days
        self.delete_old_csv_after_posting = delete_old_csv_after_posting
        self.outputs_dir = project_root / "outputs"
        self.logs_dir = self.outputs_dir / "logs"
        self.csv_dir = self.outputs_dir / "csv"

    def cleanup_logs(self) -> int:
        threshold = datetime.utcnow() - timedelta(days=self.max_log_age_days)
        deleted = 0
        for path in self.logs_dir.glob("*.log"):
            if not path.exists():
                continue
            mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
            if mtime < threshold:
                path.unlink()
                deleted += 1
        return deleted

    def cleanup_csv(self, posted_files: Iterable[str] | None = None) -> int:
        if not self.delete_old_csv_after_posting:
            return 0
        deleted = 0
        for path in self.csv_dir.glob("*.csv"):
            if posted_files and path.name not in posted_files:
                continue
            path.unlink(missing_ok=True)
            deleted += 1
        return deleted

    def run(self) -> dict:
        logs = self.cleanup_logs()
        csvs = self.cleanup_csv()
        return {"logs_deleted": logs, "csvs_deleted": csvs}


__all__ = ["StorageCleanup"]
