"""Unit tests for :mod:`framekit.modules.validate.service`.

Covers ``ValidationResult`` accounting, the ``ValidationService`` orchestrator
and each ``_check_*`` private helper. Media-info dependent checks
monkeypatch :func:`framekit.modules.validate.service.probe_media_file` so
the suite stays fast and never invokes ``mediainfo``/``ffprobe``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from framekit.modules.validate import service as validate_service
from framekit.modules.validate.service import (
    ValidationIssue,
    ValidationResult,
    ValidationRules,
    ValidationService,
    ValidationSeverity,
)

# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


def test_validation_result_starts_clean(tmp_path: Path) -> None:
    result = ValidationResult(release_path=tmp_path, release_name="X")
    assert result.is_valid is True
    assert result.issues == []
    assert (result.checks_passed, result.checks_failed, result.checks_warned) == (0, 0, 0)


def test_add_error_marks_invalid(tmp_path: Path) -> None:
    result = ValidationResult(release_path=tmp_path, release_name="X")
    result.add_error("cat", "msg", "fix")
    assert result.is_valid is False
    assert result.checks_failed == 1
    assert result.issues[0] == ValidationIssue(ValidationSeverity.ERROR, "cat", "msg", "fix")


def test_add_warning_keeps_valid(tmp_path: Path) -> None:
    result = ValidationResult(release_path=tmp_path, release_name="X")
    result.add_warning("cat", "msg")
    assert result.is_valid is True
    assert result.checks_warned == 1
    assert result.issues[0].severity is ValidationSeverity.WARNING


def test_add_pass_increments(tmp_path: Path) -> None:
    result = ValidationResult(release_path=tmp_path, release_name="X")
    result.add_pass()
    result.add_pass()
    assert result.checks_passed == 2


# ---------------------------------------------------------------------------
# ValidationService.validate — top-level
# ---------------------------------------------------------------------------


def test_validate_missing_path_reports_error(tmp_path: Path) -> None:
    target = tmp_path / "does-not-exist"
    result = ValidationService().validate(target)
    assert result.is_valid is False
    assert any(issue.category == "path" for issue in result.issues)


def test_validate_empty_folder_reports_no_media(tmp_path: Path) -> None:
    result = ValidationService().validate(tmp_path)
    assert result.is_valid is False
    assert any(issue.category == "files" for issue in result.issues)


def test_validate_finds_media_recursively(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "release.mkv").write_bytes(b"\x00")

    fake_info = SimpleNamespace(
        video_codec="HEVC",
        width=1920,
        overall_bitrate=8_000_000,
        audio_tracks=[SimpleNamespace()],
        subtitle_tracks=[],
    )
    monkeypatch.setattr(validate_service, "probe_media_file", lambda _: fake_info)

    rules = ValidationRules(
        require_nfo=False, allowed_containers=[".mkv"], min_video_bitrate_kbps=0
    )
    result = ValidationService(rules).validate(tmp_path)
    assert result.is_valid is True
    assert result.checks_passed > 0


# ---------------------------------------------------------------------------
# _find_media_files
# ---------------------------------------------------------------------------


def test_find_media_files_filters_by_extension(tmp_path: Path) -> None:
    (tmp_path / "a.mkv").write_bytes(b"\x00")
    (tmp_path / "b.mp4").write_bytes(b"\x00")
    (tmp_path / "c.txt").write_bytes(b"\x00")
    svc = ValidationService()
    files = svc._find_media_files(tmp_path)
    suffixes = {f.suffix for f in files}
    assert suffixes == {".mkv", ".mp4"}


# ---------------------------------------------------------------------------
# Container checks
# ---------------------------------------------------------------------------


def test_check_containers_rejects_unknown_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "weird.avi").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, allowed_containers=[".mkv", ".mp4"])
    result = ValidationService(rules).validate(tmp_path)
    assert any(issue.category == "container" for issue in result.issues)


# ---------------------------------------------------------------------------
# NFO check
# ---------------------------------------------------------------------------


def test_check_nfo_warns_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "release.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=True)
    result = ValidationService(rules).validate(tmp_path)
    assert any(issue.category == "nfo" for issue in result.issues)


def test_check_nfo_passes_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "release.mkv").write_bytes(b"\x00")
    (tmp_path / "release.nfo").write_text("[info]")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=True)
    result = ValidationService(rules).validate(tmp_path)
    assert all(issue.category != "nfo" for issue in result.issues)


def test_check_nfo_skipped_when_not_required(tmp_path: Path) -> None:
    rules = ValidationRules(require_nfo=False)
    svc = ValidationService(rules)
    result = ValidationResult(release_path=tmp_path, release_name="X")
    svc._check_nfo(result, tmp_path)
    # Early return path adds neither pass nor warn.
    assert result.checks_passed == 0
    assert all(issue.category != "nfo" for issue in result.issues)


# ---------------------------------------------------------------------------
# Video quality checks
# ---------------------------------------------------------------------------


def test_video_codec_not_allowed_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "release.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="MPEG2",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, allowed_video_codecs=["HEVC"])
    result = ValidationService(rules).validate(tmp_path)
    assert any(issue.category == "video" and "MPEG2" in issue.message for issue in result.issues)


def test_video_codec_h264_variant_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "release.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="H264",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, allowed_video_codecs=["H.264", "AVC", "x264"])
    result = ValidationService(rules).validate(tmp_path)
    assert all(
        not (issue.category == "video" and "not in allowed list" in issue.message)
        for issue in result.issues
    )


def test_video_resolution_below_minimum_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "r.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=720,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, min_resolution_width=1920)
    result = ValidationService(rules).validate(tmp_path)
    assert any(
        issue.category == "video" and "Resolution too low" in issue.message
        for issue in result.issues
    )


def test_video_low_bitrate_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "r.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=1_000_000,  # 1000 kbps
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, min_video_bitrate_kbps=4000)
    result = ValidationService(rules).validate(tmp_path)
    bitrate_issues = [
        i for i in result.issues if i.category == "video" and "bitrate" in i.message.lower()
    ]
    assert bitrate_issues
    assert bitrate_issues[0].severity is ValidationSeverity.WARNING


def test_video_check_handles_probe_failure_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "broken.mkv").write_bytes(b"\x00")

    def _raise(_: Any) -> Any:
        raise RuntimeError("simulated mediainfo failure")

    monkeypatch.setattr(validate_service, "probe_media_file", _raise)
    rules = ValidationRules(require_nfo=False)
    result = ValidationService(rules).validate(tmp_path)
    assert any(
        issue.category == "video" and "Could not read" in issue.message for issue in result.issues
    )


# ---------------------------------------------------------------------------
# Audio checks
# ---------------------------------------------------------------------------


def test_audio_warns_when_no_tracks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "r.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False)
    result = ValidationService(rules).validate(tmp_path)
    assert any(issue.category == "audio" for issue in result.issues)


def test_audio_skipped_when_no_codecs_allowed(tmp_path: Path) -> None:
    rules = ValidationRules(allowed_audio_codecs=[])
    svc = ValidationService(rules)
    result = ValidationResult(release_path=tmp_path, release_name="X")
    svc._check_audio(result, [])
    assert result.checks_passed == 0
    assert result.issues == []


# ---------------------------------------------------------------------------
# Subtitle checks
# ---------------------------------------------------------------------------


def test_subtitles_warn_when_required_and_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "r.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, require_subs=True)
    result = ValidationService(rules).validate(tmp_path)
    assert any(issue.category == "subtitles" for issue in result.issues)


def test_subtitles_skipped_when_not_required(tmp_path: Path) -> None:
    rules = ValidationRules(require_subs=False)
    svc = ValidationService(rules)
    result = ValidationResult(release_path=tmp_path, release_name="X")
    svc._check_subtitles(result, [])
    assert result.checks_passed == 0


# ---------------------------------------------------------------------------
# File-size checks
# ---------------------------------------------------------------------------


def test_file_size_error_when_above_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    big = tmp_path / "big.mkv"
    big.write_bytes(b"\x00")

    # Simulate a 5 GB file via os.stat.size - only for the specific file
    class _BigStat:
        st_size = 5 * 1024 * 1024 * 1024
        st_mode = 0o100644
        st_ino = 1
        st_dev = 1
        st_nlink = 1
        st_uid = 0
        st_gid = 0
        st_atime = 0.0
        st_mtime = 0.0
        st_ctime = 0.0

    original_stat = Path.stat

    def _mock_stat(self: Path, *, follow_symlinks: bool = True):  # type: ignore[no-untyped-def]
        # Only mock the specific big.mkv file, let others use real stat
        if self == big:
            return _BigStat()
        return original_stat(self, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", _mock_stat)
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, max_file_size_gb=1.0)
    result = ValidationService(rules).validate(tmp_path)
    assert any(issue.category == "size" for issue in result.issues)


# ---------------------------------------------------------------------------
# Naming checks
# ---------------------------------------------------------------------------


def test_naming_pattern_match_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "Movie.2024.1080p.BluRay.x265-GROUP.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, naming_pattern=r"\.\d{4}\.")
    result = ValidationService(rules).validate(tmp_path)
    assert all(issue.category != "naming" for issue in result.issues)


def test_naming_pattern_mismatch_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "weird name.mkv").write_bytes(b"\x00")
    monkeypatch.setattr(
        validate_service,
        "probe_media_file",
        lambda _: SimpleNamespace(
            video_codec="HEVC",
            width=1920,
            overall_bitrate=4_000_000,
            audio_tracks=[SimpleNamespace()],
            subtitle_tracks=[],
        ),
    )
    rules = ValidationRules(require_nfo=False, naming_pattern=r"\.\d{4}\.")
    result = ValidationService(rules).validate(tmp_path)
    assert any(issue.category == "naming" for issue in result.issues)
