from __future__ import annotations

from types import SimpleNamespace

from framekit.core.models.media import MediaTrack
from framekit.modules.nfo.scanner import _audio_summary_from_probe, _build_audio_tracks


def test_audio_description_detected_from_visual_impaired_flag() -> None:
    info = SimpleNamespace(
        audio_tracks=[
            MediaTrack(
                id=1,
                kind="audio",
                codec="E-AC-3",
                language="french",
                language_variant=None,
                title=None,
                is_default=True,
                is_forced=False,
                channels="2.0",
                bitrate=192000,
                format_name="E-AC-3",
                extra={"flag_visual_impaired": "1"},
            )
        ]
    )

    tracks = _build_audio_tracks(info)
    assert tracks[0].language_display == "French (AD)"
    assert tracks[0].subtitle_variant == "ad"

    summary = _audio_summary_from_probe(info)
    assert summary == ["French (AD) / E-AC-3.2.0"]
