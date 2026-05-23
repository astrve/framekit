from __future__ import annotations

from copy import deepcopy

import pytest

from framekit.commands import pipeline as pipeline_module


class _TtyStdin:
    @staticmethod
    def isatty() -> bool:
        return True


class _FakeStore:
    def __init__(self, data: dict) -> None:
        self.data = deepcopy(data)
        self.saved: list[dict] = []

    def load(self) -> dict:
        return deepcopy(self.data)

    def save(self, data: dict) -> None:
        self.data = deepcopy(data)
        self.saved.append(deepcopy(data))


def _valid_tmdb_token() -> str:
    return "eyJ" + ("a" * 30) + "." + ("b" * 30) + "." + ("c" * 30)


def test_pipeline_tmdb_prompt_can_store_token(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = {
        "metadata": {
            "tmdb_read_access_token": "",
            "prompt_missing_token_in_pipeline": True,
        }
    }
    store = _FakeStore(settings)

    monkeypatch.delenv("FRAMEKIT_TMDB_READ_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(pipeline_module.sys, "stdin", _TtyStdin())
    monkeypatch.setattr(pipeline_module, "select_one", lambda **_kwargs: "add")
    monkeypatch.setattr(
        pipeline_module.click, "prompt", lambda *_args, **_kwargs: _valid_tmdb_token()
    )

    def _store_token(fake_store: _FakeStore, token: str) -> dict:
        assert token == _valid_tmdb_token()
        fake_store.data.setdefault("metadata", {})["tmdb_read_access_token"] = "<encrypted>"
        return fake_store.load()

    monkeypatch.setattr(pipeline_module, "_store_pipeline_tmdb_token", _store_token)

    refreshed, enabled = pipeline_module._maybe_prompt_missing_tmdb_token(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        selected_modules={"nfo"},
        metadata_enabled=True,
        auto_mode=False,
    )

    assert enabled is True
    assert refreshed["metadata"]["tmdb_read_access_token"] == "<encrypted>"


def test_pipeline_tmdb_prompt_can_disable_future_reminder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = {
        "metadata": {
            "tmdb_read_access_token": "",
            "prompt_missing_token_in_pipeline": True,
        }
    }
    store = _FakeStore(settings)

    monkeypatch.delenv("FRAMEKIT_TMDB_READ_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(pipeline_module.sys, "stdin", _TtyStdin())
    monkeypatch.setattr(pipeline_module, "select_one", lambda **_kwargs: "never")

    refreshed, enabled = pipeline_module._maybe_prompt_missing_tmdb_token(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        selected_modules={"prez"},
        metadata_enabled=True,
        auto_mode=False,
    )

    assert enabled is False
    assert refreshed["metadata"]["prompt_missing_token_in_pipeline"] is False
    assert store.saved


def test_pipeline_tmdb_prompt_skips_current_run(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = {
        "metadata": {
            "tmdb_read_access_token": "",
            "prompt_missing_token_in_pipeline": True,
        }
    }
    store = _FakeStore(settings)

    monkeypatch.delenv("FRAMEKIT_TMDB_READ_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(pipeline_module.sys, "stdin", _TtyStdin())
    monkeypatch.setattr(pipeline_module, "select_one", lambda **_kwargs: "skip")

    refreshed, enabled = pipeline_module._maybe_prompt_missing_tmdb_token(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        selected_modules={"upload"},
        metadata_enabled=True,
        auto_mode=False,
    )

    assert enabled is False
    assert refreshed["metadata"]["prompt_missing_token_in_pipeline"] is True
    assert store.saved == []
