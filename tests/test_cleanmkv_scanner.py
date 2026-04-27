from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from framekit.core.models.media import MediaFileInfo, MediaTrack
from framekit.core.tools import ToolRegistry
from framekit.modules.cleanmkv import scanner


class _Registry(ToolRegistry):
    def __init__(self, mkvmerge: str | None = "mkvmerge") -> None:
        super().__init__()
        self.mkvmerge = mkvmerge

    def resolve_tool_path(self, tool_name: str) -> str | None:
        assert tool_name == "mkvmerge"
        return self.mkvmerge


def _completed(payload: dict, *, returncode: int = 0, stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=json.dumps(payload), stderr=stderr)


def _media_info(path: Path) -> MediaFileInfo:
    return MediaFileInfo(
        path=path,
        container="Matroska",
        duration_ms=60_000,
        size_bytes=1024,
        overall_bitrate=None,
        width=1920,
        height=1080,
        aspect_ratio=None,
        video_codec="H.264",
        video_profile=None,
        video_encoding_settings=None,
        video_library_name=None,
        video_format_name=None,
        video_codec_id=None,
        video_bitrate=None,
        video_frame_rate=None,
        video_bit_depth=None,
        video_stream_size_bytes=None,
        video_stream_size_ratio=None,
        hdr_format=None,
        audio_tracks=[
            MediaTrack(
                id=1,
                kind="audio",
                codec="E-AC-3",
                channels="5.1",
                bitrate=768_000,
                codec_id="A_EAC3",
                bit_depth=24,
            )
        ],
        subtitle_tracks=[
            MediaTrack(
                id=2,
                kind="subtitle",
                codec="UTF-8",
                codec_id="S_TEXT/UTF8",
                stream_size_bytes=2048,
            )
        ],
    )


def test_scan_mkv_file_parses_tracks_and_enriches_with_mediainfo(monkeypatch, tmp_path):
    movie = tmp_path / "Movie.MKV"
    movie.write_bytes(b"fake")

    payload = {
        "tracks": [
            {
                "id": 0,
                "type": "video",
                "codec": "MPEG-4p10/AVC/H.264",
                "properties": {},
            },
            {
                "id": 1,
                "type": "audio",
                "codec": "",
                "properties": {
                    "language_ietf": "fr-FR",
                    "track_name": "VFQ",
                    "default_track": True,
                    "forced_track": False,
                    "audio_channels": 6,
                },
            },
            {
                "id": 2,
                "type": "subtitles",
                "codec": "SubRip/SRT",
                "properties": {
                    "language": "eng",
                    "track_name": "Forced",
                    "default_track": False,
                    "forced_track": True,
                },
            },
        ]
    }

    monkeypatch.setattr(scanner, "_run", lambda cmd: _completed(payload))
    monkeypatch.setattr(scanner, "probe_media_file", _media_info)

    scan = scanner.scan_mkv_file(movie, _Registry())

    assert scan.path == movie
    assert len(scan.audio_tracks) == 1
    assert len(scan.subtitle_tracks) == 1

    audio = scan.audio_tracks[0]
    assert audio.track_id == 1
    assert audio.language == "french"
    assert audio.language_variant == "france"
    assert audio.title == "VFQ"
    assert audio.is_default is True
    assert audio.codec == "E-AC-3"
    assert audio.codec_id == "A_EAC3"
    assert audio.channels == "5.1"
    assert audio.bitrate == 768_000
    assert audio.bit_depth == 24

    subtitle = scan.subtitle_tracks[0]
    assert subtitle.track_id == 2
    assert subtitle.language == "english"
    assert subtitle.is_forced is True
    assert subtitle.subtitle_variant == "forced"
    assert subtitle.stream_size_bytes == 2048


def test_scan_folder_accepts_uppercase_mkv_and_ignores_other_files(monkeypatch, tmp_path):
    upper = tmp_path / "A.MKV"
    lower = tmp_path / "B.mkv"
    other = tmp_path / "notes.txt"
    for path in (upper, lower, other):
        path.write_bytes(b"x")

    seen: list[Path] = []

    def fake_scan(path: Path, registry):
        seen.append(path)
        return SimpleNamespace(path=path)

    monkeypatch.setattr(scanner, "scan_mkv_file", fake_scan)

    scans = scanner.scan_folder(tmp_path, _Registry())

    assert [scan.path.name for scan in scans] == ["A.MKV", "B.mkv"]
    assert seen == [upper, lower]


def test_scan_mkv_file_requires_mkvmerge(tmp_path):
    with pytest.raises(RuntimeError, match="mkvmerge"):
        scanner.scan_mkv_file(tmp_path / "missing.mkv", _Registry(mkvmerge=None))


def test_scan_mkv_file_reports_mkvmerge_failure(monkeypatch, tmp_path):
    movie = tmp_path / "broken.mkv"
    movie.write_bytes(b"x")
    monkeypatch.setattr(
        scanner,
        "_run",
        lambda cmd: SimpleNamespace(returncode=2, stdout="", stderr="boom"),
    )

    with pytest.raises(RuntimeError, match="boom"):
        scanner.scan_mkv_file(movie, _Registry())
