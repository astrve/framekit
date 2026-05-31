"""Media extraction module for subtitles, audio, and video streams.

This module provides functionality to extract and convert media streams from
video files using FFmpeg and mkvextract.
"""

from __future__ import annotations

from swirrl.modules.extract.audio_extractor import AudioExtractor
from swirrl.modules.extract.models import (
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
from swirrl.modules.extract.service import ExtractionService
from swirrl.modules.extract.subtitle_extractor import SubtitleExtractor
from swirrl.modules.extract.video_extractor import VideoExtractor

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
