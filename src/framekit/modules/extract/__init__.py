"""Media extraction module for subtitles, audio, and video streams.

This module provides functionality to extract and convert media streams from
video files using FFmpeg and mkvextract.
"""

from __future__ import annotations

from framekit.modules.extract.audio_extractor import AudioExtractor
from framekit.modules.extract.models import (
    AudioExtractionOptions,
    AudioFormat,
    AudioTrack,
    ExtractionOptions,
    ExtractionResult,
    SubtitleFormat,
    SubtitleTrack,
    VideoCodec,
    VideoExtractionOptions,
    VideoTrack,
)
from framekit.modules.extract.service import ExtractionService
from framekit.modules.extract.subtitle_extractor import SubtitleExtractor
from framekit.modules.extract.video_extractor import VideoExtractor

__all__ = [
    # Extractors
    "SubtitleExtractor",
    "AudioExtractor",
    "VideoExtractor",
    # Service
    "ExtractionService",
    # Models - Tracks
    "SubtitleTrack",
    "AudioTrack",
    "VideoTrack",
    # Models - Formats/Codecs
    "SubtitleFormat",
    "AudioFormat",
    "VideoCodec",
    # Models - Options
    "ExtractionOptions",
    "AudioExtractionOptions",
    "VideoExtractionOptions",
    # Models - Results
    "ExtractionResult",
]
