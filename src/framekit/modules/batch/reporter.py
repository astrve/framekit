"""Batch processing reporting and statistics."""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from framekit.core.i18n import tr
from framekit.modules.batch.errors import BatchErrorType, get_error_hint
from framekit.modules.batch.models import BatchItem, BatchResult, BatchStatistics, BatchStatus
from framekit.ui.console import console


class BatchReporter:
    """Generate reports and statistics for batch processing."""

    def __init__(self, results: list[BatchResult], start_time: float) -> None:
        """Initialize the reporter.

        Args:
            results: List of batch results
            start_time: Start time of batch processing
        """
        self.results = results
        self.start_time = start_time
        self.total_time = time.time() - start_time
        self.statistics = BatchStatistics.from_results(results, self.total_time)

    def print_summary(self) -> None:
        """Print a comprehensive summary to console."""
        console.print()

        # Create summary table
        table = Table(
            title=tr("batch.report.title", default="Batch Processing Summary"),
            show_header=True,
            header_style="bold cyan",
        )

        table.add_column(tr("batch.report.metric", default="Metric"), style="white")
        table.add_column(tr("batch.report.value", default="Value"), justify="right", style="cyan")

        # Add rows
        table.add_row(
            tr("batch.report.total", default="Total Releases"),
            str(self.statistics.total),
        )
        table.add_row(
            tr("batch.report.completed", default="Completed"),
            f"[green]{self.statistics.completed}[/green]",
        )
        table.add_row(
            tr("batch.report.failed", default="Failed"),
            f"[red]{self.statistics.failed}[/red]",
        )

        if self.statistics.skipped > 0:
            table.add_row(
                tr("batch.report.skipped", default="Skipped"),
                f"[yellow]{self.statistics.skipped}[/yellow]",
            )

        if self.statistics.completed + self.statistics.failed > 0:
            table.add_row(
                tr("batch.report.success_rate", default="Success Rate"),
                f"{self.statistics.success_rate:.1f}%",
            )

        # Format total time
        hours = int(self.total_time // 3600)
        minutes = int((self.total_time % 3600) // 60)
        seconds = int(self.total_time % 60)

        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"

        table.add_row(
            tr("batch.report.total_time", default="Total Time"),
            time_str,
        )

        if self.statistics.completed > 0:
            avg = self.statistics.average_time
            avg_minutes = int(avg // 60)
            avg_seconds = int(avg % 60)
            avg_str = f"{avg_minutes}m {avg_seconds}s" if avg_minutes > 0 else f"{avg_seconds}s"

            table.add_row(
                tr("batch.report.avg_time", default="Avg Time/Release"),
                avg_str,
            )

        console.print(table)

        # Print failed releases if any
        if self.statistics.failed_items:
            console.print()
            self._print_failed_releases()

        console.print()

    def _print_failed_releases(self) -> None:
        """Print details of failed releases, grouped by error type."""
        errors_by_type = self._group_errors_by_type()
        self._print_error_summary(errors_by_type)
        self._print_failure_details(errors_by_type)
        console.print()
        console.print(
            f"[yellow]{tr('batch.report.retry_hint', default='Use --retry-failed to retry these releases')}[/yellow]"
        )

    def _group_errors_by_type(self) -> dict[BatchErrorType | None, list[BatchItem]]:
        errors_by_type: dict[BatchErrorType | None, list[BatchItem]] = defaultdict(list)
        for item in self.statistics.failed_items:
            errors_by_type[item.error_type].append(item)
        return errors_by_type

    def _ordered_error_groups(
        self, errors_by_type: dict[BatchErrorType | None, list[BatchItem]]
    ) -> list[tuple[BatchErrorType | None, list[BatchItem]]]:
        return sorted(errors_by_type.items(), key=lambda group: len(group[1]), reverse=True)

    def _print_error_summary(
        self, errors_by_type: dict[BatchErrorType | None, list[BatchItem]]
    ) -> None:
        show_summary = len(errors_by_type) > 1 or (
            len(errors_by_type) == 1 and None not in errors_by_type
        )
        if not show_summary:
            return
        console.print()
        summary_table = Table(
            title=tr("batch.report.error_summary", default="Error Summary"),
            show_header=True,
            header_style="bold red",
        )
        summary_table.add_column(
            tr("batch.report.error_type", default="Error Type"), style="yellow"
        )
        summary_table.add_column(
            tr("batch.report.count", default="Count"), justify="right", style="red"
        )
        for error_type, items in self._ordered_error_groups(errors_by_type):
            type_name = error_type.value if error_type else "unknown"
            summary_table.add_row(type_name.replace("_", " ").title(), str(len(items)))
        console.print(summary_table)

    def _build_failure_panel_content(
        self, error_type: BatchErrorType | None, items: list[BatchItem]
    ) -> Text:
        content = Text()
        type_name = error_type.value if error_type else "unknown"
        suffix = "s" if len(items) != 1 else ""
        content.append(
            f"{type_name.replace('_', ' ').title()} ({len(items)} item{suffix})\n\n",
            style="bold red",
        )
        for item in items:
            content.append(f"✗ {item.display_name}\n", style="red")
            if item.error_message:
                content.append(f"  {item.error_message}\n", style="bright_black")
        if error_type:
            content.append(f"\n💡 {get_error_hint(error_type)}\n", style="yellow")
        return content

    def _print_failure_details(
        self, errors_by_type: dict[BatchErrorType | None, list[BatchItem]]
    ) -> None:
        console.print()
        for error_type, items in self._ordered_error_groups(errors_by_type):
            console.print(
                Panel(
                    self._build_failure_panel_content(error_type, items),
                    title=tr("batch.report.failures_title", default="Failures"),
                    border_style="red",
                )
            )

    def export_json(self, path: Path) -> bool:
        """Export report to JSON file.

        Args:
            path: Path to output file

        Returns:
            True if exported successfully
        """
        import json
        from datetime import datetime

        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": self.statistics.total,
                    "completed": self.statistics.completed,
                    "failed": self.statistics.failed,
                    "skipped": self.statistics.skipped,
                    "success_rate": self.statistics.success_rate,
                    "total_time_seconds": self.total_time,
                    "average_time_seconds": self.statistics.average_time,
                },
                "results": [
                    {
                        "name": r.item.display_name,
                        "path": str(r.item.path),
                        "status": r.item.status.value,
                        "success": r.success,
                        "exit_code": r.exit_code,
                        "duration_seconds": r.duration_seconds,
                        "error": r.item.error_message,
                        "error_type": r.item.error_type.value if r.item.error_type else None,
                        "error_details": r.item.error_details,
                    }
                    for r in self.results
                ],
            }

            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True

        except Exception:
            return False

    def export_csv(self, path: Path) -> bool:
        """Export report to CSV file.

        Args:
            path: Path to output file

        Returns:
            True if exported successfully
        """
        import csv

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(
                    [
                        "Name",
                        "Path",
                        "Status",
                        "Success",
                        "Exit Code",
                        "Duration (seconds)",
                        "Error",
                        "Error Type",
                    ]
                )

                # Write data
                for r in self.results:
                    writer.writerow(
                        [
                            r.item.display_name,
                            str(r.item.path),
                            r.item.status.value,
                            "Yes" if r.success else "No",
                            r.exit_code,
                            f"{r.duration_seconds:.2f}" if r.duration_seconds else "",
                            r.item.error_message or "",
                            r.item.error_type.value if r.item.error_type else "",
                        ]
                    )

            return True

        except Exception:
            return False

    def export_html(self, path: Path) -> bool:
        """Export report to HTML file.

        Args:
            path: Path to output file

        Returns:
            True if exported successfully
        """
        try:
            time_str = self._format_total_time_for_html()
            html = self._html_header(time_str)
            html += "".join(self._html_result_rows())
            html += self._html_footer()

            with open(path, "w", encoding="utf-8") as f:
                f.write(html)

            return True

        except Exception:
            return False

    def _format_total_time_for_html(self) -> str:
        hours = int(self.total_time // 3600)
        minutes = int((self.total_time % 3600) // 60)
        seconds = int(self.total_time % 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"

    def _html_header(self, time_str: str) -> str:
        from datetime import datetime

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Batch Processing Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #00bcd4; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat {{ background: #f9f9f9; padding: 15px; border-radius: 4px; border-left: 4px solid #00bcd4; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #333; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #00bcd4; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
        .success {{ color: #4caf50; font-weight: bold; }}
        .failed {{ color: #f44336; font-weight: bold; }}
        .skipped {{ color: #ff9800; font-weight: bold; }}
        .error {{ color: #999; font-size: 12px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Batch Processing Report</h1>
        <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <h2>Summary</h2>
        <div class="summary">
            <div class="stat">
                <div class="stat-label">Total Releases</div>
                <div class="stat-value">{self.statistics.total}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Completed</div>
                <div class="stat-value" style="color: #4caf50;">{self.statistics.completed}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Failed</div>
                <div class="stat-value" style="color: #f44336;">{self.statistics.failed}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Success Rate</div>
                <div class="stat-value">{self.statistics.success_rate:.1f}%</div>
            </div>
            <div class="stat">
                <div class="stat-label">Total Time</div>
                <div class="stat-value">{time_str}</div>
            </div>
        </div>
        
        <h2>Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Release</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
"""

    def _html_status(self, result: BatchResult) -> tuple[str, str]:
        if result.success:
            return "success", "✓ Success"
        if result.item.status == BatchStatus.FAILED:
            return "failed", "✗ Failed"
        return "skipped", "○ Skipped"

    def _html_result_rows(self) -> list[str]:
        rows: list[str] = []
        for result in self.results:
            status_class, status_text = self._html_status(result)
            duration = f"{result.duration_seconds:.1f}s" if result.duration_seconds else "-"
            error = (
                f'<div class="error">{result.item.error_message}</div>'
                if result.item.error_message
                else ""
            )
            rows.append(
                f"""
                <tr>
                    <td>{result.item.display_name}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{duration}</td>
                    <td>{error if error else "-"}</td>
                </tr>
"""
            )
        return rows

    def _html_footer(self) -> str:
        return """
            </tbody>
        </table>
        
        <div class="footer">
            <p>Generated by Framekit Batch Processing</p>
        </div>
    </div>
</body>
</html>
"""
