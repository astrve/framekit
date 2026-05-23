"""Tests for extraction service orchestration.

Following TDD principles - tests written before implementation.
Tests cover:
- Service orchestration of subtitle/audio/video extractors
- Batch file processing
- Progress reporting integration
- Error handling and recovery
- Settings integration
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from framekit.core.tools import ToolRegistry  # noqa: E402
from framekit.modules.extract.models import (  # noqa: E402
    AudioFormat,
    AudioTrack,
    ExtractionOptions,
    ExtractionResult,
    SubtitleFormat,
    SubtitleTrack,
    VideoCodec,
    VideoTrack,
)


class TestExtractionService:
    """Test ExtractionService orchestration."""

    @pytest.fixture(autouse=True)
    def mock_probe_media_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock media probing so service tests don't depend on real media parsing."""
        fake_info = SimpleNamespace(
            video_codec="H264",
            video_format_name="AVC",
            width=1920,
            height=1080,
            video_frame_rate=23.976,
            video_bitrate=4_000_000,
            hdr_format=None,
            audio_tracks=[
                SimpleNamespace(
                    id=1,
                    codec="AAC",
                    format_name="AAC",
                    codec_id="A_AAC",
                    language="eng",
                    title="Main",
                    is_default=True,
                    bitrate=128_000,
                )
            ],
            subtitle_tracks=[
                SimpleNamespace(
                    id=2,
                    codec="SubRip",
                    format_name="SubRip",
                    codec_id="S_TEXT/UTF8",
                    language="eng",
                    title="English",
                    is_forced=False,
                    is_default=True,
                    subtitle_variant="full",
                )
            ],
        )
        monkeypatch.setattr(
            "framekit.modules.extract.service.probe_media_file", lambda _: fake_info
        )

    @pytest.fixture
    def mock_registry(self):
        """Create mock tool registry."""
        registry = Mock(spec=ToolRegistry)
        registry.resolve_tool_path.return_value = Path("/usr/bin/ffmpeg")
        return registry

    @pytest.fixture
    def mock_subtitle_extractor(self):
        """Create mock subtitle extractor."""
        extractor = Mock()
        extractor.extract_subtitle.return_value = ExtractionResult(
            track=SubtitleTrack(
                track_id=2,
                codec="subrip",
                language="eng",
                language_name="English",
            ),
            source_file=Path("test.mkv"),
            output_file=Path("test.eng.srt"),
            success=True,
            format_converted=False,
        )
        return extractor

    @pytest.fixture
    def mock_audio_extractor(self):
        """Create mock audio extractor."""
        extractor = Mock()
        extractor.extract_audio.return_value = ExtractionResult(
            track=AudioTrack(
                track_id=1,
                codec="aac",
                language="eng",
                language_name="English",
                channels=2,
                sample_rate=48000,
            ),
            source_file=Path("test.mkv"),
            output_file=Path("test.eng.aac"),
            success=True,
            format_converted=False,
        )
        return extractor

    @pytest.fixture
    def mock_video_extractor(self):
        """Create mock video extractor."""
        extractor = Mock()
        extractor.extract_video.return_value = ExtractionResult(
            track=VideoTrack(
                track_id=0,
                codec="h264",
                width=1920,
                height=1080,
                fps=23.976,
            ),
            source_file=Path("test.mkv"),
            output_file=Path("test.mp4"),
            success=True,
            codec_converted=False,
        )
        return extractor

    def test_service_initialization(self, mock_registry):
        """Test service can be initialized with registry."""
        from framekit.modules.extract.service import ExtractionService

        service = ExtractionService(mock_registry)
        assert service.registry == mock_registry

    def test_extract_subtitles_single_file(self, mock_registry, mock_subtitle_extractor, tmp_path):
        """Test extracting subtitles from a single file."""
        from framekit.modules.extract.service import ExtractionService

        # Create test file
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        # Mock the extractor
        with patch(
            "framekit.modules.extract.service.SubtitleExtractor",
            return_value=mock_subtitle_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = ExtractionOptions(
                output_format=SubtitleFormat.SRT,
                languages=["eng"],
            )

            report, results = service.extract_subtitles(
                files=[test_file],
                options=options,
            )

            assert report.tool == "extract"
            assert report.processed == 1
            assert len(results) == 1
            assert results[0].success
            mock_subtitle_extractor.extract_subtitle.assert_called_once()

    def test_extract_subtitles_batch(self, mock_registry, mock_subtitle_extractor, tmp_path):
        """Test batch subtitle extraction from multiple files."""
        from framekit.modules.extract.service import ExtractionService

        # Create test files
        test_files = [tmp_path / f"test{i}.mkv" for i in range(3)]
        for f in test_files:
            f.touch()

        with patch(
            "framekit.modules.extract.service.SubtitleExtractor",
            return_value=mock_subtitle_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = ExtractionOptions(output_format=SubtitleFormat.SRT)

            report, results = service.extract_subtitles(
                files=test_files,
                options=options,
            )

            assert report.processed == 3
            assert len(results) == 3
            assert all(r.success for r in results)
            assert mock_subtitle_extractor.extract_subtitle.call_count == 3

    def test_extract_audio_single_file(self, mock_registry, mock_audio_extractor, tmp_path):
        """Test extracting audio from a single file."""
        from framekit.modules.extract.models import AudioExtractionOptions
        from framekit.modules.extract.service import ExtractionService

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch(
            "framekit.modules.extract.service.AudioExtractor",
            return_value=mock_audio_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = AudioExtractionOptions(
                output_format=AudioFormat.AAC,
                languages=["eng"],
            )

            report, results = service.extract_audio(
                files=[test_file],
                options=options,
            )

            assert report.tool == "extract"
            assert report.processed == 1
            assert len(results) == 1
            assert results[0].success
            mock_audio_extractor.extract_audio.assert_called_once()

    def test_extract_audio_original_uses_source_codec_extension(
        self, mock_registry, mock_audio_extractor, tmp_path
    ):
        """Original/copy audio extraction must not emit invalid '.audio' files."""
        from framekit.modules.extract.models import AudioExtractionOptions
        from framekit.modules.extract.service import ExtractionService

        test_file = tmp_path / "movie.mkv"
        test_file.touch()
        mock_audio_extractor.detect_audio_format.return_value = AudioFormat.AAC

        with patch(
            "framekit.modules.extract.service.AudioExtractor",
            return_value=mock_audio_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = AudioExtractionOptions(output_format=AudioFormat.ORIGINAL)

            _report, _results = service.extract_audio(files=[test_file], options=options)

            call = mock_audio_extractor.extract_audio.call_args
            assert call is not None
            assert call.kwargs["output_path"].name == "movie.a0.aac"

    def test_extract_video_single_file(self, mock_registry, mock_video_extractor, tmp_path):
        """Test extracting video from a single file."""
        from framekit.modules.extract.models import VideoExtractionOptions
        from framekit.modules.extract.service import ExtractionService

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch(
            "framekit.modules.extract.service.VideoExtractor",
            return_value=mock_video_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = VideoExtractionOptions(
                codec=VideoCodec.H264,
                crf=23,
            )

            report, results = service.extract_video(
                files=[test_file],
                options=options,
            )

            assert report.tool == "extract"
            assert report.processed == 1
            assert len(results) == 1
            assert results[0].success
            mock_video_extractor.extract_video.assert_called_once()

    def test_progress_callback_invoked(self, mock_registry, mock_subtitle_extractor, tmp_path):
        """Test that progress callback is invoked during extraction."""
        from framekit.modules.extract.service import ExtractionService

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        progress_callback = Mock()

        with patch(
            "framekit.modules.extract.service.SubtitleExtractor",
            return_value=mock_subtitle_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = ExtractionOptions(output_format=SubtitleFormat.SRT)

            service.extract_subtitles(
                files=[test_file],
                options=options,
                progress_callback=progress_callback,
            )

            # Progress callback should be called at least once
            assert progress_callback.call_count >= 1

    def test_error_handling_partial_success(self, mock_registry, mock_subtitle_extractor, tmp_path):
        """Test error handling with partial success."""
        from framekit.modules.extract.service import ExtractionService

        test_files = [tmp_path / f"test{i}.mkv" for i in range(3)]
        for f in test_files:
            f.touch()

        # Make second extraction fail
        mock_subtitle_extractor.extract_subtitle.side_effect = [
            ExtractionResult(
                track=SubtitleTrack(track_id=2, codec="subrip", language="eng"),
                source_file=test_files[0],
                output_file=Path("test0.srt"),
                success=True,
            ),
            ExtractionResult(
                track=SubtitleTrack(track_id=2, codec="subrip", language="eng"),
                source_file=test_files[1],
                output_file=Path("test1.srt"),
                success=False,
                error="Extraction failed",
            ),
            ExtractionResult(
                track=SubtitleTrack(track_id=2, codec="subrip", language="eng"),
                source_file=test_files[2],
                output_file=Path("test2.srt"),
                success=True,
            ),
        ]

        with patch(
            "framekit.modules.extract.service.SubtitleExtractor",
            return_value=mock_subtitle_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = ExtractionOptions(output_format=SubtitleFormat.SRT)

            report, results = service.extract_subtitles(
                files=test_files,
                options=options,
            )

            assert report.processed == 3
            assert len(results) == 3
            assert results[0].success
            assert not results[1].success
            assert results[2].success
            assert len(report.errors) >= 1

    def test_output_directory_creation(self, mock_registry, mock_subtitle_extractor, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        from framekit.modules.extract.service import ExtractionService

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        output_dir = tmp_path / "extracted" / "subtitles"
        assert not output_dir.exists()

        with patch(
            "framekit.modules.extract.service.SubtitleExtractor",
            return_value=mock_subtitle_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = ExtractionOptions(
                output_format=SubtitleFormat.SRT,
                output_dir=output_dir,
            )

            service.extract_subtitles(
                files=[test_file],
                options=options,
            )

            # Service should create output directory
            assert output_dir.exists()

    def test_extract_all_tracks(self, mock_registry, mock_subtitle_extractor, tmp_path):
        """Test extracting all tracks regardless of filters."""
        from framekit.modules.extract.service import ExtractionService

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        # Mock multiple tracks
        mock_subtitle_extractor.extract_subtitle.side_effect = [
            ExtractionResult(
                track=SubtitleTrack(track_id=2, codec="subrip", language="eng"),
                source_file=test_file,
                output_file=Path("test.eng.srt"),
                success=True,
            ),
            ExtractionResult(
                track=SubtitleTrack(track_id=3, codec="subrip", language="fra"),
                source_file=test_file,
                output_file=Path("test.fra.srt"),
                success=True,
            ),
        ]

        with patch(
            "framekit.modules.extract.service.SubtitleExtractor",
            return_value=mock_subtitle_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = ExtractionOptions(
                output_format=SubtitleFormat.SRT,
                extract_all=True,
            )

            report, results = service.extract_subtitles(
                files=[test_file],
                options=options,
            )

            # Should extract all tracks
            assert len(results) >= 1

    def test_nonexistent_file_handling(self, mock_registry):
        """Test handling of nonexistent files."""
        from framekit.modules.extract.service import ExtractionService

        service = ExtractionService(mock_registry)
        options = ExtractionOptions(output_format=SubtitleFormat.SRT)

        report, results = service.extract_subtitles(
            files=[Path("/nonexistent/file.mkv")],
            options=options,
        )

        # Should handle gracefully
        assert len(report.errors) >= 1
        assert (
            "not found" in report.errors[0].message.lower()
            or "does not exist" in report.errors[0].message.lower()
        )

    def test_empty_file_list(self, mock_registry):
        """Test handling of empty file list."""
        from framekit.modules.extract.service import ExtractionService

        service = ExtractionService(mock_registry)
        options = ExtractionOptions(output_format=SubtitleFormat.SRT)

        report, results = service.extract_subtitles(
            files=[],
            options=options,
        )

        assert report.processed == 0
        assert len(results) == 0

    def test_extract_subtitles_skips_font_tracks(
        self, mock_registry, mock_subtitle_extractor, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        """Embedded font subtitle-like streams must be skipped."""
        from framekit.modules.extract.service import ExtractionService

        test_file = tmp_path / "fonty.mkv"
        test_file.touch()

        fake_info = SimpleNamespace(
            video_codec="H264",
            video_format_name="AVC",
            width=1920,
            height=1080,
            video_frame_rate=23.976,
            video_bitrate=4_000_000,
            hdr_format=None,
            audio_tracks=[],
            subtitle_tracks=[
                SimpleNamespace(
                    id=2,
                    codec="application/x-truetype-font",
                    format_name="TrueType",
                    codec_id="S_TEXT/TTF",
                    language="und",
                    title="Embedded font",
                    is_forced=False,
                    is_default=False,
                    subtitle_variant="full",
                ),
                SimpleNamespace(
                    id=3,
                    codec="SubRip",
                    format_name="SubRip",
                    codec_id="S_TEXT/UTF8",
                    language="eng",
                    title="English",
                    is_forced=False,
                    is_default=True,
                    subtitle_variant="full",
                ),
            ],
        )
        monkeypatch.setattr(
            "framekit.modules.extract.service.probe_media_file", lambda _: fake_info
        )

        with patch(
            "framekit.modules.extract.service.SubtitleExtractor",
            return_value=mock_subtitle_extractor,
        ):
            service = ExtractionService(mock_registry)
            options = ExtractionOptions(output_format=SubtitleFormat.SRT, extract_all=True)
            report, results = service.extract_subtitles(files=[test_file], options=options)

            assert len(results) == 1
            assert report.warnings
            assert mock_subtitle_extractor.extract_subtitle.call_count == 1
