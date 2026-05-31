"""Main encoding service for the Encoder module."""

import contextlib
import subprocess  # nosec B404
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from queue import Empty, Queue

from loguru import logger
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from swirrl.core.path_validation import PathValidationError, validate_file_path
from swirrl.core.subprocess_safe import (
    MissingToolError,
    SafeSubprocessError,
    popen_safe,
    run_safe,
)
from swirrl.core.tools import get_install_instructions
from swirrl.ui.console import console

from .models import EncodePreset, EncodeResult, ProgressInfo
from .validator import EncoderValidator


class EncoderService:
    """Service for encoding video files."""

    def __init__(
        self, preset: EncodePreset, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"
    ):
        """Initialize encoder service.

        Args:
            preset: Encoding preset to use
            ffmpeg_path: Path to ffmpeg executable
            ffprobe_path: Path to ffprobe executable

        Raises:
            RuntimeError: If FFmpeg executable is not found or not accessible
        """
        self.preset = preset
        self.ffmpeg_path = ffmpeg_path
        self.validator = EncoderValidator(ffmpeg_path, ffprobe_path)

        # Validate FFmpeg executable
        if not self._validate_ffmpeg_executable():
            install_help = get_install_instructions("ffmpeg")
            raise RuntimeError(
                f"FFmpeg executable not found or not accessible at '{ffmpeg_path}'. {install_help}"
            )

    def _validate_ffmpeg_executable(self) -> bool:
        """Check if FFmpeg executable exists and is accessible.

        Returns:
            True if FFmpeg is accessible, False otherwise
        """
        try:
            result = run_safe(
                [self.ffmpeg_path, "-version"],
                timeout=5,
                check=False,
                capture_output=True,
                log_label="ffmpeg version probe",
            )
            if result.returncode == 0:
                logger.debug(f"FFmpeg validation successful: {self.ffmpeg_path}")
                return True
            logger.error(f"FFmpeg returned non-zero exit code: {result.returncode}")
            return False
        except MissingToolError:
            logger.error(f"FFmpeg executable not found: {self.ffmpeg_path}")
            return False
        except SafeSubprocessError as exc:
            logger.error(f"FFmpeg validation failed: {exc}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating FFmpeg: {e}")
            return False

    def encode(
        self,
        input_file: Path,
        output_file: Path,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
        show_progress: bool = True,
    ) -> EncodeResult:
        """Encode a video file using the preset.

        Args:
            input_file: Path to input video file
            output_file: Path to output video file
            progress_callback: Optional callback for progress updates
            show_progress: Whether to show progress bar

        Returns:
            EncodeResult with encoding results
        """
        result = EncodeResult(success=False, input_file=input_file, output_file=output_file)
        start_time = time.time()
        input_info = self._prepare_encoding(input_file, result)
        if input_info is None:
            return result

        cmd = self.build_ffmpeg_command(input_file, output_file)
        if not self._execute_encoding(cmd, input_info, result, progress_callback, show_progress):
            return result

        encoding_time = time.time() - start_time
        result.encoding_time = encoding_time
        self._finalize_encoding_result(result, input_info, output_file, encoding_time)
        return result

    def _prepare_encoding(self, input_file: Path, result: EncodeResult):
        validation = self.validator.validate_input_file(input_file, self.preset.source_codec)
        if not validation.valid:
            for error in validation.errors:
                result.add_error(error)
            return None
        for warning in validation.warnings:
            result.add_warning(warning)
        try:
            input_info = self.validator.get_media_info(input_file)
        except Exception as exc:
            result.add_error(f"Failed to get input file info: {exc}")
            return None
        result.input_size = input_info.size
        result.duration = input_info.duration
        return input_info

    def _execute_encoding(
        self,
        cmd: list[str],
        input_info,
        result: EncodeResult,
        progress_callback: Callable[[ProgressInfo], None] | None,
        show_progress: bool,
    ) -> bool:
        try:
            if show_progress:
                self._encode_with_progress(cmd, input_info, progress_callback, result)
            else:
                self._encode_simple(cmd, result)
            return True
        except KeyboardInterrupt:
            result.add_error("Encoding interrupted by user")
            if result.output_file.exists():
                result.output_file.unlink()
            return False
        except Exception as exc:
            result.add_error(f"Encoding failed: {exc}")
            return False

    def _finalize_encoding_result(
        self, result: EncodeResult, input_info, output_file: Path, encoding_time: float
    ) -> None:
        if not output_file.exists():
            result.add_error("Output file was not created")
            return
        validation = self.validator.validate_output_file(output_file, input_info.duration)
        if not validation.valid:
            for error in validation.errors:
                result.add_error(error)
            return
        try:
            output_info = self.validator.get_media_info(output_file)
        except Exception as exc:
            result.add_error(f"Failed to get output file info: {exc}")
            return

        result.output_size = output_info.size
        if result.input_size > 0:
            result.compression_ratio = (1 - (result.output_size / result.input_size)) * 100
        if encoding_time > 0 and input_info.duration > 0:
            total_frames = input_info.duration * input_info.fps
            result.avg_fps = total_frames / encoding_time
        result.success = True

    def build_ffmpeg_command(self, input_file: Path, output_file: Path) -> list[str]:
        """Build ffmpeg command from preset with security validation.

        Args:
            input_file: Path to input file
            output_file: Path to output file

        Returns:
            List of command arguments

        Raises:
            FileNotFoundError: If input file doesn't exist
            PathValidationError: If paths are invalid or unsafe
        """
        validated_input = self._validated_input_file(input_file)
        validated_output = self._validated_output_file(output_file)
        cmd = [self.ffmpeg_path, "-i", str(validated_input)]
        self._append_video_options(cmd)
        self._append_advanced_video_options(cmd)
        self._append_audio_options(cmd)
        self._append_subtitle_options(cmd)
        self._append_metadata_options(cmd)
        self._append_chapter_options(cmd)
        cmd.extend(["-map", "0"])
        cmd.append(str(validated_output))
        logger.info(f"Built FFmpeg command: {' '.join(cmd)}")
        return cmd

    def _validated_input_file(self, input_file: Path) -> Path:
        try:
            return validate_file_path(
                input_file,
                allowed_extensions={".mkv", ".mp4", ".avi", ".mov", ".m4v"},
                max_size_mb=50000,
                must_exist=True,
            )
        except PathValidationError as exc:
            raise FileNotFoundError(f"Invalid input file: {exc}") from exc

    def _validated_output_file(self, output_file: Path) -> Path:
        try:
            return validate_file_path(
                output_file,
                allowed_extensions={".mkv", ".mp4", ".avi", ".mov", ".m4v"},
                must_exist=False,
            )
        except PathValidationError as exc:
            raise ValueError(f"Invalid output file: {exc}") from exc

    def _append_video_options(self, cmd: list[str]) -> None:
        cmd.extend(["-c:v", self.preset.encoder])
        cmd.extend(["-crf", str(self.preset.video.crf)])
        cmd.extend(["-preset", self.preset.video.preset])
        if self.preset.video.tune:
            cmd.extend(["-tune", self.preset.video.tune])
        cmd.extend(["-profile:v", self.preset.video.profile])
        cmd.extend(["-level", self.preset.video.level])
        cmd.extend(["-pix_fmt", self.preset.video.pix_fmt])

    def _append_advanced_video_options(self, cmd: list[str]) -> None:
        if self.preset.encoder == "libx265":
            self._append_x265_options(cmd)
            return
        if self.preset.encoder == "libx264":
            self._append_x264_options(cmd)

    def _append_x265_options(self, cmd: list[str]) -> None:
        if not self.preset.advanced.x265_params:
            return
        x265_params = ":".join(self.preset.advanced.x265_params)
        cmd.extend(["-x265-params", x265_params])

    def _append_x264_options(self, cmd: list[str]) -> None:
        for param in self.preset.advanced.x264_params:
            cmd.extend(["-x264-params", param])

    def _append_audio_options(self, cmd: list[str]) -> None:
        if self.preset.audio.copy:
            cmd.extend(["-c:a", "copy"])
            return
        if not self.preset.audio.codec:
            return
        cmd.extend(["-c:a", self.preset.audio.codec])
        if self.preset.audio.bitrate:
            cmd.extend(["-b:a", self.preset.audio.bitrate])

    def _append_subtitle_options(self, cmd: list[str]) -> None:
        if self.preset.subtitles.copy:
            cmd.extend(["-c:s", "copy"])

    def _append_metadata_options(self, cmd: list[str]) -> None:
        if self.preset.metadata.preserve:
            cmd.extend(["-map_metadata", "0"])

    def _append_chapter_options(self, cmd: list[str]) -> None:
        if self.preset.chapters.preserve:
            cmd.extend(["-map_chapters", "0"])

    def _encode_simple(self, cmd: list[str], result: EncodeResult) -> None:
        """Execute encoding without progress display.

        Args:
            cmd: ffmpeg command
            result: EncodeResult to update with errors
        """
        max_time = self.preset.max_encoding_time
        try:
            process = run_safe(
                cmd,
                timeout=max_time,
                check=False,
                capture_output=True,
                log_label="ffmpeg encode (simple)",
            )
        except MissingToolError as exc:
            result.add_error(f"ffmpeg not found: {exc}")
            return
        except SafeSubprocessError as exc:
            # Cleanup partial output file
            if result.output_file.exists():
                result.output_file.unlink()
            if exc.returncode is None:  # timeout
                raise RuntimeError(
                    f"FFmpeg encoding timed out after {max_time} seconds. "
                    f"Increase max_encoding_time in the preset if this file "
                    f"requires longer encoding."
                ) from exc
            result.add_error(f"ffmpeg failed: {exc.stderr or exc}")
            return

        if process.returncode != 0:
            result.add_error(f"ffmpeg failed with code {process.returncode}")
            if process.stderr:
                result.add_error(process.stderr)

    def _encode_with_progress(
        self,
        cmd: list[str],
        input_info,
        progress_callback: Callable[[ProgressInfo], None] | None,
        result: EncodeResult,
    ) -> None:
        """Execute encoding with a Rich live progress bar."""
        max_time = self.preset.max_encoding_time
        progress_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")  # noqa: SIM115
        progress_path = progress_file.name
        progress_file.close()

        try:
            self._prepare_progress_command(cmd, progress_path, result.output_file)
            process = self._start_streamed_encode_process(cmd, result)
            if process is None:
                return
            if self._process_exited_immediately(process, result):
                return

            error_queue, stderr_thread = self._start_stderr_drain_thread(process)
            encode_start_time = time.time()
            total_frames = self._total_frames(input_info)
            current_progress = ProgressInfo()
            progress = self._new_progress_display()
            with progress:
                task_id = progress.add_task(
                    "encode",
                    total=total_frames or None,
                    fps="0",
                    speed="0x",
                    bitrate="0kbps",
                )
                last_position = self._monitor_encode_progress(
                    process=process,
                    progress_path=progress_path,
                    current_progress=current_progress,
                    progress=progress,
                    task_id=task_id,
                    progress_callback=progress_callback,
                    encode_start_time=encode_start_time,
                    max_time=max_time,
                    result=result,
                )
                self._finalize_progress_file_pass(progress_path, last_position, current_progress)
                self._refresh_progress_display(progress, task_id, current_progress, total_frames)

            process.wait()
            errors = self._collect_stderr_errors(error_queue, stderr_thread)
            self._record_process_errors(process.returncode, errors, result)
        finally:
            with contextlib.suppress(Exception):
                Path(progress_path).unlink()

    def _prepare_progress_command(
        self, cmd: list[str], progress_path: str, output_file: Path
    ) -> None:
        cmd.extend(["-progress", progress_path, "-stats_period", "0.5"])
        cmd.append("-y")
        cmd.append(str(output_file))

    def _start_streamed_encode_process(self, cmd: list[str], result: EncodeResult):
        logger.debug(f"Executing FFmpeg command: {' '.join(cmd)}")
        try:
            return popen_safe(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                log_label="ffmpeg encode (streamed)",
            )
        except MissingToolError as exc:
            result.add_error(f"FFmpeg executable not found: {exc}")
        except PermissionError as exc:
            result.add_error(f"Permission denied executing FFmpeg: {exc}")
        except Exception as exc:
            result.add_error(f"Failed to start FFmpeg subprocess: {exc}")
        return None

    def _process_exited_immediately(self, process, result: EncodeResult) -> bool:
        time.sleep(0.1)
        if process.poll() is None:
            return False
        result.add_error(f"FFmpeg process terminated immediately (exit code {process.returncode})")
        return True

    def _start_stderr_drain_thread(self, process) -> tuple[Queue, threading.Thread]:
        error_queue: Queue = Queue()

        def _drain_stderr() -> None:
            try:
                if process.stderr:
                    for line in iter(process.stderr.readline, ""):
                        if line:
                            error_queue.put(line.strip())
            except Exception as exc:
                logger.warning(f"Error draining stderr: {exc}")
            finally:
                if process.stderr:
                    process.stderr.close()

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=False, name="stderr-drain")
        stderr_thread.start()
        return error_queue, stderr_thread

    def _total_frames(self, input_info) -> int:
        return int(input_info.duration * input_info.fps) if input_info.fps > 0 else 0

    def _new_progress_display(self) -> Progress:
        return Progress(
            TextColumn("[bold cyan]Encoding[/bold cyan]"),
            BarColumn(bar_width=None, complete_style="green", finished_style="bold green"),
            TextColumn("[progress.percentage]{task.percentage:>5.1f}%"),
            TextColumn("{task.completed:>7}/{task.total} frames"),
            TextColumn("[yellow]{task.fields[fps]:>6} fps[/yellow]"),
            TextColumn("[magenta]{task.fields[speed]:>6}[/magenta]"),
            TextColumn("[blue]{task.fields[bitrate]}[/blue]"),
            TimeElapsedColumn(),
            TextColumn("ETA"),
            TimeRemainingColumn(),
            console=console,
            transient=False,
            expand=True,
            refresh_per_second=4,
        )

    def _monitor_encode_progress(
        self,
        *,
        process,
        progress_path: str,
        current_progress: ProgressInfo,
        progress: Progress,
        task_id: TaskID,
        progress_callback: Callable[[ProgressInfo], None] | None,
        encode_start_time: float,
        max_time: int,
        result: EncodeResult,
    ) -> int:
        last_position = 0
        while process.poll() is None:
            last_position = self._read_progress_updates(
                progress_path, last_position, current_progress, progress_callback
            )
            self._refresh_progress_display(progress, task_id, current_progress, None)
            self._enforce_encoding_timeout(process, encode_start_time, max_time, result)
            time.sleep(0.25)
        return last_position

    def _read_progress_updates(
        self,
        progress_path: str,
        last_position: int,
        current_progress: ProgressInfo,
        progress_callback: Callable[[ProgressInfo], None] | None,
    ) -> int:
        try:
            with open(progress_path, encoding="utf-8") as progress_file:
                progress_file.seek(last_position)
                new_content = progress_file.read()
                new_position = progress_file.tell()
        except FileNotFoundError:
            return last_position
        except Exception as exc:
            logger.debug(f"Progress read error: {exc}")
            return last_position

        for line in new_content.splitlines():
            self._apply_progress_line(line.strip(), current_progress, progress_callback)
        return new_position

    def _apply_progress_line(
        self,
        line: str,
        current_progress: ProgressInfo,
        progress_callback: Callable[[ProgressInfo], None] | None,
    ) -> None:
        if not line:
            return
        parsed = self.parse_progress(line)
        if parsed is None:
            return
        self._merge_progress_update(current_progress, parsed)
        if progress_callback:
            progress_callback(current_progress)

    def _merge_progress_update(self, current: ProgressInfo, parsed: ProgressInfo) -> None:
        if parsed.frame:
            current.frame = parsed.frame
        if parsed.fps:
            current.fps = parsed.fps
        for field_name, sentinel in (
            ("speed", "0x"),
            ("bitrate", "0kbits/s"),
            ("time", "00:00:00"),
            ("size", "0kB"),
        ):
            value = getattr(parsed, field_name)
            if value and value != sentinel:
                setattr(current, field_name, value)

    def _refresh_progress_display(
        self,
        progress: Progress,
        task_id: TaskID,
        current_progress: ProgressInfo,
        total_frames: int | None,
    ) -> None:
        completed = total_frames or current_progress.frame
        progress.update(
            task_id,
            completed=completed,
            fps=f"{current_progress.fps:.1f}",
            speed=current_progress.speed,
            bitrate=current_progress.bitrate,
        )

    def _enforce_encoding_timeout(
        self,
        process,
        encode_start_time: float,
        max_time: int,
        result: EncodeResult,
    ) -> None:
        elapsed = time.time() - encode_start_time
        if elapsed <= max_time:
            return
        logger.error(f"Encoding timed out after {elapsed:.0f}s (limit: {max_time}s)")
        process.kill()
        process.wait()
        if result.output_file.exists():
            result.output_file.unlink()
        raise RuntimeError(
            f"FFmpeg encoding timed out after {max_time} seconds. "
            f"Increase max_encoding_time in the preset if this file "
            f"requires longer encoding."
        )

    def _finalize_progress_file_pass(
        self, progress_path: str, last_position: int, current_progress: ProgressInfo
    ) -> None:
        try:
            with open(progress_path, encoding="utf-8") as progress_file:
                progress_file.seek(last_position)
                for line in progress_file.read().splitlines():
                    parsed = self.parse_progress(line.strip())
                    if parsed and parsed.frame:
                        current_progress.frame = parsed.frame
        except Exception:  # nosec B110
            return

    def _collect_stderr_errors(
        self, error_queue: Queue, stderr_thread: threading.Thread
    ) -> list[str]:
        stderr_thread.join(timeout=5.0)
        if stderr_thread.is_alive():
            logger.warning("stderr drain thread did not finish in time")
        errors: list[str] = []
        try:
            while True:
                errors.append(error_queue.get_nowait())
        except Empty:
            return errors

    def _record_process_errors(
        self, returncode: int | None, errors: Sequence[str], result: EncodeResult
    ) -> None:
        if returncode == 0:
            return
        result.add_error(f"ffmpeg failed with code {returncode}")
        if errors:
            result.add_error("\n".join(errors))

    def parse_progress(self, line: str) -> ProgressInfo | None:
        """Parse one line of ffmpeg `-progress` output (key=value).

        Returns a partial ProgressInfo for the recognized key, else None.
        """
        key, value = self._split_progress_key_value(line)
        if key is None or value is None:
            return None
        if value.upper() == "N/A":
            return None
        parser = self._progress_value_parsers().get(key)
        if parser is None:
            return None
        return parser(value)

    def _split_progress_key_value(self, line: str) -> tuple[str | None, str | None]:
        if "=" not in line:
            return None, None
        key, value = line.split("=", 1)
        return key.strip(), value.strip()

    def _progress_value_parsers(self) -> dict[str, Callable[[str], ProgressInfo | None]]:
        return {
            "frame": self._parse_progress_frame,
            "fps": self._parse_progress_fps,
            "speed": self._parse_progress_speed,
            "bitrate": self._parse_progress_bitrate,
            "out_time": self._parse_progress_time,
            "total_size": self._parse_progress_size,
        }

    def _parse_progress_frame(self, value: str) -> ProgressInfo | None:
        try:
            frame_num = int(value)
        except ValueError:
            return None
        if frame_num < 0:
            return None
        return ProgressInfo(frame=frame_num)

    def _parse_progress_fps(self, value: str) -> ProgressInfo | None:
        try:
            return ProgressInfo(fps=float(value))
        except ValueError:
            return None

    def _parse_progress_speed(self, value: str) -> ProgressInfo | None:
        return ProgressInfo(speed=value)

    def _parse_progress_bitrate(self, value: str) -> ProgressInfo | None:
        return ProgressInfo(bitrate=value)

    def _parse_progress_time(self, value: str) -> ProgressInfo | None:
        return ProgressInfo(time=value.split(".")[0])

    def _parse_progress_size(self, value: str) -> ProgressInfo | None:
        try:
            size_bytes = int(value)
        except ValueError:
            return None
        if size_bytes < 0:
            return None
        return ProgressInfo(size=f"{size_bytes / 1024:.0f}kB")

    def estimate_output_size(self, input_file: Path) -> int | None:
        """Estimate output file size based on preset and input file.

        Args:
            input_file: Path to input file

        Returns:
            Estimated size in bytes, or None if estimation fails
        """
        try:
            input_info = self.validator.get_media_info(input_file)

            # Rough estimation based on CRF and codec
            # Lower CRF = higher quality = larger file
            # This is a very rough estimate
            crf_factor = (51 - self.preset.video.crf) / 51.0

            # h265 typically achieves 30-50% better compression than h264
            codec_factor = 0.6 if self.preset.target_codec == "h265" else 1.0

            estimated_size = int(input_info.size * crf_factor * codec_factor)

            return estimated_size
        except Exception:
            return None
