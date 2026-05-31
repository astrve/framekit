"""Unit tests for :mod:`swirrl.core.subprocess_safe`.

These tests cover the safety contract documented in ADR-0006: full-path
resolution, mandatory timeout, secret redaction, and the typed error
hierarchy. They do **not** require any external tool to be installed because
every subprocess call is monkeypatched at the boundary.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from swirrl.core import subprocess_safe
from swirrl.core.subprocess_safe import (
    MissingToolError,
    SafeSubprocessError,
    _redact_argv,
    popen_safe,
    resolve_tool,
    run_safe,
)


@pytest.fixture(autouse=True)
def _clear_tool_cache() -> None:
    """``resolve_tool`` is ``lru_cache``-d; clear between tests."""

    resolve_tool.cache_clear()


# ---------------------------------------------------------------------------
# resolve_tool
# ---------------------------------------------------------------------------


def test_resolve_tool_returns_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/mkvmerge")
    assert resolve_tool("mkvmerge") == "/usr/bin/mkvmerge"


def test_resolve_tool_accepts_absolute_path(tmp_path: Path) -> None:
    binary = tmp_path / "fake_tool"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    assert resolve_tool(str(binary)) == str(binary)


def test_resolve_tool_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: None)
    with pytest.raises(MissingToolError) as exc_info:
        resolve_tool("no_such_tool_xyz")
    assert "not found on PATH" in str(exc_info.value)
    assert exc_info.value.tool == "no_such_tool_xyz"


# ---------------------------------------------------------------------------
# run_safe
# ---------------------------------------------------------------------------


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _stub_run(
    completed: _FakeCompleted,
    captured: dict[str, object] | None = None,
):
    def _run(argv: Sequence[str], **kwargs: object) -> _FakeCompleted:
        if captured is not None:
            captured["argv"] = tuple(argv)
            captured["kwargs"] = kwargs
        return completed

    return _run


def test_run_safe_rejects_string_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/x")
    with pytest.raises(TypeError):
        run_safe("ls -la", timeout=5)  # type: ignore[arg-type]


def test_run_safe_requires_nonempty_argv() -> None:
    with pytest.raises(ValueError):
        run_safe([], timeout=5)


def test_run_safe_resolves_and_passes_full_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/echo")
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        subprocess_safe.subprocess,
        "run",
        _stub_run(_FakeCompleted(returncode=0, stdout="hi"), captured),
    )
    result = run_safe(["echo", "hi"], timeout=5)
    assert result.returncode == 0
    assert captured["argv"] == ("/usr/bin/echo", "hi")
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["shell"] is False
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"


def test_run_safe_raises_on_nonzero_when_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        subprocess_safe.subprocess,
        "run",
        _stub_run(_FakeCompleted(returncode=1, stderr="boom")),
    )
    with pytest.raises(SafeSubprocessError) as exc_info:
        run_safe(["ffmpeg", "-version"], timeout=5)
    assert exc_info.value.returncode == 1
    assert "boom" in exc_info.value.stderr


def test_run_safe_returns_on_nonzero_without_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(
        subprocess_safe.subprocess,
        "run",
        _stub_run(_FakeCompleted(returncode=2, stderr="warn")),
    )
    completed = run_safe(["ffmpeg", "-version"], timeout=5, check=False)
    assert completed.returncode == 2
    assert completed.stderr == "warn"


def test_run_safe_translates_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    def _raise(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=1)

    monkeypatch.setattr(subprocess_safe.subprocess, "run", _raise)
    with pytest.raises(SafeSubprocessError) as exc_info:
        run_safe(["ffmpeg", "-i", "x.mkv"], timeout=1)
    assert exc_info.value.returncode is None
    assert "timed out" in str(exc_info.value)


def test_run_safe_merges_extra_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/x")
    monkeypatch.setenv("EXISTING", "1")
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        subprocess_safe.subprocess,
        "run",
        _stub_run(_FakeCompleted(returncode=0), captured),
    )
    run_safe(["x"], timeout=5, extra_env={"NEW_KEY": "value"})
    env = captured["kwargs"]["env"]  # type: ignore[index]
    assert isinstance(env, Mapping)
    assert env["EXISTING"] == "1"
    assert env["NEW_KEY"] == "value"


# ---------------------------------------------------------------------------
# popen_safe
# ---------------------------------------------------------------------------


def test_popen_safe_rejects_string_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/x")
    with pytest.raises(TypeError):
        popen_safe("ls")  # type: ignore[arg-type]


def test_popen_safe_resolves_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_safe.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    captured: dict[str, object] = {}

    class _FakePopen:
        def __init__(self, argv: Sequence[str], **kwargs: object) -> None:
            captured["argv"] = tuple(argv)
            captured["kwargs"] = kwargs

    monkeypatch.setattr(subprocess_safe.subprocess, "Popen", _FakePopen)
    popen_safe(["ffmpeg", "-version"])
    assert captured["argv"] == ("/usr/bin/ffmpeg", "-version")


# ---------------------------------------------------------------------------
# _redact_argv
# ---------------------------------------------------------------------------


def test_redact_argv_masks_long_url_segment() -> None:
    redacted = _redact_argv(
        [
            "mktorrent",
            "-a",
            "https://tracker.example/abcdef1234567890abcdef12345/announce",
            "release.mkv",
        ]
    )
    assert redacted[2].startswith("https://tracker.example/")
    assert "<redacted>" in redacted[2]
    assert redacted[2].endswith("/announce")


def test_redact_argv_leaves_short_segments_alone() -> None:
    redacted = _redact_argv(["mkvmerge", "-J", "/tmp/short/path"])
    assert redacted == ("mkvmerge", "-J", "/tmp/short/path")
