"""Summaries for module log files."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable


class LogSummaryModule:
    """Aggregate stats from the various log files."""

    ERROR_PATTERNS = re.compile(r"ERROR|Error|Failed")
    WARNING_PATTERNS = re.compile(r"WARNING|Warning")

    def summarize(self, log_paths: Iterable[Path]) -> Dict[str, object]:
        total_lines = 0
        errors = 0
        warnings = 0
        messages: Counter[str] = Counter()
        for path in log_paths:
            if not path or not path.exists():
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                total_lines += 1
                if self.ERROR_PATTERNS.search(line):
                    errors += 1
                if self.WARNING_PATTERNS.search(line):
                    warnings += 1
                messages[line.strip()] += 1
        top_messages = [
            {"message": msg, "count": count}
            for msg, count in messages.most_common(5)
        ]
        return {
            "total_lines": total_lines,
            "total_errors": errors,
            "total_warnings": warnings,
            "top_messages": top_messages,
        }

    def to_json(self, summary: Dict[str, object], output_path: Path) -> None:
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


__all__ = ["LogSummaryModule"]
