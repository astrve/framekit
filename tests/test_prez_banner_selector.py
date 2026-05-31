from __future__ import annotations

import json
import time

from swirrl.modules.prez import banner_selector


def test_banner_selector_fallback_exposes_current_30_styles(monkeypatch, tmp_path) -> None:
    cache_file = tmp_path / "missing-cache.json"
    monkeypatch.setattr(banner_selector, "_cache_path", lambda: cache_file)
    monkeypatch.setattr(banner_selector, "_fetch_remote_index", lambda: None)

    designs = banner_selector.get_available_designs("fr")

    assert len(designs) == 30
    assert "_previews" not in designs
    assert "abstract_red" in designs
    assert "metal-frame_blue" in designs
    assert "white-steel_blue" in designs


def test_banner_selector_rejects_old_partial_cache(monkeypatch, tmp_path) -> None:
    cache_file = tmp_path / "prez_banners_index.json"
    cache_file.write_text(
        json.dumps(
            {
                "fetched_at": time.time(),
                "designs": {
                    "abstract_red": {"fr": list(banner_selector.BANNER_SECTIONS)},
                    "astro_gradient": {"fr": list(banner_selector.BANNER_SECTIONS)},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(banner_selector, "_cache_path", lambda: cache_file)

    assert banner_selector._load_cache() is None


def test_banner_selector_skips_preview_directories() -> None:
    entries = [
        {"type": "dir", "name": "_preview"},
        {"type": "dir", "name": "_previews"},
        {"type": "dir", "name": ".github"},
        {"type": "dir", "name": "abstract_red"},
    ]

    assert banner_selector._iter_design_names(entries) == ["abstract_red"]


def test_banner_url_uses_current_branch_design_name(monkeypatch, tmp_path) -> None:
    cache_file = tmp_path / "missing-cache.json"
    monkeypatch.setattr(banner_selector, "_cache_path", lambda: cache_file)
    monkeypatch.setattr(banner_selector, "_fetch_remote_index", lambda: None)

    url = banner_selector.get_banner_url("abstract_red", "fr", "audio")

    assert url.endswith("/feature/banners/abstract_red/fr/audio.png")
