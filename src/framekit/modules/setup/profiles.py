"""Setup wizard profile definitions and defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    """Configuration for a setup profile."""

    name: str
    description: str
    questions: list[str] | str  # List of question IDs or "all"
    show_help: bool
    defaults: dict[str, Any]


# Profile definitions
BEGINNER_PROFILE = ProfileConfig(
    name="beginner",
    description="Simplified setup with sensible defaults, minimal questions",
    questions=["language", "tmdb_token"],
    show_help=False,
    defaults={
        # General
        "general.locale": "en",
        # Metadata
        "metadata.provider": "tmdb",
        "metadata.interactive_confirmation": True,
        "metadata.cache_ttl_hours": 168,
        "metadata.language": "en-US",
        "metadata.enabled_by_default": True,
        # Cache
        "cache.enabled": True,
        "cache.auto_cleanup": True,
        "cache.cleanup_on_startup": True,
        "cache.tmdb.enabled": True,
        "cache.tmdb.ttl_days": 7,
        "cache.tmdb.max_size_mb": 50,
        "cache.mediainfo.enabled": True,
        "cache.mediainfo.ttl_days": 30,
        "cache.mediainfo.max_size_mb": 50,
        "cache.release.enabled": True,
        "cache.release.ttl_days": 7,
        "cache.release.max_size_mb": 50,
        # Logging
        "logging.enabled": True,
        "logging.level": "INFO",
        "logging.rotation.enabled": True,
        "logging.rotation.max_days": 30,
        "logging.rotation.max_size_mb": 100,
        "logging.formats.console": "simple",
        "logging.formats.file": "detailed",
        "logging.performance_tracking": True,
        # Performance
        "performance.parallel_processing.enabled": True,
        "performance.parallel_processing.max_workers": 4,
        "performance.parallel_processing.batch_size": 10,
        "performance.memory.max_cache_size_mb": 500,
        "performance.memory.clear_after_operations": True,
        "performance.memory.use_streaming": True,
        "performance.cleanmkv.parallel_remux": False,
        "performance.cleanmkv.cache_track_info": True,
        "performance.cleanmkv.buffer_size_mb": 64,
        "performance.batch.parallel_releases": True,
        "performance.batch.max_concurrent": 2,
        "performance.batch.prioritize_small_files": True,
        "performance.io.buffer_size_kb": 8192,
        "performance.io.use_mmap": False,
        "performance.io.async_io": False,
        # Modules
        "modules.cleanmkv.default_preset": "multi",
        "modules.cleanmkv.copy_unchanged_files": True,
        "modules.cleanmkv.output_dir_name": "Release/{release}",
        "modules.nfo.active_template": "default",
        "modules.nfo.locale": "auto",
        "modules.nfo.with_metadata": True,
        "modules.nfo.mode": "global",
        "modules.torrent.private": True,
        "modules.torrent.piece_length": "auto",
        "modules.prez.locale": "auto",
        "modules.prez.format": "both",
        "modules.prez.preset": "default",
        "modules.prez.html_template": "aurora",
        "modules.prez.bbcode_template": "classic",
        "modules.prez.mediainfo_mode": "none",
        "modules.prez.include_mediainfo": False,
        "modules.prez.with_metadata": True,
        "modules.pipeline.stop_on_error": True,
        "modules.pipeline.enabled_modules": ["renamer", "cleanmkv", "nfo", "torrent", "prez"],
        "modules.pipeline.with_metadata": True,
        "modules.renamer.default_language_tag": "MULTI.VFF",
    },
)

ADVANCED_PROFILE = ProfileConfig(
    name="advanced",
    description="Full control over all settings, detailed configuration",
    questions="all",
    show_help=False,
    defaults={
        # Minimal defaults - user configures everything
        "general.locale": "en",
        "metadata.provider": "tmdb",
        "cache.enabled": True,
        "backup.enabled": True,
        "logging.enabled": True,
        "performance.parallel_processing.enabled": True,
    },
)

CUSTOM_PROFILE = ProfileConfig(
    name="custom",
    description="Step-by-step guided setup with explanations",
    questions="all",
    show_help=True,
    defaults={
        # Same as beginner but with help text shown
        **BEGINNER_PROFILE.defaults,
    },
)

# Profile registry
PROFILES: dict[str, ProfileConfig] = {
    "beginner": BEGINNER_PROFILE,
    "advanced": ADVANCED_PROFILE,
    "custom": CUSTOM_PROFILE,
}


def get_profile(name: str) -> ProfileConfig:
    """Get a profile by name.

    Args:
        name: Profile name (beginner, advanced, custom)

    Returns:
        ProfileConfig for the requested profile

    Raises:
        ValueError: If profile name is invalid
    """
    if name not in PROFILES:
        raise ValueError(f"Invalid profile: {name}. Must be one of: {', '.join(PROFILES.keys())}")
    return PROFILES[name]


def get_profile_names() -> list[str]:
    """Get list of available profile names.

    Returns:
        List of profile names
    """
    return list(PROFILES.keys())


def should_ask_question(profile: ProfileConfig, question_id: str) -> bool:
    """Check if a question should be asked for a profile.

    Args:
        profile: Profile configuration
        question_id: Question identifier

    Returns:
        True if question should be asked
    """
    if profile.questions == "all":
        return True
    return question_id in profile.questions


# Question definitions for wizard steps
WIZARD_QUESTIONS = {
    "language": {
        "step": 2,
        "required": True,
        "profiles": ["beginner", "advanced", "custom"],
    },
    "tmdb_token": {
        "step": 3,
        "required": True,
        "profiles": ["beginner", "advanced", "custom"],
    },
    "torrent_announce": {
        "step": 4,
        "required": False,
        "profiles": ["advanced", "custom"],
    },
    "presets": {
        "step": 5,
        "required": False,
        "profiles": ["advanced", "custom"],
    },
    "performance": {
        "step": 6,
        "required": False,
        "profiles": ["advanced", "custom"],
    },
    "security": {
        "step": 7,
        "required": False,
        "profiles": ["advanced", "custom"],
    },
}
