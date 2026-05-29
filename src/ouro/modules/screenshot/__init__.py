"""Screenshot extraction module.

This module provides functionality for extracting screenshots from video files
using FFmpeg, with intelligent frame selection to avoid black frames and credits.

Public API:
    - FrameAnalyzer: Analyzes video frames for quality and content
    - ScreenshotExtractor: Extracts screenshots from video files
"""

from ouro.modules.screenshot.analyzer import FrameAnalyzer
from ouro.modules.screenshot.extractor import ScreenshotExtractor

__all__ = ["FrameAnalyzer", "ScreenshotExtractor"]
