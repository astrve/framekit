from __future__ import annotations

from framekit.modules.batch.queue import BatchQueue


def test_batch_queue_defaults_to_cache_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRAMEKIT_CACHE_DIR", str(tmp_path / "cache"))

    queue = BatchQueue()

    assert str(queue.queue_file).startswith(str(tmp_path / "cache"))
    assert queue.queue_file.name == ".framekit_batch_queue.json"
