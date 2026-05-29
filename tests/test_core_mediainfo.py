from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ouro.core import mediainfo


def test_media_file_info_from_cache_ignores_invalid_tracks(tmp_path: Path) -> None:
    file_path = tmp_path / "movie.mkv"
    payload = {
        "path": str(file_path),
        "container": "Matroska",
        "size_bytes": 1234,
        "audio_tracks": [
            {"id": 1, "kind": "audio", "codec": "AAC"},
            "invalid-track",
        ],
        "subtitle_tracks": [{"id": 2, "kind": "subtitle", "codec": "SRT"}],
    }

    info = mediainfo._media_file_info_from_cache(payload)

    assert info.path == file_path
    assert info.size_bytes == 1234
    assert len(info.audio_tracks) == 1
    assert len(info.subtitle_tracks) == 1
    assert info.audio_tracks[0].codec == "AAC"


def test_probe_media_file_handles_missing_video_track(monkeypatch, tmp_path: Path) -> None:
    file_path = tmp_path / "movie.mkv"
    file_path.write_bytes(b"abc")

    general_track = SimpleNamespace(
        track_type="General",
        format="Matroska",
        duration="60000",
        file_size="9999",
        overall_bit_rate="1024",
        bit_rate=None,
    )
    audio_track = SimpleNamespace(
        track_type="Audio",
        streamorder="1",
        format="AAC",
        codec_id="A_AAC",
        language="en",
        language_ietf=None,
        title="Main",
        default="Yes",
        forced="No",
        channel_s="2",
        channels=None,
        bit_rate="128000",
        format_profile="LC",
        stream_size="1000",
        stream_size_proportion="0.2",
    )

    class _FakeMediaInfo:
        @staticmethod
        def parse(_path: str):
            return SimpleNamespace(tracks=[general_track, audio_track])

    monkeypatch.setattr(mediainfo, "MediaInfo", _FakeMediaInfo)
    info = mediainfo.probe_media_file(file_path)

    assert info.container == "MATROSKA"
    assert info.size_bytes == 9999
    assert info.video_codec is None
    assert info.width is None
    assert len(info.audio_tracks) == 1
