"""Data models for batch processing."""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    pass

from framekit.modules.batch.errors import BatchErrorType


class BatchStatus(StrEnum):
    """Status of a batch item."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BatchItem(BaseModel):
    """Represents a single release in the batch queue."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    display_name: str
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: BatchStatus = BatchStatus.PENDING
    enabled: bool = True
    selected: bool = False
    error_message: str | None = None
    error_type: BatchErrorType | None = None
    error_details: dict | None = None
    added_at: datetime = Field(default_factory=datetime.now)
    processing_time: float | None = None
    current_module: str | None = None
    current_step: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: object) -> BatchStatus:
        if isinstance(v, str):
            return BatchStatus(v)
        return v  # type: ignore[return-value]

    @field_validator("added_at", mode="before")
    @classmethod
    def _coerce_added_at(cls, v: object) -> datetime:
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v  # type: ignore[return-value]

    @field_validator("error_type", mode="before")
    @classmethod
    def _coerce_error_type(cls, v: object) -> BatchErrorType | None:
        if isinstance(v, str):
            with contextlib.suppress(ValueError, KeyError):
                return BatchErrorType(v)
            return None
        return v  # type: ignore[return-value]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "path": str(self.path),
            "display_name": self.display_name,
            "status": self.status.value,
            "enabled": self.enabled,
            "selected": self.selected,
            "error_message": self.error_message,
            "error_type": self.error_type.value if self.error_type else None,
            "error_details": self.error_details,
            "added_at": self.added_at.isoformat(),
            "processing_time": self.processing_time,
            "current_module": self.current_module,
            "current_step": self.current_step,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BatchItem:
        """Create from dictionary (JSON deserialization)."""
        return cls.model_validate(data)


@dataclass(slots=True)
class BatchResult:
    """Result of processing a batch item."""

    item: BatchItem
    exit_code: int
    duration_seconds: float | None = None

    @property
    def success(self) -> bool:
        """Check if the batch item was processed successfully."""
        return self.exit_code == 0 and self.item.status == BatchStatus.COMPLETED


@dataclass(slots=True)
class BatchQueueStats:
    """Statistics about the batch queue."""

    total: int = 0
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0

    @classmethod
    def from_items(cls, items: list[BatchItem]) -> BatchQueueStats:
        """Create statistics from a list of batch items."""
        stats = cls(total=len(items))
        for item in items:
            if item.status == BatchStatus.PENDING:
                stats.pending += 1
            elif item.status == BatchStatus.PROCESSING:
                stats.processing += 1
            elif item.status == BatchStatus.COMPLETED:
                stats.completed += 1
            elif item.status == BatchStatus.FAILED:
                stats.failed += 1
            elif item.status == BatchStatus.SKIPPED:
                stats.skipped += 1
        return stats


@dataclass(slots=True)
class BatchStatistics:
    """Statistics for batch processing results."""

    total: int
    completed: int
    failed: int
    skipped: int
    total_time: float
    average_time: float = 0.0
    estimated_remaining: float = 0.0
    success_rate: float = 0.0
    failed_items: list[BatchItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Calculate derived statistics."""
        if self.completed > 0:
            self.average_time = self.total_time / self.completed
            processed = self.completed + self.failed
            if processed > 0:
                self.success_rate = (self.completed / processed) * 100

        remaining_items = self.total - self.completed - self.failed - self.skipped
        if remaining_items > 0 and self.average_time > 0:
            self.estimated_remaining = self.average_time * remaining_items

    @classmethod
    def from_results(cls, results: list[BatchResult], total_time: float) -> BatchStatistics:
        """Create statistics from batch results."""
        completed = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success and r.item.status == BatchStatus.FAILED)
        skipped = sum(1 for r in results if r.item.status == BatchStatus.SKIPPED)
        failed_items = [r.item for r in results if not r.success]
        return cls(
            total=len(results),
            completed=completed,
            failed=failed,
            skipped=skipped,
            total_time=total_time,
            failed_items=failed_items,
        )


@dataclass(slots=True)
class BatchConfig:
    """Configuration for batch processing."""

    pipeline_preset: str | None = None
    nfo_locale: str | None = None
    announce: str | None = None

    preset: str | None = None
    with_metadata: bool | None = None
    remove_terms: tuple[str, ...] = field(default_factory=tuple)
    select_templates: bool = False
    nfo_mode: str | None = None
    enabled_modules: tuple[str, ...] | None = None
    auto_mode: bool = False

    def to_pipeline_kwargs(self) -> dict:
        """Convert batch config to pipeline command kwargs."""
        return {
            "nfo_locale": self.nfo_locale,
            "announce": self.announce,
            "preset": self.preset,
            "with_metadata": self.with_metadata,
            "remove_terms": self.remove_terms,
            "select_modules": False,
            "select_templates": self.select_templates if not self.auto_mode else False,
            "select_terms": False,
            "nfo_mode": self.nfo_mode,
            "enabled_modules": self.enabled_modules,
            "pipeline_preset": self.pipeline_preset,
            "auto_mode": self.auto_mode,
            "preview": False,
            "explain": False,
        }
