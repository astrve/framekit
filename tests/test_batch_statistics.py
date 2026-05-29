from __future__ import annotations

from pathlib import Path

from ouro.modules.batch.models import BatchItem, BatchResult, BatchStatistics, BatchStatus


def _item(name: str, status: BatchStatus) -> BatchItem:
    return BatchItem(
        path=Path(f"/tmp/{name}"),
        display_name=name,
        status=status,
    )


def test_batch_statistics_failed_items_excludes_skipped() -> None:
    completed = BatchResult(item=_item("ok", BatchStatus.COMPLETED), exit_code=0, duration_seconds=1.0)
    failed = BatchResult(item=_item("ko", BatchStatus.FAILED), exit_code=1, duration_seconds=1.0)
    skipped = BatchResult(item=_item("skip", BatchStatus.SKIPPED), exit_code=0, duration_seconds=0.1)

    stats = BatchStatistics.from_results([completed, failed, skipped], total_time=2.1)

    assert stats.completed == 1
    assert stats.failed == 1
    assert stats.skipped == 1
    assert [item.display_name for item in stats.failed_items] == ["ko"]
