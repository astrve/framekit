"""Dry-run mode for previewing operations without execution."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class DryRunOperation:
    """Represents a single operation in dry-run mode."""

    operation_type: str
    target: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert operation to dictionary."""
        return asdict(self)


class DryRunRecorder:
    """Records operations during dry-run mode."""

    def __init__(self) -> None:
        """Initialize dry-run recorder."""
        self.operations: list[DryRunOperation] = []
        self.is_active: bool = False

    def activate(self) -> None:
        """Activate dry-run recording."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate dry-run recording."""
        self.is_active = False

    def record(
        self,
        operation_type: str,
        target: str,
        description: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an operation."""
        if not self.is_active:
            return

        self.operations.append(
            DryRunOperation(
                operation_type=operation_type,
                target=target,
                description=description,
                metadata=metadata or {},
            )
        )

    def clear(self) -> None:
        """Clear all recorded operations."""
        self.operations.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get summary of recorded operations."""
        by_type: dict[str, int] = defaultdict(int)
        for op in self.operations:
            by_type[op.operation_type] += 1

        return {
            "total": len(self.operations),
            "by_type": dict(by_type),
        }

    def format_summary(self) -> str:
        """Format summary for display."""
        if not self.operations:
            return "No operations recorded."

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("Dry-Run Summary")
        lines.append("=" * 60)
        lines.append("")

        summary = self.get_summary()
        lines.append(f"Total Operations: {summary['total']}")
        lines.append("")
        lines.append("Operations by Type:")
        for op_type, count in summary["by_type"].items():
            lines.append(f"  {op_type}: {count}")
        lines.append("")

        lines.append("Detailed Operations:")
        lines.append("-" * 60)
        for i, op in enumerate(self.operations, 1):
            lines.append(f"{i}. [{op.operation_type.upper()}] {op.target}")
            lines.append(f"   {op.description}")
            if op.metadata:
                lines.append("   Metadata:")
                for key, value in op.metadata.items():
                    lines.append(f"     {key}: {value}")
            lines.append("")

        lines.append("=" * 60)
        lines.append("NOTE: No actual changes were made (dry-run mode)")
        lines.append("=" * 60)

        return "\n".join(lines)

    def format_operations(self) -> str:
        """Format operations list for display."""
        if not self.operations:
            return "No operations recorded."

        lines: list[str] = []
        for op in self.operations:
            lines.append(f"[{op.operation_type.upper()}] {op.target}")
            lines.append(f"  {op.description}")
            if op.metadata:
                for key, value in op.metadata.items():
                    lines.append(f"  {key}: {value}")
            lines.append("")

        return "\n".join(lines)


# Global dry-run recorder instance
_global_recorder: DryRunRecorder | None = None


def _get_recorder() -> DryRunRecorder | None:
    """Get the global dry-run recorder."""
    return _global_recorder


def _set_recorder(recorder: DryRunRecorder | None) -> None:
    """Set the global dry-run recorder."""
    global _global_recorder
    _global_recorder = recorder


def is_dry_run() -> bool:
    """Check if dry-run mode is active."""
    recorder = _get_recorder()
    return recorder is not None and recorder.is_active


def record_operation(
    operation_type: str,
    target: str,
    description: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an operation in dry-run mode."""
    recorder = _get_recorder()
    if recorder:
        recorder.record(operation_type, target, description, metadata=metadata)


@contextmanager
def dry_run_mode() -> Generator[DryRunRecorder, None, None]:
    """Context manager for dry-run mode.

    Usage:
        with dry_run_mode() as recorder:
            record_operation("delete", "/tmp/file.mkv", "Delete file")
            # ... more operations ...

        print(recorder.format_summary())
    """
    recorder = DryRunRecorder()
    recorder.activate()
    _set_recorder(recorder)

    try:
        yield recorder
    finally:
        recorder.deactivate()
        _set_recorder(None)
