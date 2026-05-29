from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class WarningItem:
    """Warning item."""

    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ErrorItem:
    """Error item."""

    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OperationDetail:
    """Operation detail."""

    file: str | None
    action: str
    status: str
    message: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProgressMetrics:
    """Enhanced progress metrics for tracking operation progress."""

    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    total_bytes: int = 0
    processed_bytes: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100.0

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio as percentage."""
        if self.total_bytes == 0:
            return 0.0
        return (self.processed_bytes / self.total_bytes) * 100.0

    @property
    def processing_rate(self) -> float:
        """Calculate processing rate in items per second."""
        elapsed = time.time() - self.start_time
        if elapsed < 0.001:  # Less than 1ms
            return 0.0
        return self.completed_items / elapsed

    @property
    def bytes_per_second(self) -> float:
        """Calculate bytes per second."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        return self.processed_bytes / elapsed

    @property
    def estimated_time_remaining(self) -> float | None:
        """Calculate estimated time remaining in seconds."""
        if self.completed_items == 0:
            return None
        if self.completed_items >= self.total_items:
            return 0.0
        elapsed = time.time() - self.start_time
        rate = self.completed_items / elapsed
        remaining_items = self.total_items - self.completed_items
        return remaining_items / rate

    def increment_completed(self) -> None:
        """Increment completed items counter."""
        self.completed_items += 1

    def increment_failed(self) -> None:
        """Increment failed items counter."""
        self.failed_items += 1

    def increment_skipped(self) -> None:
        """Increment skipped items counter."""
        self.skipped_items += 1

    def add_bytes(self, bytes_count: int) -> None:
        """Add to processed bytes counter."""
        self.processed_bytes += bytes_count


@dataclass(slots=True)
class OperationReport:
    """Report for operation."""

    tool: str
    scanned: int = 0
    processed: int = 0
    modified: int = 0
    skipped: int = 0
    warnings: list[WarningItem] = field(default_factory=list)
    errors: list[ErrorItem] = field(default_factory=list)
    details: list[OperationDetail] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    metrics: ProgressMetrics = field(default_factory=ProgressMetrics)

    @property
    def ok(self) -> bool:
        """Handle ok."""
        return not self.errors

    def add_warning(self, code: str, message: str, **context: Any) -> None:
        """Handle add warning."""
        self.warnings.append(WarningItem(code=code, message=message, context=context))

    def add_error(self, code: str, message: str, **context: Any) -> None:
        """Handle add error."""
        self.errors.append(ErrorItem(code=code, message=message, context=context))

    def add_detail(
        self,
        *,
        file: str | None,
        action: str,
        status: str,
        message: str = "",
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        """Handle add detail."""
        self.details.append(
            OperationDetail(
                file=file,
                action=action,
                status=status,
                message=message,
                before=before or {},
                after=after or {},
            )
        )

    def get_summary(self) -> dict[str, Any]:
        """Get summary including metrics."""
        return {
            "tool": self.tool,
            "scanned": self.scanned,
            "processed": self.processed,
            "modified": self.modified,
            "skipped": self.skipped,
            "warnings": len(self.warnings),
            "errors": len(self.errors),
            "success_rate": self.metrics.success_rate,
            "compression_ratio": self.metrics.compression_ratio,
            "processing_rate": self.metrics.processing_rate,
            "bytes_per_second": self.metrics.bytes_per_second,
        }

    def to_dict(self) -> dict[str, Any]:
        """Handle to dict."""
        return asdict(self)
