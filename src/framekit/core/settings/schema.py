from __future__ import annotations

import re
from typing import Any

SETTINGS_SCHEMA_VERSION = 15
ENCRYPTED_PLACEHOLDER = "<encrypted>"
SUPPORTED_UI_LOCALES = frozenset({"en", "fr", "es"})
SUPPORTED_NFO_LOCALES = frozenset({"auto", "en", "fr", "es"})
NFO_LOCALE_TO_METADATA_LANGUAGE = {
    "en": "en-US",
    "fr": "fr-FR",
    "es": "es-ES",
}
DEFAULT_UI_LOCALE = "en"
DEFAULT_NFO_LOCALE = "auto"
DEFAULT_METADATA_LANGUAGE = "en-US"
METADATA_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
# List of key substrings that should be considered sensitive.  Any key
# containing one of these parts (case-insensitive) will be redacted
# when settings are printed or logged.  This list is extended to
# include torrent announce configuration so that announce URLs and
# profiles are masked by default.  Additional entries for
# ``authorization`` and ``bearer`` mirror the diagnostics module to
# avoid exposing HTTP Authorization headers or Bearer tokens via
# settings.  See ``redact_settings()`` for usage.
SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    # Authorization/Bearer headers should be masked as well
    "authorization",
    "bearer",
    "token",
    "password",
    "secret",
    "client_secret",
    # Torrent announce configuration
    "announce",
    "announce_url",
    "announce_urls",
    "selected_announce",
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": SETTINGS_SCHEMA_VERSION,
    "general": {
        "locale": DEFAULT_UI_LOCALE,
        "default_folder": "",
        "report_output_folder": "",
    },
    "logging": {
        "max_size_mb": 100,
        "max_backups": 30,
        "compress_old_logs": True,
        "retention_days": 5,
        "cleanup_on_startup": True,
    },
    "tools": {
        "mkvmerge": "",
        "ffmpeg": "",
        "ffprobe": "",
        "mediainfo": "",
    },
    "setup": {
        "completed": False,
        "prompt_on_start": True,
    },
    "security": {
        "enabled": True,
        "vault_path": "",  # Empty means use default
        "key_storage": "keyring",  # or 'file'
        "auto_migrate": True,
        "backup_before_changes": True,
    },
    "metadata": {
        "provider": "tmdb",
        "fallback_providers": [],
        "interactive_confirmation": True,
        "cache_ttl_hours": 168,
        "language": DEFAULT_METADATA_LANGUAGE,
        "tmdb_read_access_token": "",  # nosec B105
        "tvdb_api_key": "",
        "tvdb_language": "eng",
        "anilist_enabled": True,
        "anilist_language": "en",
        "trakt_client_id": "",
        "trakt_client_secret": "",  # nosec B105
        "trakt_access_token": "",  # nosec B105
        "enabled_by_default": True,
        "prompt_missing_token_in_pipeline": True,
        "content_type_hints": {
            "anime": ["anilist", "tmdb"],
            "tv": ["tvdb", "tmdb"],
            "movie": ["tmdb"],
        },
    },
    "cache": {
        "enabled": True,
        "directory": "",
        "auto_cleanup": True,
        "cleanup_on_startup": True,
        "tmdb": {
            "enabled": True,
            "ttl_days": 7,
            "max_size_mb": 50,
        },
        "tvdb": {
            "enabled": True,
            "ttl_days": 7,
            "max_size_mb": 50,
        },
        "anilist": {
            "enabled": True,
            "ttl_days": 7,
            "max_size_mb": 50,
        },
        "trakt": {
            "enabled": True,
            "ttl_days": 7,
            "max_size_mb": 50,
        },
        "mediainfo": {
            "enabled": True,
            "ttl_days": 30,
            "max_size_mb": 50,
        },
        "release": {
            "enabled": True,
            "ttl_days": 7,
            "max_size_mb": 50,
        },
    },
    "modules": {
        "renamer": {
            "default_folder": "",
            "default_language_tag": "MULTI.VFF",
            "profile": "fr_tracker",
            "language_profiles": {
                "active": "fr_tracker",
                "profiles": {},
            },
        },
        "cleanmkv": {
            "default_folder": "",
            "output_dir_name": "Release/{release}",
            "default_preset": "multi",
            "copy_unchanged_files": True,
        },
        "nfo": {
            "default_folder": "",
            "active_template": "default",
            "locale": DEFAULT_NFO_LOCALE,
            "logo_path": "",
            "active_logo": "",
            "with_metadata": True,
            "mode": "global",
        },
        "torrent": {
            "default_folder": "",
            "announce": "",
            "announce_urls": [],
            "selected_announce": "",
            "private": True,
            "piece_length": "auto",
            "prompt_save_announce": True,
        },
        "prez": {
            "default_folder": "",
            "locale": DEFAULT_NFO_LOCALE,
            "format": "both",
            "preset": "default",
            "html_template": "aurora",
            "bbcode_template": "classic",
            "mediainfo_mode": "none",
            "include_mediainfo": False,
            "with_metadata": True,
        },
        "screenshot": {
            "default_folder": "",
            "target": "prez",
        },
        "pipeline": {
            "default_folder": "",
            "stop_on_error": False,
            "enabled_modules": ["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"],
            "with_metadata": True,
            "auto_mode": False,
            "upload_on_failure": False,
            "upload_timeout": 300,
        },
        "encoder": {
            "default_folder": "",
            "output_dir_name": "encoded",
            "preset": "",
            "ffmpeg_path": "ffmpeg",
            "ffprobe_path": "ffprobe",
        },
    },
    "upload": {
        "enabled": False,
        "auto_upload": False,
        "max_parallel_uploads": 3,  # Maximum concurrent uploads
        "trackers": [],
        "image_host": "",  # imgbb, imgbox, ptpimg, freeimage
        "image_host_api_key": "",
        "torrent_client": "",  # "qbittorrent" or empty to disable
        "torrent_client_host": "localhost",
        "torrent_client_port": 8080,
        "torrent_client_username": "",
        "torrent_client_password": "",  # nosec B105
        "torrent_client_category": "framekit",
    },
    "seedbox": {
        "default": "",
        "default_by_profile": {},
        "history_enabled": True,
        "max_concurrent_uploads": 3,
        "seedboxes": [],
    },
    "watch": {
        "enabled": False,
        "folders": [],
        "notifications": {
            "enabled": True,
            "on_watch_started": True,
            "on_start": False,
            "on_success": False,
            "on_error": True,
        },
    },
    "plugins": {
        # Third-party distributions explicitly allowed to register
        # ``framekit.modules`` entry-points at startup.
        "allowed": [],
    },
    "aliases": {
        "enabled": True,
        "max_chain_depth": 5,
        "removed": [],
        "user": {},
        "builtin": {
            "ren": {"command": "renamer", "description": "Shortcut for renamer", "enabled": True},
            "cmk": {"command": "cleanmkv", "description": "Shortcut for cleanmkv", "enabled": True},
            "nf": {"command": "nfo", "description": "Shortcut for nfo", "enabled": True},
            "md": {"command": "metadata", "description": "Shortcut for metadata", "enabled": True},
            "tor": {"command": "torrent", "description": "Shortcut for torrent", "enabled": True},
            "sc": {
                "command": "screenshot",
                "description": "Screenshot extraction",
                "enabled": True,
            },
            "pipe": {
                "command": "pipeline",
                "description": "Shortcut for pipeline",
                "enabled": True,
            },
            "bat": {"command": "batch", "description": "Shortcut for batch", "enabled": True},
            "seed": {"command": "seedbox", "description": "Shortcut for seedbox", "enabled": True},
            "pull": {
                "command": "seedbox pull",
                "description": "Shortcut for seedbox pull",
                "enabled": True,
            },
        },
    },
}
