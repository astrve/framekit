"""Screenshot extraction service orchestrating the complete workflow."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from swirrl.core.models.screenshot import (
    ScreenshotConfig,
    ScreenshotMetadata,
    ScreenshotReport,
    ScreenshotResult,
)
from swirrl.core.tools import ToolRegistry
from swirrl.modules.screenshot.analyzer import FrameAnalyzer
from swirrl.modules.screenshot.extractor import ScreenshotExtractor
from swirrl.modules.screenshot.naming import get_unique_filename


class ScreenshotService:
    """Service for orchestrating screenshot extraction workflow.

    Integrates FrameAnalyzer and ScreenshotExtractor to provide a complete
    screenshot extraction workflow with progress reporting, error handling,
    and batch processing support.
    """

    def __init__(
        self,
        analyzer: FrameAnalyzer | None = None,
        extractor: ScreenshotExtractor | None = None,
    ) -> None:
        """Initialize service with optional dependencies for testing.

        Args:
            analyzer: Optional FrameAnalyzer instance (creates default if None)
            extractor: Optional ScreenshotExtractor instance (creates default if None)
        """
        registry = ToolRegistry()
        self.analyzer = analyzer or FrameAnalyzer(registry)
        self.extractor = extractor or ScreenshotExtractor(registry)

    def extract_screenshots(
        self,
        video_paths: list[Path],
        output_dir: Path,
        config: ScreenshotConfig,
        release_name: str | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ScreenshotReport:
        """Extract screenshots from multiple video files.

        Args:
            video_paths: List of video file paths
            output_dir: Output directory for screenshots
            config: Screenshot configuration
            release_name: Optional release name for filenames
            progress_callback: Optional callback(message, current, total)

        Returns:
            ScreenshotReport with results for all videos
        """
        start_time = time.time()

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        results: list[ScreenshotResult] = []
        total_videos = len(video_paths)
        total_screenshots = 0
        total_failures = 0

        for idx, video_path in enumerate(video_paths, start=1):
            # Report progress
            if progress_callback:
                progress_callback(
                    f"Processing {video_path.name}",
                    idx,
                    total_videos,
                )

            # Process single video
            result = self._extract_from_video(
                video_path=video_path,
                output_dir=output_dir,
                config=config,
                release_name=release_name or video_path.stem,
            )

            results.append(result)

            if result.success:
                total_screenshots += len(result.screenshots)
            else:
                total_failures += 1

        elapsed_seconds = time.time() - start_time

        return ScreenshotReport(
            results=results,
            total_videos=total_videos,
            total_screenshots=total_screenshots,
            total_failures=total_failures,
            elapsed_seconds=elapsed_seconds,
        )

    def _video_not_found_result(self, video_path: Path, output_dir: Path) -> ScreenshotResult:
        logger.error(f"Video file not found: {video_path}")
        return ScreenshotResult(
            video_path=video_path,
            output_dir=output_dir,
            success=False,
            error=f"Video file not found: {video_path}",
        )

    def _build_output_paths(
        self,
        output_dir: Path,
        release_name: str,
        count: int,
        format_name: str,
    ) -> list[Path]:
        output_paths: list[Path] = []
        for idx in range(1, count + 1):
            output_paths.append(
                get_unique_filename(
                    output_dir=output_dir,
                    release_name=release_name,
                    index=idx,
                    format=format_name,
                )
            )
        return output_paths

    def _collect_screenshots_metadata(
        self,
        *,
        video_path: Path,
        timestamps: list[float],
        output_paths: list[Path],
        success_flags: list[bool],
        config: ScreenshotConfig,
        video_info: dict[str, float] | None,
    ) -> tuple[list[Path], list[ScreenshotMetadata]]:
        screenshots: list[Path] = []
        metadata_list: list[ScreenshotMetadata] = []
        width = int(config.width or (video_info.get("width", 0) if video_info else 0))
        height = int(config.height or (video_info.get("height", 0) if video_info else 0))

        for timestamp, output_path, success in zip(
            timestamps, output_paths, success_flags, strict=False
        ):
            if not success or not output_path.exists():
                continue
            screenshots.append(output_path)
            metadata_list.append(
                ScreenshotMetadata(
                    timestamp_seconds=timestamp,
                    frame_number=None,
                    width=width,
                    height=height,
                    file_size_bytes=output_path.stat().st_size,
                    quality_score=None,
                    is_black_frame=False,
                    video_source=video_path,
                )
            )

        return screenshots, metadata_list

    def _validate_video_for_auto_extract(
        self, video_path: Path, output_dir: Path
    ) -> tuple[dict[str, float] | None, float, ScreenshotResult | None]:
        if not video_path.exists():
            return None, 0.0, self._video_not_found_result(video_path, output_dir)

        video_info = self.analyzer.get_video_info(video_path)
        if not video_info:
            logger.error(f"Failed to get video info for {video_path}")
            return (
                None,
                0.0,
                ScreenshotResult(
                    video_path=video_path,
                    output_dir=output_dir,
                    success=False,
                    error="Failed to analyze video file",
                ),
            )

        duration = float(video_info.get("duration", 0.0))
        if duration <= 0:
            logger.error(f"Invalid video duration for {video_path}")
            return (
                video_info,
                duration,
                ScreenshotResult(
                    video_path=video_path,
                    output_dir=output_dir,
                    duration_seconds=duration,
                    success=False,
                    error="Invalid video duration",
                ),
            )

        return video_info, duration, None

    def _filter_timestamps_for_black_frames(
        self,
        *,
        video_path: Path,
        timestamps: list[float],
        config: ScreenshotConfig,
    ) -> tuple[list[float], int]:
        if not config.avoid_black_frames:
            return timestamps, 0

        black_frames = self.analyzer.detect_black_frames(
            video_path=video_path,
            threshold=config.black_threshold,
        )
        if not black_frames:
            return timestamps, 0

        original_count = len(timestamps)
        filtered = self.analyzer.filter_black_frames(
            timestamps=timestamps,
            black_frames=black_frames,
        )
        skipped = original_count - len(filtered)
        logger.debug(f"Filtered {skipped} timestamps near black frames")
        return filtered, skipped

    def extract_from_timestamps(
        self,
        video_path: Path,
        timestamps: list[float],
        output_dir: Path,
        config: ScreenshotConfig,
        release_name: str | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ScreenshotResult:
        """Extract screenshots at specific timestamps.

        Args:
            video_path: Video file path
            timestamps: List of timestamps in seconds
            output_dir: Output directory
            config: Screenshot configuration
            release_name: Optional release name
            progress_callback: Optional progress callback

        Returns:
            ScreenshotResult for the video
        """
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        release_name = release_name or video_path.stem
        if not video_path.exists():
            return self._video_not_found_result(video_path, output_dir)

        # Get video info
        video_info = self.analyzer.get_video_info(video_path)
        if not video_info:
            logger.warning(f"Could not get video info for {video_path}")
            duration = 0.0
        else:
            duration = video_info.get("duration", 0.0)

        output_paths = self._build_output_paths(
            output_dir,
            release_name,
            len(timestamps),
            config.format,
        )

        # Extract screenshots with progress reporting
        def extractor_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback(
                    f"Extracting screenshot {current}/{total}",
                    current,
                    total,
                )

        success_flags = self.extractor.extract_multiple(
            video_path=video_path,
            timestamps=timestamps,
            output_paths=output_paths,
            width=config.width,
            height=config.height,
            quality=config.quality,
            progress_callback=extractor_progress,
        )

        screenshots, metadata_list = self._collect_screenshots_metadata(
            video_path=video_path,
            timestamps=timestamps,
            output_paths=output_paths,
            success_flags=success_flags,
            config=config,
            video_info=video_info,
        )

        # Determine overall success
        all_success = all(success_flags)
        error = None if all_success else "Some screenshots failed to extract"

        return ScreenshotResult(
            video_path=video_path,
            output_dir=output_dir,
            screenshots=screenshots,
            metadata=metadata_list,
            duration_seconds=duration,
            success=all_success,
            error=error,
        )

    def _extract_from_video(
        self,
        video_path: Path,
        output_dir: Path,
        config: ScreenshotConfig,
        release_name: str,
    ) -> ScreenshotResult:
        """Extract screenshots from a single video using automatic analysis.

        Args:
            video_path: Path to video file
            output_dir: Output directory
            config: Screenshot configuration
            release_name: Release name for filenames

        Returns:
            ScreenshotResult for the video
        """
        video_info, duration, error_result = self._validate_video_for_auto_extract(
            video_path, output_dir
        )
        if error_result is not None:
            return error_result
        if video_info is None:
            return ScreenshotResult(
                video_path=video_path,
                output_dir=output_dir,
                success=False,
                error="Failed to analyze video file",
            )

        # Generate timestamps with percentage-based margins
        timestamps = self.analyzer.generate_timestamps(
            duration=duration,
            count=config.count,
            skip_start=config.skip_start_seconds,
            skip_end=config.skip_end_seconds,
            skip_start_percent=config.skip_start_percent,
            skip_end_percent=config.skip_end_percent,
            min_interval=config.min_interval_seconds,
        )

        if not timestamps:
            logger.error(f"No valid timestamps generated for {video_path}")
            return ScreenshotResult(
                video_path=video_path,
                output_dir=output_dir,
                duration_seconds=duration,
                success=False,
                error="No valid timestamps could be generated",
            )

        timestamps, skipped_black_frames = self._filter_timestamps_for_black_frames(
            video_path=video_path,
            timestamps=timestamps,
            config=config,
        )

        if not timestamps:
            logger.error(f"All timestamps filtered out for {video_path}")
            return ScreenshotResult(
                video_path=video_path,
                output_dir=output_dir,
                duration_seconds=duration,
                skipped_black_frames=skipped_black_frames,
                success=False,
                error="All timestamps were filtered out (too many black frames)",
            )

        output_paths = self._build_output_paths(
            output_dir,
            release_name,
            len(timestamps),
            config.format,
        )

        # Extract screenshots
        success_flags = self.extractor.extract_multiple(
            video_path=video_path,
            timestamps=timestamps,
            output_paths=output_paths,
            width=config.width,
            height=config.height,
            quality=config.quality,
        )

        screenshots, metadata_list = self._collect_screenshots_metadata(
            video_path=video_path,
            timestamps=timestamps,
            output_paths=output_paths,
            success_flags=success_flags,
            config=config,
            video_info=video_info,
        )

        # Determine overall success
        all_success = all(success_flags)
        error = None if all_success else "Some screenshots failed to extract"

        return ScreenshotResult(
            video_path=video_path,
            output_dir=output_dir,
            screenshots=screenshots,
            metadata=metadata_list,
            skipped_black_frames=skipped_black_frames,
            total_frames_analyzed=len(timestamps),
            duration_seconds=duration,
            success=all_success,
            error=error,
        )
