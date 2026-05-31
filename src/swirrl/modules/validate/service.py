"""Release validation service for pre-upload checking."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from loguru import logger

from swirrl.core.mediainfo import probe_media_file
from swirrl.core.naming import release_name_from_mkv_paths


class ValidationSeverity(Enum):
    """Severity level for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue found."""

    severity: ValidationSeverity
    category: str
    message: str
    suggestion: str = ""


@dataclass
class ValidationResult:
    """Complete validation result for a release."""

    release_path: Path
    release_name: str
    issues: list[ValidationIssue] = field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    checks_warned: int = 0

    @property
    def is_valid(self) -> bool:
        return self.checks_failed == 0

    def add_error(self, category: str, message: str, suggestion: str = "") -> None:
        self.issues.append(ValidationIssue(ValidationSeverity.ERROR, category, message, suggestion))
        self.checks_failed += 1

    def add_warning(self, category: str, message: str, suggestion: str = "") -> None:
        self.issues.append(
            ValidationIssue(ValidationSeverity.WARNING, category, message, suggestion)
        )
        self.checks_warned += 1

    def add_pass(self) -> None:
        self.checks_passed += 1


@dataclass
class ValidationRules:
    """Validation rules - can be customized per tracker."""

    require_nfo: bool = True
    require_torrent: bool = False
    allowed_video_codecs: list[str] = field(
        default_factory=lambda: ["HEVC", "AVC", "x264", "x265", "H.264", "H.265"]
    )
    allowed_audio_codecs: list[str] = field(
        default_factory=lambda: [
            "AAC",
            "AC-3",
            "E-AC-3",
            "DTS",
            "DTS-HD",
            "FLAC",
            "TrueHD",
            "Opus",
        ]
    )
    min_video_bitrate_kbps: int = 0
    max_file_size_gb: float = 0
    require_language_tags: bool = False
    allowed_containers: list[str] = field(default_factory=lambda: [".mkv", ".mp4"])
    naming_pattern: str = ""
    require_subs: bool = False
    min_resolution_width: int = 0


class ValidationService:
    """Validates a release folder against configurable rules."""

    def __init__(self, rules: ValidationRules | None = None) -> None:
        self.rules = rules or ValidationRules()

    @staticmethod
    def _normalize_codec_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def validate(self, release_path: Path) -> ValidationResult:
        """Run all validation checks on a release folder."""
        release_path = Path(release_path)
        if not release_path.exists():
            result = ValidationResult(release_path=release_path, release_name="")
            result.add_error("path", f"Release path does not exist: {release_path}")
            return result

        # Find MKV/media files
        media_files = self._find_media_files(release_path)
        release_name = ""
        if media_files:
            mkv_files = [f for f in media_files if f.suffix.lower() == ".mkv"]
            if mkv_files:
                release_name = release_name_from_mkv_paths(mkv_files) or release_path.name
            else:
                release_name = release_path.name
        else:
            release_name = release_path.name

        result = ValidationResult(release_path=release_path, release_name=release_name)

        # Run checks
        self._check_media_files(result, release_path, media_files)
        self._check_containers(result, media_files)
        self._check_nfo(result, release_path)
        self._check_video_quality(result, media_files)
        self._check_audio(result, media_files)
        self._check_subtitles(result, media_files)
        self._check_file_sizes(result, media_files)
        self._check_naming(result, release_path, media_files)

        return result

    def _find_media_files(self, path: Path) -> list[Path]:
        extensions = {".mkv", ".mp4", ".m4v", ".avi"}
        files: list[Path] = []
        for item in path.rglob("*"):
            if item.is_file() and not item.is_symlink() and item.suffix.lower() in extensions:
                files.append(item)
        return sorted(files)

    def _check_media_files(
        self,
        result: ValidationResult,
        path: Path,
        media_files: list[Path],
    ) -> None:
        if not media_files:
            result.add_error(
                "files",
                "No media files found in release folder",
                "Add MKV or MP4 files",
            )
            return
        result.add_pass()

    def _check_containers(self, result: ValidationResult, media_files: list[Path]) -> None:
        for f in media_files:
            if f.suffix.lower() not in self.rules.allowed_containers:
                result.add_error(
                    "container",
                    f"Unsupported container: {f.suffix} ({f.name})",
                    f"Allowed: {', '.join(self.rules.allowed_containers)}",
                )
                return
        result.add_pass()

    def _check_nfo(self, result: ValidationResult, path: Path) -> None:
        if not self.rules.require_nfo:
            return
        nfo_files = list(path.rglob("*.nfo"))
        if not nfo_files:
            result.add_warning("nfo", "No NFO file found", "Run `swirrl nfo` to generate one")
            return
        result.add_pass()

    def _check_video_quality(self, result: ValidationResult, media_files: list[Path]) -> None:
        for media_file in media_files:
            self._check_video_file_quality(result, media_file)

    def _check_video_file_quality(self, result: ValidationResult, media_file: Path) -> None:
        info = self._probe_video_info(result, media_file)
        if info is None:
            return
        if not self._check_video_codec(result, media_file, info.video_codec or ""):
            return
        if not self._check_video_resolution(result, media_file, info.width or 0):
            return
        if not self._check_video_bitrate(result, media_file, info.overall_bitrate or 0):
            return
        result.add_pass()

    def _probe_video_info(self, result: ValidationResult, media_file: Path):
        try:
            return probe_media_file(media_file)
        except Exception:
            logger.debug("Could not probe media file: {}", media_file.name)
            result.add_warning("video", f"Could not read media info: {media_file.name}")
            return None

    def _check_video_codec(
        self,
        result: ValidationResult,
        media_file: Path,
        video_codec: str,
    ) -> bool:
        if not self.rules.allowed_video_codecs or not video_codec:
            return True
        normalized_video = self._normalize_codec_token(video_codec)
        codec_ok = any(
            self._normalize_codec_token(allowed) in normalized_video
            for allowed in self.rules.allowed_video_codecs
        )
        if codec_ok:
            return True
        result.add_error(
            "video",
            f"Video codec '{video_codec}' not in allowed list ({media_file.name})",
            f"Allowed: {', '.join(self.rules.allowed_video_codecs)}",
        )
        return False

    def _check_video_resolution(
        self,
        result: ValidationResult,
        media_file: Path,
        width: int,
    ) -> bool:
        if not self.rules.min_resolution_width or width >= self.rules.min_resolution_width:
            return True
        result.add_error(
            "video",
            f"Resolution too low: {width}px width ({media_file.name})",
            f"Minimum required: {self.rules.min_resolution_width}px",
        )
        return False

    def _check_video_bitrate(
        self,
        result: ValidationResult,
        media_file: Path,
        bitrate: int,
    ) -> bool:
        if not self.rules.min_video_bitrate_kbps or not bitrate:
            return True
        bitrate_kbps = bitrate / 1000
        if bitrate_kbps >= self.rules.min_video_bitrate_kbps:
            return True
        result.add_warning(
            "video",
            f"Low bitrate: {bitrate_kbps:.0f} kbps ({media_file.name})",
            f"Minimum recommended: {self.rules.min_video_bitrate_kbps} kbps",
        )
        return False

    def _check_audio(self, result: ValidationResult, media_files: list[Path]) -> None:
        if not self.rules.allowed_audio_codecs:
            return
        for f in media_files:
            try:
                info = probe_media_file(f)
            except Exception:  # nosec B112
                continue
            audio_tracks = info.audio_tracks
            if not audio_tracks:
                result.add_warning("audio", f"No audio tracks found: {f.name}")
                continue
            result.add_pass()

    def _check_subtitles(self, result: ValidationResult, media_files: list[Path]) -> None:
        if not self.rules.require_subs:
            return
        for f in media_files:
            try:
                info = probe_media_file(f)
            except Exception:  # nosec B112
                continue
            sub_tracks = info.subtitle_tracks
            if not sub_tracks:
                result.add_warning(
                    "subtitles",
                    f"No subtitle tracks: {f.name}",
                    "Consider adding subtitles",
                )
                return
        result.add_pass()

    def _check_file_sizes(self, result: ValidationResult, media_files: list[Path]) -> None:
        if not self.rules.max_file_size_gb:
            return
        max_bytes = self.rules.max_file_size_gb * 1024 * 1024 * 1024
        for f in media_files:
            size = f.stat().st_size
            if size > max_bytes:
                size_gb = size / (1024 * 1024 * 1024)
                result.add_error(
                    "size",
                    f"File too large: {size_gb:.2f} GB ({f.name})",
                    f"Maximum: {self.rules.max_file_size_gb} GB",
                )
                return
        result.add_pass()

    def _check_naming(
        self,
        result: ValidationResult,
        path: Path,
        media_files: list[Path],
    ) -> None:
        if not self.rules.naming_pattern:
            return
        pattern = re.compile(self.rules.naming_pattern)
        for f in media_files:
            if not pattern.search(f.stem):
                result.add_warning(
                    "naming",
                    f"Filename may not match naming convention: {f.name}",
                    "Check tracker naming rules",
                )
                return
        result.add_pass()
