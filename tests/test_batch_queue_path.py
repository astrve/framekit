from __future__ import annotations

from ouro.modules.batch.queue import BatchQueue


def test_batch_queue_defaults_to_cache_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OURO_CACHE_DIR", str(tmp_path / "cache"))

    queue = BatchQueue()

    assert str(queue.queue_file).startswith(str(tmp_path / "cache"))
    assert queue.queue_file.name == ".ouro_batch_queue.json"
