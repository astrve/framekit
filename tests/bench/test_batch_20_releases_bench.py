from __future__ import annotations

import pytest

pytestmark = pytest.mark.benchmark


def test_bench_batch_queue_construction(benchmark, tmp_path) -> None:
    from ouro.modules.batch.queue import BatchQueue

    releases: list = []
    for i in range(20):
        folder = tmp_path / f"release-{i:02d}"
        folder.mkdir()
        (folder / "release.mkv").write_bytes(b"\x00")
        releases.append(folder)

    queue_file = tmp_path / "queue.json"

    def _build() -> int:
        q = BatchQueue(queue_file=queue_file)
        for folder in releases:
            q.add_path(folder)
        q.save()
        return len(q)

    result = benchmark(_build)
    assert result == 20
