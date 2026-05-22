from __future__ import annotations

import pytest

pytestmark = pytest.mark.benchmark


@pytest.mark.realmedia
def test_bench_probe_media_file_realmedia(benchmark, tmp_path) -> None:
    """Placeholder for fixture-backed MediaInfo benchmark."""
    pytest.skip("Real-media fixture not yet wired (S11)")
