from __future__ import annotations

from types import SimpleNamespace

import pytest

from framekit.core.models.cleanmkv import RemuxPlan
from framekit.core.tools import ToolRegistry
from framekit.modules.cleanmkv import remuxer


class _Registry(ToolRegistry):
    def __init__(self, mkvmerge: str | None = "mkvmerge") -> None:
        self.mkvmerge = mkvmerge

    def resolve_tool_path(self, tool_name: str) -> str | None:
        assert tool_name == "mkvmerge"
        return self.mkvmerge


def _plan(tmp_path, *, copy_only: bool) -> RemuxPlan:
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"mkv")
    return RemuxPlan(
        source=source,
        target=tmp_path / "clean" / "movie.mkv",
        keep_audio_track_ids=[1, 2],
        keep_subtitle_track_ids=[3],
        default_audio_track_id=2,
        default_subtitle_track_id=None,
        copy_only=copy_only,
    )


def test_copy_only_plan_copies_when_enabled(tmp_path):
    plan = _plan(tmp_path, copy_only=True)

    remuxer.apply_remux_plan(plan, _Registry(), copy_unchanged_files=True)

    assert plan.target.read_bytes() == b"mkv"


def test_copy_only_plan_can_skip_copying_unchanged_files(tmp_path):
    plan = _plan(tmp_path, copy_only=True)

    remuxer.apply_remux_plan(plan, _Registry(), copy_unchanged_files=False)

    assert not plan.target.exists()


def test_remux_command_sets_default_flags_for_all_kept_tracks(monkeypatch, tmp_path):
    plan = _plan(tmp_path, copy_only=False)
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str]):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(remuxer, "_run", fake_run)

    remuxer.apply_remux_plan(plan, _Registry())

    cmd = captured["cmd"]
    assert cmd[:3] == ["mkvmerge", "-o", str(plan.target)]
    assert "--audio-tracks" in cmd
    assert "1,2" in cmd
    assert "--subtitle-tracks" in cmd
    assert "3" in cmd
    assert "1:no" in cmd
    assert "2:yes" in cmd
    assert "3:no" in cmd


def test_remux_plan_requires_mkvmerge(tmp_path):
    plan = _plan(tmp_path, copy_only=False)

    with pytest.raises(RuntimeError, match="mkvmerge"):
        remuxer.apply_remux_plan(plan, _Registry(mkvmerge=None))


def test_remux_failure_raises_runtime_error(monkeypatch, tmp_path):
    plan = _plan(tmp_path, copy_only=False)
    monkeypatch.setattr(
        remuxer,
        "_run",
        lambda cmd: SimpleNamespace(returncode=1, stderr="bad flags"),
    )

    with pytest.raises(RuntimeError, match="bad flags"):
        remuxer.apply_remux_plan(plan, _Registry())
