"""Upload statistics and analytics.

Analyzes upload history to provide insights and trends.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from framekit.core.paths import get_config_dir


class UploadStats:
    """Analyze upload history and generate statistics."""

    def __init__(self):
        self.history_file = get_config_dir() / "upload_history.jsonl"

    def _load_history(self) -> list[dict[str, Any]]:
        """Load upload history from JSONL file."""
        if not self.history_file.exists():
            return []

        history = []
        with open(self.history_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        history.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return history

    @staticmethod
    def _default_stats() -> dict[str, Any]:
        return {
            "total_uploads": 0,
            "successful_uploads": 0,
            "failed_uploads": 0,
            "success_rate": 0.0,
            "by_tracker": {},
            "by_day": {},
            "average_time": 0.0,
            "last_upload": None,
        }

    @staticmethod
    def _recent_entries(history: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
        cutoff_date = datetime.now() - timedelta(days=days)
        return [
            entry
            for entry in history
            if datetime.fromisoformat(entry.get("timestamp", "1970-01-01")) >= cutoff_date
        ]

    @staticmethod
    def _group_by_tracker(entries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        by_tracker: defaultdict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "success": 0, "failed": 0}
        )
        for entry in entries:
            tracker = entry.get("tracker", "Unknown")
            by_tracker[tracker]["total"] += 1
            if entry.get("success", False):
                by_tracker[tracker]["success"] += 1
            else:
                by_tracker[tracker]["failed"] += 1
        return dict(by_tracker)

    @staticmethod
    def _group_by_day(entries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        by_day: defaultdict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "success": 0, "failed": 0}
        )
        for entry in entries:
            date = datetime.fromisoformat(entry.get("timestamp", "1970-01-01")).date()
            day_str = date.isoformat()
            by_day[day_str]["total"] += 1
            if entry.get("success", False):
                by_day[day_str]["success"] += 1
            else:
                by_day[day_str]["failed"] += 1
        return dict(sorted(by_day.items()))

    @staticmethod
    def _average_duration(entries: list[dict[str, Any]]) -> float:
        durations = [entry.get("duration", 0) for entry in entries if entry.get("duration")]
        return (sum(durations) / len(durations)) if durations else 0.0

    @staticmethod
    def _last_upload_timestamp(entries: list[dict[str, Any]]) -> str | None:
        timestamps = [ts for entry in entries if (ts := entry.get("timestamp")) is not None]
        return max(timestamps, default=None)

    def get_stats(self, days: int = 30) -> dict[str, Any]:
        """Calculate upload statistics for the last N days.

        Args:
            days: Number of days to analyze (default: 30)

        Returns:
            Dict with statistics
        """
        history = self._load_history()
        recent = self._recent_entries(history, days)
        if not recent:
            return self._default_stats()

        total = len(recent)
        successful = sum(1 for entry in recent if entry.get("success", False))
        failed = total - successful
        by_tracker = self._group_by_tracker(recent)
        by_day = self._group_by_day(recent)
        avg_time = self._average_duration(recent)
        last_upload = self._last_upload_timestamp(recent)

        return {
            "total_uploads": total,
            "successful_uploads": successful,
            "failed_uploads": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "by_tracker": by_tracker,
            "by_day": by_day,
            "average_time": avg_time,
            "last_upload": last_upload,
        }

    def get_ascii_chart(self, days: int = 30) -> str:
        """Generate ASCII bar chart of uploads over time.

        Args:
            days: Number of days to show

        Returns:
            ASCII chart string
        """
        stats = self.get_stats(days)
        by_day = stats["by_day"]

        if not by_day:
            return "No data available"

        # Build chart
        max_count = max(d["total"] for d in by_day.values())
        if max_count == 0:
            return "No uploads in this period"

        chart_lines = []
        chart_lines.append(f"Upload Activity (Last {days} Days)")
        chart_lines.append("=" * 50)

        for date_str, counts in list(by_day.items())[-14:]:  # Last 14 days
            date = datetime.fromisoformat(date_str).strftime("%m/%d")
            bar_length = int((counts["total"] / max_count) * 30)
            bar = "█" * bar_length
            chart_lines.append(f"{date} │{bar} {counts['total']}")

        chart_lines.append("=" * 50)
        return "\n".join(chart_lines)
