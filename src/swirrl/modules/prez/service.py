from __future__ import annotations

# ruff: noqa: I001

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from html import escape
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any, cast

# babel is optional; format_date is only used to format literal dates. If babel is
# unavailable, a fallback is provided.
try:
    from babel.dates import format_date  # type: ignore[import]
except ImportError:
    format_date = None  # type: ignore[assignment]
from jinja2 import Environment, PackageLoader, select_autoescape

try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename fallback when pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(filename: str, replacement_text: str = "_") -> str:
        """Sanitize a filename by replacing characters illegal on most filesystems.

        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


try:
    from pymediainfo import MediaInfo  # type: ignore[import]
except ImportError:
    MediaInfo = None  # type: ignore[assignment]

from swirrl.core.i18n import temporary_locale, tr
from swirrl.core.models.nfo import EpisodeNfoData, ReleaseNfoData, TrackNfoData
from swirrl.core.tools import ToolRegistry
from swirrl.core.reporting import OperationReport
from swirrl.modules.nfo.builder import build_release_nfo
from swirrl.modules.nfo.formatting import format_bytes_human, format_duration_ms_human
from swirrl.modules.nfo.scanner import scan_nfo_folder
from swirrl.modules.prez.models import PrezData, PrezField, PrezTrack, PrezTrackGroup
from swirrl.modules.prez.theme_loader import get_html_theme_css

SCREENSHOT_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SCREENSHOT_DIR_NAMES = {"screens", "screen", "screenshots", "screenshot", "captures"}
POSTER_FILENAMES = {
    "poster.jpg",
    "poster.jpeg",
    "poster.png",
    "poster.webp",
    "cover.jpg",
    "cover.jpeg",
    "cover.png",
    "cover.webp",
    "folder.jpg",
    "folder.jpeg",
    "folder.png",
    "folder.webp",
}
MEDIAINFO_FILENAMES = {
    "mediainfo.txt",
    "media_info.txt",
    "media-info.txt",
    "mediainfo.log",
}
PREZ_LOCALES = frozenset({"en", "fr", "es"})
# New Template System: 10 designs × 14 colors = 140 templates
HTML_TEMPLATE_NAMES = (
    # Cinematic (14 variants)
    "cinematic_dark",
    "cinematic_forest",
    "cinematic_sunset",
    "cinematic_ocean",
    "cinematic_sepia",
    "cinematic_rainbow",
    "cinematic_midnight",
    "cinematic_cherry",
    "cinematic_lavender",
    "cinematic_mint",
    "cinematic_amber",
    "cinematic_slate",
    "cinematic_coral",
    "cinematic_teal",
    # Magazine (14 variants)
    "magazine_dark",
    "magazine_forest",
    "magazine_sunset",
    "magazine_ocean",
    "magazine_sepia",
    "magazine_rainbow",
    "magazine_midnight",
    "magazine_cherry",
    "magazine_lavender",
    "magazine_mint",
    "magazine_amber",
    "magazine_slate",
    "magazine_coral",
    "magazine_teal",
    # Minimal (14 variants)
    "minimal_dark",
    "minimal_forest",
    "minimal_sunset",
    "minimal_ocean",
    "minimal_sepia",
    "minimal_rainbow",
    "minimal_midnight",
    "minimal_cherry",
    "minimal_lavender",
    "minimal_mint",
    "minimal_amber",
    "minimal_slate",
    "minimal_coral",
    "minimal_teal",
    # Card (14 variants)
    "card_dark",
    "card_forest",
    "card_sunset",
    "card_ocean",
    "card_sepia",
    "card_rainbow",
    "card_midnight",
    "card_cherry",
    "card_lavender",
    "card_mint",
    "card_amber",
    "card_slate",
    "card_coral",
    "card_teal",
    # Timeline (14 variants)
    "timeline_dark",
    "timeline_forest",
    "timeline_sunset",
    "timeline_ocean",
    "timeline_sepia",
    "timeline_rainbow",
    "timeline_midnight",
    "timeline_cherry",
    "timeline_lavender",
    "timeline_mint",
    "timeline_amber",
    "timeline_slate",
    "timeline_coral",
    "timeline_teal",
    # Glassmorphism (14 variants)
    "glassmorphism_dark",
    "glassmorphism_forest",
    "glassmorphism_sunset",
    "glassmorphism_ocean",
    "glassmorphism_sepia",
    "glassmorphism_rainbow",
    "glassmorphism_midnight",
    "glassmorphism_cherry",
    "glassmorphism_lavender",
    "glassmorphism_mint",
    "glassmorphism_amber",
    "glassmorphism_slate",
    "glassmorphism_coral",
    "glassmorphism_teal",
    # Brutalist (14 variants)
    "brutalist_dark",
    "brutalist_forest",
    "brutalist_sunset",
    "brutalist_ocean",
    "brutalist_sepia",
    "brutalist_rainbow",
    "brutalist_midnight",
    "brutalist_cherry",
    "brutalist_lavender",
    "brutalist_mint",
    "brutalist_amber",
    "brutalist_slate",
    "brutalist_coral",
    "brutalist_teal",
    # Neon Cyberpunk (14 variants)
    "neon_cyberpunk_dark",
    "neon_cyberpunk_forest",
    "neon_cyberpunk_sunset",
    "neon_cyberpunk_ocean",
    "neon_cyberpunk_sepia",
    "neon_cyberpunk_rainbow",
    "neon_cyberpunk_midnight",
    "neon_cyberpunk_cherry",
    "neon_cyberpunk_lavender",
    "neon_cyberpunk_mint",
    "neon_cyberpunk_amber",
    "neon_cyberpunk_slate",
    "neon_cyberpunk_coral",
    "neon_cyberpunk_teal",
    # Vintage Retro (14 variants)
    "vintage_retro_dark",
    "vintage_retro_forest",
    "vintage_retro_sunset",
    "vintage_retro_ocean",
    "vintage_retro_sepia",
    "vintage_retro_rainbow",
    "vintage_retro_midnight",
    "vintage_retro_cherry",
    "vintage_retro_lavender",
    "vintage_retro_mint",
    "vintage_retro_amber",
    "vintage_retro_slate",
    "vintage_retro_coral",
    "vintage_retro_teal",
    # Neumorphism (14 variants)
    "neumorphism_dark",
    "neumorphism_forest",
    "neumorphism_sunset",
    "neumorphism_ocean",
    "neumorphism_sepia",
    "neumorphism_rainbow",
    "neumorphism_midnight",
    "neumorphism_cherry",
    "neumorphism_lavender",
    "neumorphism_mint",
    "neumorphism_amber",
    "neumorphism_slate",
    "neumorphism_coral",
    "neumorphism_teal",
)
BBCODE_TEMPLATE_NAMES = (
    "classic",
    "compact",
    "detailed",
    "technical",
    "cinematic",
    "tracker",
    "spoiler",
    "boxed",
)
# Aliases for backward compatibility and convenience
HTML_STYLE_ALIASES = {
    "default": "minimal_dark",
    "premium": "cinematic_dark",
    "tracker": "minimal_dark",
    # Old template names mapped to new equivalents
    "aurora": "minimal_blue",
    "emerald": "minimal_green",
    "midnight": "minimal_dark",
    "cinema": "cinematic_dark",
    "poster": "card_dark",
    "minimal": "minimal_dark",
    "neon": "neon_cyberpunk_dark",
    "mono": "minimal_light",
    "editorial": "magazine_dark",
    "lobby": "magazine_dark",
    "vertical": "timeline_dark",
    "terminal": "minimal_dark",
    "magazine": "magazine_dark",
    "split": "card_dark",
    "archive": "magazine_dark",
    "poster_focus": "card_dark",
    "timeline": "timeline_dark",
    "timeline_noir": "timeline_noir",
    "timeline_amber": "timeline_amber",
    "timeline_ocean": "timeline_ocean",
}
BBCODE_STYLE_ALIASES = {"default": "classic", "premium": "cinematic"}
# Updated presets with new template names
PREZ_PRESETS: dict[str, dict[str, str]] = {
    "default": {
        "format": "both",
        "html_template": "minimal_dark",
        "bbcode_template": "classic",
        "mediainfo_mode": "none",
        "detail_level": "standard",
        "show_tmdb": "true",
        "show_mediainfo": "false",
    },
    "tracker": {
        "format": "bbcode",
        "html_template": "magazine_dark",
        "bbcode_template": "tracker",
        "mediainfo_mode": "spoiler",
        "detail_level": "tracker",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "compact": {
        "format": "bbcode",
        "html_template": "minimal_light",
        "bbcode_template": "compact",
        "mediainfo_mode": "none",
        "detail_level": "compact",
        "show_tmdb": "true",
        "show_mediainfo": "false",
    },
    "detailed": {
        "format": "both",
        "html_template": "magazine_dark",
        "bbcode_template": "detailed",
        "mediainfo_mode": "spoiler",
        "detail_level": "detailed",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "technical": {
        "format": "both",
        "html_template": "minimal_dark",
        "bbcode_template": "technical",
        "mediainfo_mode": "spoiler",
        "detail_level": "technical",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "premium": {
        "format": "both",
        "html_template": "cinematic_dark",
        "bbcode_template": "cinematic",
        "mediainfo_mode": "spoiler",
        "detail_level": "premium",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "timeline": {
        "format": "both",
        "html_template": "timeline_dark",
        "bbcode_template": "detailed",
        "mediainfo_mode": "spoiler",
        "detail_level": "timeline",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
}
MEDIAINFO_MODES = frozenset({"none", "spoiler", "only"})

_FLAG_BY_LANGUAGE = {
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "en": "gb",
    "eng": "gb",
    "english": "gb",
    "anglais": "gb",
    "en-gb": "gb",
    "en-us": "us",
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "espagnol": "es",
    "espanol": "es",
    "español": "es",
    "de": "de",
    "ger": "de",
    "deu": "de",
    "german": "de",
    "allemand": "de",
    "it": "it",
    "ita": "it",
    "italian": "it",
    "italien": "it",
    "pt": "pt",
    "por": "pt",
    "portuguese": "pt",
    "portugais": "pt",
    "pt-br": "br",
    "ja": "jp",
    "jpn": "jp",
    "japanese": "jp",
    "japonais": "jp",
    "ko": "kr",
    "kor": "kr",
    "korean": "kr",
    "coreen": "kr",
    "coréen": "kr",
    "zh": "cn",
    "chi": "cn",
    "zho": "cn",
    "chinese": "cn",
    "chinois": "cn",
    "nl": "nl",
    "dut": "nl",
    "nld": "nl",
    "dutch": "nl",
    "neerlandais": "nl",
    "néerlandais": "nl",
    "pl": "pl",
    "pol": "pl",
    "polish": "pl",
    "polonais": "pl",
    "ru": "ru",
    "rus": "ru",
    "russian": "ru",
    "russe": "ru",
    "uk": "ua",
    "ukr": "ua",
    "ukrainian": "ua",
    "ukrainien": "ua",
}


@dataclass(frozen=True, slots=True)
class PrezBuildOptions:
    """Prez build options."""

    formats: tuple[str, ...] = ("html", "bbcode")
    output_dir: Path | None = None
    metadata_context: dict | None = None
    locale: str | None = None
    include_mediainfo: bool = False
    mediainfo_mode: str = "none"
    mediainfo_text: str | None = None
    screenshots: tuple[str, ...] = ()
    html_template: str | None = None
    bbcode_template: str | None = None
    preset: str = "default"
    release: ReleaseNfoData | None = None
    poster_url: str | None = None
    banner_audio: str = ""
    banner_information: str = ""
    banner_metadata: str = ""
    banner_release: str = ""
    banner_subtitles: str = ""
    banner_synopsis: str = ""
    banner_technical: str = ""


@dataclass(frozen=True, slots=True)
class PrezBuildResult:
    """Result of prez build."""

    release: ReleaseNfoData
    outputs: tuple[Path, ...]


def available_html_templates() -> tuple[str, ...]:
    """Return packaged HTML templates discovered from resource files."""
    return _discover_template_names("html", fallback=HTML_TEMPLATE_NAMES)


def available_bbcode_templates() -> tuple[str, ...]:
    """Return packaged BBCode templates discovered from resource files."""
    return _discover_template_names("bbcode", fallback=BBCODE_TEMPLATE_NAMES)


def available_prez_presets() -> tuple[str, ...]:
    """Handle available prez presets."""
    return tuple(PREZ_PRESETS)


# New template descriptions (10 designs × 14 colors = 140 templates)
HTML_TEMPLATE_DESCRIPTIONS = {
    # Cinematic (14 colors)
    "cinematic_dark": "Movie-style horizontal layout - Dark",
    "cinematic_forest": "Movie-style horizontal layout - Forest 🌲",
    "cinematic_sunset": "Movie-style horizontal layout - Sunset 🌅",
    "cinematic_ocean": "Movie-style horizontal layout - Ocean 🌊",
    "cinematic_sepia": "Movie-style horizontal layout - Sepia 🟤",
    "cinematic_rainbow": "Movie-style horizontal layout - Rainbow 🌈",
    "cinematic_midnight": "Movie-style horizontal layout - Midnight 🌙",
    "cinematic_cherry": "Movie-style horizontal layout - Cherry 🍒",
    "cinematic_lavender": "Movie-style horizontal layout - Lavender 💜",
    "cinematic_mint": "Movie-style horizontal layout - Mint 🌿",
    "cinematic_amber": "Movie-style horizontal layout - Amber 🟠",
    "cinematic_slate": "Movie-style horizontal layout - Slate 🪨",
    "cinematic_coral": "Movie-style horizontal layout - Coral 🪸",
    "cinematic_teal": "Movie-style horizontal layout - Teal 🦚",
    # Magazine (14 colors)
    "magazine_dark": "Editorial multi-column layout - Dark",
    "magazine_forest": "Editorial multi-column layout - Forest 🌲",
    "magazine_sunset": "Editorial multi-column layout - Sunset 🌅",
    "magazine_ocean": "Editorial multi-column layout - Ocean 🌊",
    "magazine_sepia": "Editorial multi-column layout - Sepia 🟤",
    "magazine_rainbow": "Editorial multi-column layout - Rainbow 🌈",
    "magazine_midnight": "Editorial multi-column layout - Midnight 🌙",
    "magazine_cherry": "Editorial multi-column layout - Cherry 🍒",
    "magazine_lavender": "Editorial multi-column layout - Lavender 💜",
    "magazine_mint": "Editorial multi-column layout - Mint 🌿",
    "magazine_amber": "Editorial multi-column layout - Amber 🟠",
    "magazine_slate": "Editorial multi-column layout - Slate 🪨",
    "magazine_coral": "Editorial multi-column layout - Coral 🪸",
    "magazine_teal": "Editorial multi-column layout - Teal 🦚",
    # Minimal (14 colors)
    "minimal_dark": "Clean and spacious design - Dark",
    "minimal_forest": "Clean and spacious design - Forest 🌲",
    "minimal_sunset": "Clean and spacious design - Sunset 🌅",
    "minimal_ocean": "Clean and spacious design - Ocean 🌊",
    "minimal_sepia": "Clean and spacious design - Sepia 🟤",
    "minimal_rainbow": "Clean and spacious design - Rainbow 🌈",
    "minimal_midnight": "Clean and spacious design - Midnight 🌙",
    "minimal_cherry": "Clean and spacious design - Cherry 🍒",
    "minimal_lavender": "Clean and spacious design - Lavender 💜",
    "minimal_mint": "Clean and spacious design - Mint 🌿",
    "minimal_amber": "Clean and spacious design - Amber 🟠",
    "minimal_slate": "Clean and spacious design - Slate 🪨",
    "minimal_coral": "Clean and spacious design - Coral 🪸",
    "minimal_teal": "Clean and spacious design - Teal 🦚",
    # Card (14 colors)
    "card_dark": "Grid-based card layout - Dark",
    "card_forest": "Grid-based card layout - Forest 🌲",
    "card_sunset": "Grid-based card layout - Sunset 🌅",
    "card_ocean": "Grid-based card layout - Ocean 🌊",
    "card_sepia": "Grid-based card layout - Sepia 🟤",
    "card_rainbow": "Grid-based card layout - Rainbow 🌈",
    "card_midnight": "Grid-based card layout - Midnight 🌙",
    "card_cherry": "Grid-based card layout - Cherry 🍒",
    "card_lavender": "Grid-based card layout - Lavender 💜",
    "card_mint": "Grid-based card layout - Mint 🌿",
    "card_amber": "Grid-based card layout - Amber 🟠",
    "card_slate": "Grid-based card layout - Slate 🪨",
    "card_coral": "Grid-based card layout - Coral 🪸",
    "card_teal": "Grid-based card layout - Teal 🦚",
    # Timeline (14 colors)
    "timeline_dark": "Chronological vertical layout - Dark",
    "timeline_forest": "Chronological vertical layout - Forest 🌲",
    "timeline_sunset": "Chronological vertical layout - Sunset 🌅",
    "timeline_ocean": "Chronological vertical layout - Ocean 🌊",
    "timeline_sepia": "Chronological vertical layout - Sepia 🟤",
    "timeline_rainbow": "Chronological vertical layout - Rainbow 🌈",
    "timeline_midnight": "Chronological vertical layout - Midnight 🌙",
    "timeline_cherry": "Chronological vertical layout - Cherry 🍒",
    "timeline_lavender": "Chronological vertical layout - Lavender 💜",
    "timeline_mint": "Chronological vertical layout - Mint 🌿",
    "timeline_amber": "Chronological vertical layout - Amber 🟠",
    "timeline_slate": "Chronological vertical layout - Slate 🪨",
    "timeline_coral": "Chronological vertical layout - Coral 🪸",
    "timeline_teal": "Chronological vertical layout - Teal 🦚",
    # Glassmorphism (14 colors)
    "glassmorphism_dark": "Frosted glass effects - Dark",
    "glassmorphism_forest": "Frosted glass effects - Forest 🌲",
    "glassmorphism_sunset": "Frosted glass effects - Sunset 🌅",
    "glassmorphism_ocean": "Frosted glass effects - Ocean 🌊",
    "glassmorphism_sepia": "Frosted glass effects - Sepia 🟤",
    "glassmorphism_rainbow": "Frosted glass effects - Rainbow 🌈",
    "glassmorphism_midnight": "Frosted glass effects - Midnight 🌙",
    "glassmorphism_cherry": "Frosted glass effects - Cherry 🍒",
    "glassmorphism_lavender": "Frosted glass effects - Lavender 💜",
    "glassmorphism_mint": "Frosted glass effects - Mint 🌿",
    "glassmorphism_amber": "Frosted glass effects - Amber 🟠",
    "glassmorphism_slate": "Frosted glass effects - Slate 🪨",
    "glassmorphism_coral": "Frosted glass effects - Coral 🪸",
    "glassmorphism_teal": "Frosted glass effects - Teal 🦚",
    # Brutalist (14 colors)
    "brutalist_dark": "Raw asymmetric design - Dark",
    "brutalist_forest": "Raw asymmetric design - Forest 🌲",
    "brutalist_sunset": "Raw asymmetric design - Sunset 🌅",
    "brutalist_ocean": "Raw asymmetric design - Ocean 🌊",
    "brutalist_sepia": "Raw asymmetric design - Sepia 🟤",
    "brutalist_rainbow": "Raw asymmetric design - Rainbow 🌈",
    "brutalist_midnight": "Raw asymmetric design - Midnight 🌙",
    "brutalist_cherry": "Raw asymmetric design - Cherry 🍒",
    "brutalist_lavender": "Raw asymmetric design - Lavender 💜",
    "brutalist_mint": "Raw asymmetric design - Mint 🌿",
    "brutalist_amber": "Raw asymmetric design - Amber 🟠",
    "brutalist_slate": "Raw asymmetric design - Slate 🪨",
    "brutalist_coral": "Raw asymmetric design - Coral 🪸",
    "brutalist_teal": "Raw asymmetric design - Teal 🦚",
    # Neon Cyberpunk (14 colors)
    "neon_cyberpunk_dark": "Glowing futuristic style - Dark",
    "neon_cyberpunk_forest": "Glowing futuristic style - Forest 🌲",
    "neon_cyberpunk_sunset": "Glowing futuristic style - Sunset 🌅",
    "neon_cyberpunk_ocean": "Glowing futuristic style - Ocean 🌊",
    "neon_cyberpunk_sepia": "Glowing futuristic style - Sepia 🟤",
    "neon_cyberpunk_rainbow": "Glowing futuristic style - Rainbow 🌈",
    "neon_cyberpunk_midnight": "Glowing futuristic style - Midnight 🌙",
    "neon_cyberpunk_cherry": "Glowing futuristic style - Cherry 🍒",
    "neon_cyberpunk_lavender": "Glowing futuristic style - Lavender 💜",
    "neon_cyberpunk_mint": "Glowing futuristic style - Mint 🌿",
    "neon_cyberpunk_amber": "Glowing futuristic style - Amber 🟠",
    "neon_cyberpunk_slate": "Glowing futuristic style - Slate 🪨",
    "neon_cyberpunk_coral": "Glowing futuristic style - Coral 🪸",
    "neon_cyberpunk_teal": "Glowing futuristic style - Teal 🦚",
    # Vintage Retro (14 colors)
    "vintage_retro_dark": "80s/90s pastel aesthetic - Dark",
    "vintage_retro_forest": "80s/90s pastel aesthetic - Forest 🌲",
    "vintage_retro_sunset": "80s/90s pastel aesthetic - Sunset 🌅",
    "vintage_retro_ocean": "80s/90s pastel aesthetic - Ocean 🌊",
    "vintage_retro_sepia": "80s/90s pastel aesthetic - Sepia 🟤",
    "vintage_retro_rainbow": "80s/90s pastel aesthetic - Rainbow 🌈",
    "vintage_retro_midnight": "80s/90s pastel aesthetic - Midnight 🌙",
    "vintage_retro_cherry": "80s/90s pastel aesthetic - Cherry 🍒",
    "vintage_retro_lavender": "80s/90s pastel aesthetic - Lavender 💜",
    "vintage_retro_mint": "80s/90s pastel aesthetic - Mint 🌿",
    "vintage_retro_amber": "80s/90s pastel aesthetic - Amber 🟠",
    "vintage_retro_slate": "80s/90s pastel aesthetic - Slate 🪨",
    "vintage_retro_coral": "80s/90s pastel aesthetic - Coral 🪸",
    "vintage_retro_teal": "80s/90s pastel aesthetic - Teal 🦚",
    # Neumorphism (14 colors)
    "neumorphism_dark": "Soft 3D relief design - Dark",
    "neumorphism_forest": "Soft 3D relief design - Forest 🌲",
    "neumorphism_sunset": "Soft 3D relief design - Sunset 🌅",
    "neumorphism_ocean": "Soft 3D relief design - Ocean 🌊",
    "neumorphism_sepia": "Soft 3D relief design - Sepia 🟤",
    "neumorphism_rainbow": "Soft 3D relief design - Rainbow 🌈",
    "neumorphism_midnight": "Soft 3D relief design - Midnight 🌙",
    "neumorphism_cherry": "Soft 3D relief design - Cherry 🍒",
    "neumorphism_lavender": "Soft 3D relief design - Lavender 💜",
    "neumorphism_mint": "Soft 3D relief design - Mint 🌿",
    "neumorphism_amber": "Soft 3D relief design - Amber 🟠",
    "neumorphism_slate": "Soft 3D relief design - Slate 🪨",
    "neumorphism_coral": "Soft 3D relief design - Coral 🪸",
    "neumorphism_teal": "Soft 3D relief design - Teal 🦚",
}

BBCODE_TEMPLATE_DESCRIPTIONS = {
    "classic": "Readable general-purpose BBCode.",
    "compact": "Short tracker-friendly BBCode.",
    "detailed": "Detailed BBCode with full release sections.",
    "technical": "Technical BBCode emphasizing codecs and MediaInfo.",
    "cinematic": "More styled cinematic BBCode.",
    "tracker": "Strict tracker-oriented BBCode.",
    "spoiler": "BBCode using spoiler blocks for dense details.",
    "boxed": "Boxed BBCode organization for visual separation.",
}

# New template categories (10 designs × 14 colors = 140 templates)
HTML_TEMPLATE_CATEGORIES = {
    # Cinematic (14 colors)
    "cinematic_dark": "Cinematic",
    "cinematic_forest": "Cinematic",
    "cinematic_sunset": "Cinematic",
    "cinematic_ocean": "Cinematic",
    "cinematic_sepia": "Cinematic",
    "cinematic_rainbow": "Cinematic",
    "cinematic_midnight": "Cinematic",
    "cinematic_cherry": "Cinematic",
    "cinematic_lavender": "Cinematic",
    "cinematic_mint": "Cinematic",
    "cinematic_amber": "Cinematic",
    "cinematic_slate": "Cinematic",
    "cinematic_coral": "Cinematic",
    "cinematic_teal": "Cinematic",
    # Magazine (14 colors)
    "magazine_dark": "Magazine",
    "magazine_forest": "Magazine",
    "magazine_sunset": "Magazine",
    "magazine_ocean": "Magazine",
    "magazine_sepia": "Magazine",
    "magazine_rainbow": "Magazine",
    "magazine_midnight": "Magazine",
    "magazine_cherry": "Magazine",
    "magazine_lavender": "Magazine",
    "magazine_mint": "Magazine",
    "magazine_amber": "Magazine",
    "magazine_slate": "Magazine",
    "magazine_coral": "Magazine",
    "magazine_teal": "Magazine",
    # Minimal (14 colors)
    "minimal_dark": "Minimal",
    "minimal_forest": "Minimal",
    "minimal_sunset": "Minimal",
    "minimal_ocean": "Minimal",
    "minimal_sepia": "Minimal",
    "minimal_rainbow": "Minimal",
    "minimal_midnight": "Minimal",
    "minimal_cherry": "Minimal",
    "minimal_lavender": "Minimal",
    "minimal_mint": "Minimal",
    "minimal_amber": "Minimal",
    "minimal_slate": "Minimal",
    "minimal_coral": "Minimal",
    "minimal_teal": "Minimal",
    # Card (14 colors)
    "card_dark": "Card",
    "card_forest": "Card",
    "card_sunset": "Card",
    "card_ocean": "Card",
    "card_sepia": "Card",
    "card_rainbow": "Card",
    "card_midnight": "Card",
    "card_cherry": "Card",
    "card_lavender": "Card",
    "card_mint": "Card",
    "card_amber": "Card",
    "card_slate": "Card",
    "card_coral": "Card",
    "card_teal": "Card",
    # Timeline (14 colors)
    "timeline_dark": "Timeline",
    "timeline_forest": "Timeline",
    "timeline_sunset": "Timeline",
    "timeline_ocean": "Timeline",
    "timeline_sepia": "Timeline",
    "timeline_rainbow": "Timeline",
    "timeline_midnight": "Timeline",
    "timeline_cherry": "Timeline",
    "timeline_lavender": "Timeline",
    "timeline_mint": "Timeline",
    "timeline_amber": "Timeline",
    "timeline_slate": "Timeline",
    "timeline_coral": "Timeline",
    "timeline_teal": "Timeline",
    # Glassmorphism (14 colors)
    "glassmorphism_dark": "Glassmorphism",
    "glassmorphism_forest": "Glassmorphism",
    "glassmorphism_sunset": "Glassmorphism",
    "glassmorphism_ocean": "Glassmorphism",
    "glassmorphism_sepia": "Glassmorphism",
    "glassmorphism_rainbow": "Glassmorphism",
    "glassmorphism_midnight": "Glassmorphism",
    "glassmorphism_cherry": "Glassmorphism",
    "glassmorphism_lavender": "Glassmorphism",
    "glassmorphism_mint": "Glassmorphism",
    "glassmorphism_amber": "Glassmorphism",
    "glassmorphism_slate": "Glassmorphism",
    "glassmorphism_coral": "Glassmorphism",
    "glassmorphism_teal": "Glassmorphism",
    # Brutalist (14 colors)
    "brutalist_dark": "Brutalist",
    "brutalist_forest": "Brutalist",
    "brutalist_sunset": "Brutalist",
    "brutalist_ocean": "Brutalist",
    "brutalist_sepia": "Brutalist",
    "brutalist_rainbow": "Brutalist",
    "brutalist_midnight": "Brutalist",
    "brutalist_cherry": "Brutalist",
    "brutalist_lavender": "Brutalist",
    "brutalist_mint": "Brutalist",
    "brutalist_amber": "Brutalist",
    "brutalist_slate": "Brutalist",
    "brutalist_coral": "Brutalist",
    "brutalist_teal": "Brutalist",
    # Neon Cyberpunk (14 colors)
    "neon_cyberpunk_dark": "Neon Cyberpunk",
    "neon_cyberpunk_forest": "Neon Cyberpunk",
    "neon_cyberpunk_sunset": "Neon Cyberpunk",
    "neon_cyberpunk_ocean": "Neon Cyberpunk",
    "neon_cyberpunk_sepia": "Neon Cyberpunk",
    "neon_cyberpunk_rainbow": "Neon Cyberpunk",
    "neon_cyberpunk_midnight": "Neon Cyberpunk",
    "neon_cyberpunk_cherry": "Neon Cyberpunk",
    "neon_cyberpunk_lavender": "Neon Cyberpunk",
    "neon_cyberpunk_mint": "Neon Cyberpunk",
    "neon_cyberpunk_amber": "Neon Cyberpunk",
    "neon_cyberpunk_slate": "Neon Cyberpunk",
    "neon_cyberpunk_coral": "Neon Cyberpunk",
    "neon_cyberpunk_teal": "Neon Cyberpunk",
    # Vintage Retro (14 colors)
    "vintage_retro_dark": "Vintage Retro",
    "vintage_retro_forest": "Vintage Retro",
    "vintage_retro_sunset": "Vintage Retro",
    "vintage_retro_ocean": "Vintage Retro",
    "vintage_retro_sepia": "Vintage Retro",
    "vintage_retro_rainbow": "Vintage Retro",
    "vintage_retro_midnight": "Vintage Retro",
    "vintage_retro_cherry": "Vintage Retro",
    "vintage_retro_lavender": "Vintage Retro",
    "vintage_retro_mint": "Vintage Retro",
    "vintage_retro_amber": "Vintage Retro",
    "vintage_retro_slate": "Vintage Retro",
    "vintage_retro_coral": "Vintage Retro",
    "vintage_retro_teal": "Vintage Retro",
    # Neumorphism (14 colors)
    "neumorphism_dark": "Neumorphism",
    "neumorphism_forest": "Neumorphism",
    "neumorphism_sunset": "Neumorphism",
    "neumorphism_ocean": "Neumorphism",
    "neumorphism_sepia": "Neumorphism",
    "neumorphism_rainbow": "Neumorphism",
    "neumorphism_midnight": "Neumorphism",
    "neumorphism_cherry": "Neumorphism",
    "neumorphism_lavender": "Neumorphism",
    "neumorphism_mint": "Neumorphism",
    "neumorphism_amber": "Neumorphism",
    "neumorphism_slate": "Neumorphism",
    "neumorphism_coral": "Neumorphism",
    "neumorphism_teal": "Neumorphism",
}

BBCODE_TEMPLATE_CATEGORIES = {
    "classic": "Classic",
    "compact": "Tracker",
    "detailed": "Classic",
    "technical": "Tracker",
    "cinematic": "Styled",
    "tracker": "Tracker",
    "spoiler": "Styled",
    "boxed": "Styled",
}

HTML_TEMPLATE_FAMILY_LABELS = {
    "cinematic": "Cinematic",
    "magazine": "Magazine",
    "minimal": "Minimal",
    "card": "Card",
    "timeline": "Timeline",
    "glassmorphism": "Glassmorphism",
    "brutalist": "Brutalist",
    "neon_cyberpunk": "Neon Cyberpunk",
    "vintage_retro": "Vintage Retro",
    "neumorphism": "Neumorphism",
}


def _template_name_from_filename(filename: str) -> str | None:
    if not filename.endswith(".jinja2"):
        return None
    stem = filename.removesuffix(".jinja2")
    base, separator, locale = stem.rpartition(".")
    if separator and locale in PREZ_LOCALES:
        return base
    return stem


def _discover_template_names(kind: str, *, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if kind == "html":
        resource_dir = "templates/prez/html/generated"
    elif kind == "bbcode":
        resource_dir = "templates/prez/bbcode"
    else:
        return fallback

    try:
        root = importlib_resources.files("swirrl").joinpath(resource_dir)
        discovered = {
            template_name
            for item in root.iterdir()
            if item.is_file()
            for template_name in [_template_name_from_filename(item.name)]
            if template_name
        }
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        return fallback

    return tuple(sorted(discovered)) or fallback


def _html_family_label(template_name: str) -> str | None:
    for family, label in sorted(
        HTML_TEMPLATE_FAMILY_LABELS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if template_name.startswith(f"{family}_"):
            return label
    return None


def describe_html_template(name: str) -> str:
    """Handle describe html template."""
    normalized = _normalize_template_name(name, kind="html")
    description = HTML_TEMPLATE_DESCRIPTIONS.get(normalized)
    if description:
        return description
    family_label = _html_family_label(normalized)
    if family_label is None:
        return normalized
    color = normalized.rsplit("_", 1)[-1].replace("_", " ").title()
    return f"{family_label} template - {color}"


def describe_bbcode_template(name: str) -> str:
    """Handle describe bbcode template."""
    normalized = _normalize_template_name(name, kind="bbcode")
    return BBCODE_TEMPLATE_DESCRIPTIONS.get(normalized, normalized)


def template_category(name: str, *, kind: str) -> str:
    """Handle template category."""
    if kind == "html":
        normalized = _normalize_template_name(name, kind=kind)
        return HTML_TEMPLATE_CATEGORIES.get(normalized) or _html_family_label(normalized) or "Other"
    return BBCODE_TEMPLATE_CATEGORIES.get(_normalize_template_name(name, kind=kind), "Other")


def _normalize_locale(locale: str | None) -> str:
    value = (locale or "en").strip().lower().split("-", 1)[0]
    return value if value in PREZ_LOCALES else "en"


def _normalize_template_name(name: str | None, *, kind: str) -> str:
    raw = (name or "").strip().lower().replace("-", "_")
    if kind == "html":
        raw = HTML_STYLE_ALIASES.get(raw, raw)
        return raw if raw in available_html_templates() else "minimal_dark"
    raw = BBCODE_STYLE_ALIASES.get(raw, raw)
    return raw if raw in available_bbcode_templates() else "classic"


def _preset_values(name: str | None) -> dict[str, str]:
    return PREZ_PRESETS.get((name or "default").strip().lower(), PREZ_PRESETS["default"])


def _apply_preset(options: PrezBuildOptions) -> tuple[str, str]:
    preset = _preset_values(options.preset)
    html_template = options.html_template or preset["html_template"]
    bbcode_template = options.bbcode_template or preset["bbcode_template"]
    return (
        _normalize_template_name(html_template, kind="html"),
        _normalize_template_name(bbcode_template, kind="bbcode"),
    )


def _safe_output_name(name: str) -> str:
    return sanitize_filename(name, replacement_text="_").strip(" .") or "release"


def _dash(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        value = value.strip()
        return value if value else "-"
    return str(value)


def _has_value(value: Any) -> bool:
    return _dash(value) != "-"


def _bbcode_escape(value: Any) -> str:
    text = _dash(value)
    return text.replace("[", "(").replace("]", ")")


def _join_list(values: Any, *, sep: str = ", ") -> str:
    if not values:
        return "-"
    if isinstance(values, str):
        return _dash(values)
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return sep.join(cleaned) if cleaned else "-"


def _format_bool(value: bool | None) -> str:
    if value is None:
        return "-"
    return tr("common.yes", default="Yes") if value else tr("common.no", default="No")


def _format_bitrate(value: int | None) -> str:
    if value is None or value <= 0:
        return "-"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} Mb/s"
    return f"{round(value / 1000):d} kb/s"


def _format_runtime_ms(value: int | None) -> str:
    if value is None or value <= 0:
        return "-"
    return format_duration_ms_human(value)


def _format_runtime_minutes(value: int | None) -> str:
    if value is None or value <= 0:
        return "-"
    return tr("prez.runtime_minutes", default="{minutes} min", minutes=value)


def _format_rating(value: Any) -> str:
    if value is None or value == "":
        return "-"
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return _dash(value)
    return f"{rating:.1f}/10"


def _metadata_object(context: dict | None, release: ReleaseNfoData) -> Any | None:
    if not context:
        return None
    if release.media_kind == "movie":
        return context.get("metadata_movie")
    if release.media_kind == "single_episode":
        return context.get("metadata_episode")
    return context.get("metadata_season")


def _title_from_metadata(value: Any | None) -> str | None:
    if not value:
        return None
    for attr in ("title", "episode_title", "series_title", "name"):
        title = getattr(value, attr, None)
        if title:
            return str(title)
    return None


def _metadata_title(context: dict | None, release: ReleaseNfoData | None = None) -> str | None:  # pyright: ignore[reportUnusedFunction]  # Public helper retained for downstream importers
    if not context:
        return None
    if release is not None:
        title = _title_from_metadata(_metadata_object(context, release))
        if title:
            return title
    for key in ("metadata_movie", "metadata_episode", "metadata_season"):
        title = _title_from_metadata(context.get(key))
        if title:
            return title
    return None


def _metadata_attr(value: Any | None, *names: str) -> str | None:
    if not value:
        return None
    for attr in names:
        item = getattr(value, attr, None)
        if item:
            return str(item)
    return None


def _runtime_minutes_from_metadata(value: Any | None) -> int | None:
    if not value:
        return None
    runtime = getattr(value, "runtime_minutes", None)
    return runtime if isinstance(runtime, int) else None


def _tmdb_web_url(path: str) -> str:
    return f"https://www.themoviedb.org/{path.strip('/')}"


def _is_tmdb_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        from urllib.parse import urlparse

        host = urlparse(value).hostname or ""
    except Exception:
        return False
    return host in ("www.themoviedb.org", "themoviedb.org")


def _tmdb_movie_url(metadata: Any | None) -> str | None:
    if not metadata:
        return None
    external = getattr(metadata, "external_url", None)
    if _is_tmdb_url(external) and "/movie/" in str(external):
        return str(external)
    provider_id = getattr(metadata, "provider_id", None)
    return _tmdb_web_url(f"movie/{provider_id}") if provider_id else None


def _tmdb_series_url(metadata: Any | None) -> str | None:
    if not metadata:
        return None
    for attr in ("series_url", "external_url"):
        value = getattr(metadata, attr, None)
        if _is_tmdb_url(value) and "/tv/" in str(value):
            return str(value).split("/season/", 1)[0].split("/episode/", 1)[0]
    series_provider_id = getattr(metadata, "series_provider_id", None)
    if series_provider_id:
        return _tmdb_web_url(f"tv/{series_provider_id}")
    return None


def _tmdb_episode_url(metadata: Any | None) -> str | None:
    if not metadata:
        return None
    value = getattr(metadata, "episode_url", None)
    if _is_tmdb_url(value):
        return str(value)
    series_url = _tmdb_series_url(metadata)
    season = getattr(metadata, "season_number", None)
    episode = getattr(metadata, "episode_number", None)
    if series_url and season is not None and episode is not None:
        return f"{series_url}/season/{season}/episode/{episode}"
    return None


def _tmdb_url(metadata: Any | None, release: ReleaseNfoData) -> str | None:
    if release.media_kind == "movie":
        return _tmdb_movie_url(metadata)
    return _tmdb_series_url(metadata)


def _tmdb_fields(metadata: Any | None, release: ReleaseNfoData) -> tuple[PrezField, ...]:
    if release.media_kind == "movie":
        movie_url = _tmdb_movie_url(metadata)
        return _fields(
            (
                _field(
                    "tmdb_movie",
                    "prez.label.tmdb_movie",
                    "Movie TMDb page",
                    tr("prez.link.tmdb_movie", default="Link to the movie TMDb page")
                    if movie_url
                    else None,
                    url=movie_url,
                    wide=True,
                ),
            )
        )

    series_url = _tmdb_series_url(metadata)
    fields: list[PrezField | None] = [
        _field(
            "tmdb_series",
            "prez.label.tmdb_series",
            "Series TMDb page",
            tr("prez.link.tmdb_series", default="Link to the series TMDb page")
            if series_url
            else None,
            url=series_url,
            wide=True,
        )
    ]
    if release.media_kind == "single_episode":
        episode_url = _tmdb_episode_url(metadata)
        fields.append(
            _field(
                "tmdb_episode",
                "prez.label.tmdb_episode",
                "Episode TMDb page",
                tr("prez.link.tmdb_episode", default="Link to the episode TMDb page")
                if episode_url
                else None,
                url=episode_url,
                wide=True,
            )
        )
    return _fields(fields)


def _heading_titles(metadata: Any | None, release: ReleaseNfoData) -> tuple[str, str]:
    if release.media_kind == "movie":
        return _movie_heading_titles(metadata, release)

    series_title = _series_heading_title(metadata, release)
    if release.media_kind != "single_episode":
        return _dash(series_title), "-"
    return _dash(series_title), _dash(_single_episode_heading_title(metadata, release))


def _movie_heading_titles(metadata: Any | None, release: ReleaseNfoData) -> tuple[str, str]:
    title = _metadata_attr(metadata, "title") or release.title_display or release.release_title
    return _dash(title), "-"


def _series_heading_title(metadata: Any | None, release: ReleaseNfoData) -> str:
    return (
        _metadata_attr(metadata, "series_title")
        or release.series_title
        or release.title_display
        or release.release_title
    )


def _single_episode_heading_title(metadata: Any | None, release: ReleaseNfoData) -> str:
    first = _first_episode(release)
    return (
        _metadata_attr(metadata, "episode_title") or (first.episode_title if first else None) or "-"
    )


def _season_episode(release: ReleaseNfoData) -> str:
    if release.media_kind == "movie":
        return "-"

    codes = _episode_codes(release)
    if not codes:
        return release.season or "-"
    if release.media_kind == "single_episode" or len(codes) == 1:
        return codes[0]
    return _season_episode_series_text(codes)


def _episode_codes(release: ReleaseNfoData) -> list[str]:
    return [episode.episode_code.upper() for episode in release.episodes if episode.episode_code]


def _season_episode_series_text(codes: Sequence[str]) -> str:
    seasons = _season_prefixes(codes)
    if len(seasons) == 1:
        return _single_season_episode_range(codes, next(iter(seasons)))
    return ", ".join(codes)


def _season_prefixes(codes: Sequence[str]) -> set[str]:
    return {code[:3] for code in codes if code.startswith("S") and "E" in code}


def _single_season_episode_range(codes: Sequence[str], season: str) -> str:
    episode_numbers = _episode_numbers(codes)
    if episode_numbers:
        return f"{season}E{min(episode_numbers):02d}-{season}E{max(episode_numbers):02d}"
    return season


def _episode_numbers(codes: Sequence[str]) -> list[int]:
    numbers: list[int] = []
    for code in codes:
        try:
            numbers.append(int(code.split("E", 1)[1]))
        except (IndexError, ValueError):
            continue
    return numbers


def _season_code(release: ReleaseNfoData) -> str:
    if release.media_kind != "season_pack":
        return "-"
    if release.season:
        return _dash(release.season).upper()
    codes = [episode.episode_code.upper() for episode in release.episodes if episode.episode_code]
    seasons = {code[:3] for code in codes if code.startswith("S") and "E" in code}
    if len(seasons) == 1:
        return next(iter(seasons))
    return "-"


def _complete_season_text() -> str:
    return tr("prez.label.complete_season", default="Complete season")


def _release_episode_codes(release: ReleaseNfoData) -> set[str]:
    return {
        episode.episode_code.upper()
        for episode in release.episodes
        if episode.episode_code and episode.episode_code.upper().startswith("S")
    }


def _metadata_episode_codes(metadata_context: dict | None, metadata: Any | None) -> set[str]:
    values: list[Any] = []
    if metadata_context:
        values.extend(metadata_context.get("metadata_season_episode_codes") or [])
        values.extend(metadata_context.get("season_episode_codes") or [])
    codes = {str(value).upper() for value in values if value}
    if codes:
        return codes
    for episode in getattr(metadata, "episode_summaries", []) or []:
        code = _episode_code_from_metadata(episode)
        if code:
            codes.add(code.upper())
    return codes


def _is_complete_season(
    release: ReleaseNfoData, metadata_context: dict | None, metadata: Any | None
) -> bool:
    if release.media_kind != "season_pack":
        return False
    release_codes = _release_episode_codes(release)
    if not release_codes:
        return False
    metadata_codes = _metadata_episode_codes(metadata_context, metadata)
    if not metadata_codes:
        return False
    season = _season_code(release)
    if season != "-":
        metadata_codes = {code for code in metadata_codes if code.startswith(season)}
    return bool(metadata_codes) and metadata_codes.issubset(release_codes)


def _season_label(release: ReleaseNfoData, *, complete: bool) -> str:
    season = _season_code(release)
    if season == "-":
        return "-"
    if complete:
        return f"{season} ({_complete_season_text()})"
    return season


def _season_episode_display(release: ReleaseNfoData, value: str, *, complete: bool) -> str:
    if release.media_kind == "season_pack" and _has_value(value) and complete:
        return f"{value} ({_complete_season_text()})"
    return value


def _title_with_year(title: str, year: Any, release: ReleaseNfoData) -> str:
    text = _dash(title)
    year_text = _dash(year)
    if release.media_kind == "season_pack" and text != "-" and year_text != "-":
        return f"{text} ({year_text})"
    return text


def _format_video_bitrate(release: ReleaseNfoData, first: EpisodeNfoData | None) -> str:
    if release.media_kind == "season_pack":
        values: list[int] = []
        for episode in release.episodes:
            bitrate = episode.video_bitrate
            if bitrate is not None and bitrate > 0:
                values.append(bitrate)
        if values:
            return _format_bitrate(round(sum(values) / len(values)))
    return _format_bitrate(first.video_bitrate if first else None)


def _format_literal_date(value: str | None, locale: str | None) -> str | None:
    if not value:
        return None
    cleaned = str(value).strip()
    try:
        parsed = datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError:
        return cleaned

    locale_map = {"fr": "fr_FR", "en": "en_US", "es": "es_ES"}
    babel_locale = locale_map.get(_normalize_locale(locale), "en_US")
    # Use babel's format_date when available; fall back to a simple strftime otherwise
    if format_date is not None:
        try:
            return format_date(parsed, format="long", locale=babel_locale)
        except Exception:  # nosec B110
            # If babel fails to format, fall back to strftime below
            pass
    return parsed.strftime("%d %B %Y")


def _metadata_release_date(
    metadata: Any | None, release: ReleaseNfoData, locale: str | None = None
) -> str | None:
    if not metadata:
        return None
    if release.media_kind == "movie":
        return _format_literal_date(_metadata_attr(metadata, "release_date"), locale)
    if release.media_kind == "season_pack":
        season_date = _metadata_attr(metadata, "air_date")
        if season_date:
            return _format_literal_date(season_date, locale)
        for episode in getattr(metadata, "episode_summaries", []) or []:
            episode_date = _metadata_attr(episode, "air_date")
            if episode_date:
                return _format_literal_date(episode_date, locale)
        return _format_literal_date(_metadata_attr(metadata, "first_air_date"), locale)
    return _format_literal_date(_metadata_attr(metadata, "air_date", "first_air_date"), locale)


def _episode_code_from_metadata(value: Any | None) -> str | None:
    season = getattr(value, "season_number", None)
    number = getattr(value, "episode_number", None)
    if season is None or number is None:
        return None
    return f"S{season:02d}E{number:02d}"


def _format_average_runtime(release: ReleaseNfoData, metadata: Any | None = None) -> str:
    if release.media_kind != "season_pack":
        return "-"
    local_runtime = _average_local_episode_runtime(release)
    if local_runtime is not None:
        return _format_runtime_minutes(local_runtime)
    metadata_runtime = _average_metadata_episode_runtime(release, metadata)
    if metadata_runtime is not None:
        return _format_runtime_minutes(metadata_runtime)
    return _format_runtime_minutes(_runtime_minutes_from_metadata(metadata))


def _average_local_episode_runtime(release: ReleaseNfoData) -> int | None:
    local_minutes = [
        round(episode.duration_ms / 60_000)
        for episode in release.episodes
        if episode.duration_ms and episode.duration_ms > 0
    ]
    return _average_minutes(local_minutes)


def _average_metadata_episode_runtime(release: ReleaseNfoData, metadata: Any | None) -> int | None:
    release_codes = {episode.episode_code for episode in release.episodes if episode.episode_code}
    metadata_minutes = _matching_metadata_runtime_minutes(metadata, release_codes)
    return _average_minutes(metadata_minutes)


def _matching_metadata_runtime_minutes(metadata: Any | None, release_codes: set[str]) -> list[int]:
    minutes: list[int] = []
    for episode in getattr(metadata, "episode_summaries", []) or []:
        code = _episode_code_from_metadata(episode)
        runtime = getattr(episode, "runtime_minutes", None)
        if runtime and (not release_codes or code in release_codes):
            minutes.append(runtime)
    return minutes


def _average_minutes(values: Sequence[int]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def _unique_tracks(episodes: list[EpisodeNfoData], kind: str) -> tuple[TrackNfoData, ...]:
    seen: set[tuple[Any, ...]] = set()
    results: list[TrackNfoData] = []
    for episode in episodes:
        tracks = episode.audio_tracks if kind == "audio" else episode.subtitle_tracks
        for track in tracks:
            key = (
                track.language_short,
                track.language_display,
                track.format_name,
                track.codec,
                track.channels if kind == "audio" else None,
                track.bitrate if kind == "audio" else None,
                track.subtitle_variant,
                track.is_default,
                track.is_forced,
            )
            if key in seen:
                continue
            seen.add(key)
            results.append(track)
    return tuple(results)


def _subtitle_track_key(track: TrackNfoData) -> tuple[Any, ...]:
    return (
        track.language_short,
        track.language_display,
        track.format_name,
        track.codec,
        track.subtitle_variant or track.title,
        track.is_default,
        track.is_forced,
    )


def _episode_suffix(codes: Sequence[str]) -> str:
    cleaned = [code.upper() for code in codes if code]
    if not cleaned:
        return ""
    seasons = {code[:3] for code in cleaned if code.startswith("S") and "E" in code}
    labels: list[str] = []
    for code in cleaned:
        if len(seasons) == 1 and "E" in code:
            labels.append("E" + code.split("E", 1)[1])
        else:
            labels.append(code)
    return ", ".join(labels)


def _unique_subtitle_tracks(release: ReleaseNfoData) -> tuple[tuple[TrackNfoData, str | None], ...]:
    episode_count = len(release.episodes)
    by_key = _collect_subtitle_track_occurrences(release)
    results: list[tuple[TrackNfoData, str | None]] = []
    for track, indexes, codes in by_key.values():
        suffix = _episode_suffix(codes) if episode_count and len(indexes) < episode_count else ""
        results.append((track, suffix or None))
    return tuple(results)


def _collect_subtitle_track_occurrences(
    release: ReleaseNfoData,
) -> dict[tuple[Any, ...], tuple[TrackNfoData, set[int], list[str]]]:
    by_key: dict[tuple[Any, ...], tuple[TrackNfoData, set[int], list[str]]] = {}
    for index, episode in enumerate(release.episodes):
        code = (episode.episode_code or "").upper()
        for track in episode.subtitle_tracks:
            key = _subtitle_track_key(track)
            if key not in by_key:
                by_key[key] = (track, set(), [])
            _track, indexes, codes = by_key[key]
            indexes.add(index)
            if code and code not in codes:
                codes.append(code)
    return by_key


def _first_episode(release: ReleaseNfoData) -> EpisodeNfoData | None:
    return release.episodes[0] if release.episodes else None


def _first_audio_track(release: ReleaseNfoData) -> TrackNfoData | None:
    for episode in release.episodes:
        if episode.audio_tracks:
            return episode.audio_tracks[0]
    return None


def _format_audio_summary(release: ReleaseNfoData) -> str | None:
    track = _first_audio_track(release)
    if track:
        codec = track.codec or track.format_name or release.audio_tag
        channels = track.channels
        if codec and channels:
            return f"{codec} {channels}"
        if codec:
            return str(codec)
    return release.audio_tag


def _format_technical_summary(release: ReleaseNfoData) -> str:
    parts: list[str] = []
    if release.media_kind == "season_pack":
        parts.append(tr("prez.summary.season_pack", default="Season Pack"))
        parts.append(
            tr("prez.summary.episodes", default="{count} episodes", count=len(release.episodes))
        )
    elif release.media_kind == "single_episode":
        parts.append(_season_episode(release))
    parts.extend(
        str(value)
        for value in (
            release.resolution,
            release.source,
            release.video_tag,
            _format_audio_summary(release),
            release.language_tag,
            release.hdr_display,
        )
        if value
    )
    parts.append(format_bytes_human(release.total_size_bytes))
    return " · ".join(part for part in parts if part and part != "-")


def _country_from_language(value: str | None) -> str | None:
    normalized = _normalized_language_value(value)
    if normalized is None:
        return None
    bracket_region = _region_in_parentheses(normalized)
    if bracket_region is not None:
        return bracket_region
    mapped_region = _FLAG_BY_LANGUAGE.get(normalized)
    if mapped_region is not None:
        return mapped_region
    locale_region = _region_from_locale_value(normalized)
    if locale_region is not None:
        return locale_region
    return _region_from_short_code(normalized)


def _normalized_language_value(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("_", "-")
    return normalized or None


def _canonical_region(value: str) -> str:
    return "gb" if value == "uk" else value


def _region_in_parentheses(normalized: str) -> str | None:
    if "(" not in normalized or ")" not in normalized:
        return None
    region = normalized.split("(", 1)[1].split(")", 1)[0].strip().lower()
    if len(region) != 2:
        return None
    return _canonical_region(region)


def _region_from_locale_value(normalized: str) -> str | None:
    if "-" not in normalized:
        return None
    region = normalized.split("-", 1)[1]
    if len(region) != 2:
        return None
    return _canonical_region(region)


def _region_from_short_code(normalized: str) -> str | None:
    if len(normalized) != 2:
        return None
    if normalized == "en":
        return "gb"
    return normalized


def _flag_url(language_code: str | None, language_display: str | None) -> str | None:
    country = _country_from_language(language_code) or _country_from_language(language_display)
    return f"https://flagcdn.com/20x15/{country}.png" if country else None


def _track_language(track: TrackNfoData) -> str:
    return _dash(track.language_display or track.language_short)


def _to_prez_audio_track(track: TrackNfoData) -> PrezTrack:
    language = _track_language(track)
    return PrezTrack(
        language=language,
        language_code=track.language_short,
        flag_url=_flag_url(track.language_short, language),
        codec=_dash(track.codec or track.format_name),
        channels=_dash(track.channels),
        bitrate=_format_bitrate(track.bitrate),
        variant="-",
        format_name=_dash(track.format_name or track.codec),
        is_default=_format_bool(track.is_default),
        is_forced=_format_bool(track.is_forced),
    )


def _normalize_subtitle_format(track: TrackNfoData) -> str:
    raw = (track.format_name or track.codec or "").strip()
    lowered = raw.lower().replace("-", "").replace("_", "")
    mapping = {
        "utf8": "SRT",
        "subrip": "SRT",
        "ssa": "ASS",
        "ass": "ASS",
        "webvtt": "WebVTT",
        "vtt": "WebVTT",
        "ttml": "TTML",
        "srt": "SRT",
        "pgs": "PGS",
    }
    return mapping.get(lowered, _dash(raw))


def _to_prez_subtitle_track(track: TrackNfoData, episode_suffix: str | None = None) -> PrezTrack:
    language = _track_language(track)
    if episode_suffix:
        language = f"{language} ({episode_suffix})"
    subtitle_format = _normalize_subtitle_format(track)
    return PrezTrack(
        language=language,
        language_code=track.language_short,
        flag_url=_flag_url(track.language_short, language),
        codec=subtitle_format,
        channels="-",
        bitrate=_format_bitrate(track.bitrate),
        variant=_dash(track.subtitle_variant or track.title),
        format_name=subtitle_format,
        is_default=_format_bool(track.is_default),
        is_forced=_format_bool(track.is_forced),
    )


def _group_tracks_by_language(tracks: Sequence[PrezTrack]) -> tuple[PrezTrackGroup, ...]:
    """Group tracks by language, maintaining order of first appearance."""
    if not tracks:
        return ()

    # Use dict to maintain insertion order (Python 3.7+)
    groups: dict[str, list[PrezTrack]] = {}
    language_metadata: dict[str, tuple[str | None, str | None]] = {}

    for track in tracks:
        lang_key = track.language_code or track.language or "unknown"

        if lang_key not in groups:
            groups[lang_key] = []
            language_metadata[lang_key] = (track.language_code, track.flag_url)

        groups[lang_key].append(track)

    return tuple(
        PrezTrackGroup(
            language=tracks_in_group[0].language,
            language_code=language_metadata[lang_key][0],
            flag_url=language_metadata[lang_key][1],
            tracks=tuple(tracks_in_group),
        )
        for lang_key, tracks_in_group in groups.items()
    )


def _field(
    key: str,
    label_key: str,
    default: str,
    value: Any,
    *,
    url: str | None = None,
    wide: bool = False,
) -> PrezField | None:
    text = _dash(value)
    if text == "-":
        return None
    return PrezField(key=key, label=tr(label_key, default=default), value=text, url=url, wide=wide)


def _fields(items: Iterable[PrezField | None]) -> tuple[PrezField, ...]:
    return tuple(item for item in items if item is not None)


def _extract_base_metadata(
    release: ReleaseNfoData,
    metadata: Any,
    first: EpisodeNfoData | None,
    metadata_context: dict | None,
    poster_url: str | None,
    locale: str | None,
) -> dict[str, Any]:
    """Extract and compute base metadata values.

    Args:
        release: Release NFO data
        metadata: Metadata object from provider
        first: First episode data (if available)
        metadata_context: Additional metadata context
        poster_url: Fallback poster URL
        locale: Locale for date formatting

    Returns:
        Dictionary containing computed metadata values
    """
    heading_title, heading_subtitle = _heading_titles(metadata, release)
    title = heading_title
    original_title = (
        _metadata_attr(metadata, "original_title", "series_original_title", "original_name")
        or title
    )
    year = getattr(metadata, "year", None) or getattr(metadata, "series_year", None) or release.year
    runtime_minutes = _runtime_minutes_from_metadata(metadata)
    runtime = _format_runtime_minutes(runtime_minutes)
    if runtime == "-":
        runtime = _format_runtime_ms(first.duration_ms if first else release.total_duration_ms)

    season_is_complete = _is_complete_season(release, metadata_context, metadata)
    season_episode_range = _season_episode(release)
    season_episode = _season_episode_display(
        release, season_episode_range, complete=season_is_complete
    )
    season_label = _season_label(release, complete=season_is_complete)
    display_title = _title_with_year(title, year, release)
    video_bitrate = _format_video_bitrate(release, first)
    average_runtime = _format_average_runtime(release, metadata)
    tmdb_url = _tmdb_url(metadata, release)
    tmdb_id = _dash(getattr(metadata, "provider_id", None))
    rating = _format_rating(getattr(metadata, "vote_average", None))
    file_size = format_bytes_human(release.total_size_bytes)
    technical_summary = _format_technical_summary(release)
    genres = _join_list(getattr(metadata, "genres", None))
    release_date = _metadata_release_date(metadata, release, locale)

    # Prioritize selected cover URL from metadata context, then metadata poster, then fallback
    selected_poster_url = (
        (metadata_context or {}).get("metadata_cover_url")
        or _metadata_attr(metadata, "poster_url", "still_url")
        or poster_url
    )

    return {
        "title": title,
        "original_title": original_title,
        "year": year,
        "runtime": runtime,
        "heading_title": heading_title,
        "heading_subtitle": heading_subtitle,
        "season_is_complete": season_is_complete,
        "season_episode_range": season_episode_range,
        "season_episode": season_episode,
        "season_label": season_label,
        "display_title": display_title,
        "video_bitrate": video_bitrate,
        "average_runtime": average_runtime,
        "tmdb_url": tmdb_url,
        "tmdb_id": tmdb_id,
        "rating": rating,
        "file_size": file_size,
        "technical_summary": technical_summary,
        "genres": genres,
        "release_date": release_date,
        "selected_poster_url": selected_poster_url,
    }


def _build_info_fields(
    release: ReleaseNfoData,
    metadata: Any,
    base_meta: dict[str, Any],
) -> tuple[PrezField, ...]:
    """Build information fields for presentation.

    Args:
        release: Release NFO data
        metadata: Metadata object from provider
        base_meta: Base metadata dictionary from _extract_base_metadata

    Returns:
        Tuple of PrezField objects for information section
    """
    runtime_field = (
        _field(
            "average_runtime",
            "prez.label.average_runtime",
            "Average runtime per episode",
            base_meta["average_runtime"],
        )
        if release.media_kind == "season_pack"
        else _field("runtime", "prez.label.runtime", "Runtime", base_meta["runtime"])
    )

    return _fields(
        (
            _field("title", "prez.label.title", "Title", base_meta["title"], wide=True),
            _field(
                "episode_title",
                "prez.label.episode_title",
                "Episode title",
                base_meta["heading_subtitle"],
                wide=True,
            ),
            _field(
                "original_title",
                "prez.label.original_title",
                "Original title",
                base_meta["original_title"],
                wide=True,
            ),
            _field(
                "season_episode",
                "prez.label.season_episode",
                "Season / Episode",
                base_meta["season_episode"],
            ),
            _field(
                "genres",
                "prez.label.genres",
                "Genres",
                base_meta["genres"],
                wide=True,
            ),
            _field(
                "release_date",
                "prez.label.release_date",
                "Release date",
                base_meta["release_date"],
            ),
            _field(
                "countries",
                "prez.label.countries",
                "Countries",
                _join_list(getattr(metadata, "countries", None)),
            ),
            _field(
                "spoken_languages",
                "prez.label.spoken_languages",
                "Spoken languages",
                _join_list(getattr(metadata, "spoken_languages", None)),
            ),
            runtime_field,
        )
    )


def _build_metadata_and_release_fields(
    release: ReleaseNfoData,
    metadata: Any,
    base_meta: dict[str, Any],
) -> tuple[tuple[PrezField, ...], tuple[PrezField, ...]]:
    """Build metadata and release fields for presentation.

    Args:
        release: Release NFO data
        metadata: Metadata object from provider
        base_meta: Base metadata dictionary from _extract_base_metadata

    Returns:
        Tuple of (metadata_fields, release_fields)
    """
    metadata_fields = _fields(
        (_field("rating", "prez.label.rating", "Rating", base_meta["rating"]),)
    )
    metadata_fields = metadata_fields + _tmdb_fields(metadata, release)

    release_fields = _fields(
        (
            _field("team", "prez.label.team", "Team", release.team),
            _field("release", "prez.label.release", "Release", release.release_title, wide=True),
            _field("file_size", "prez.label.file_size", "Size", base_meta["file_size"]),
            _field(
                "files_count",
                "prez.label.files_count",
                "Files count",
                str(_release_files_count(release)),
            ),
        )
    )

    return metadata_fields, release_fields


def _build_video_fields(
    release: ReleaseNfoData,
    first: EpisodeNfoData | None,
    base_meta: dict[str, Any],
) -> tuple[PrezField, ...]:
    """Build video technical fields for presentation.

    Args:
        release: Release NFO data
        first: First episode data (if available)
        base_meta: Base metadata dictionary from _extract_base_metadata

    Returns:
        Tuple of PrezField objects for video section
    """
    label_key, label_default = _video_bitrate_labels(release)
    return _fields(
        (
            _field("source", "prez.label.source", "Source", release.source),
            _field(
                "resolution",
                "prez.label.resolution",
                "Resolution",
                _release_resolution(release, first),
            ),
            _field(
                "video_codec",
                "prez.label.video_codec",
                "Video codec",
                _release_video_codec(release, first),
            ),
            _field(
                "video_bitrate",
                label_key,
                label_default,
                base_meta["video_bitrate"],
            ),
            _field(
                "aspect_ratio",
                "prez.label.aspect_ratio",
                "Aspect ratio",
                _release_aspect_ratio(first),
            ),
            _field(
                "hdr",
                "prez.label.hdr",
                "HDR",
                _release_hdr(release, first),
            ),
        )
    )


def _release_files_count(release: ReleaseNfoData) -> int:
    episode_count = max(len(release.episodes), 1)
    return episode_count * 2


def _video_bitrate_labels(release: ReleaseNfoData) -> tuple[str, str]:
    if release.media_kind == "season_pack":
        return "prez.label.average_video_bitrate", "Average video bitrate"
    return "prez.label.video_bitrate", "Video bitrate"


def _release_resolution(release: ReleaseNfoData, first: EpisodeNfoData | None) -> str | None:
    if release.resolution:
        return release.resolution
    return first.resolution if first else None


def _release_video_codec(release: ReleaseNfoData, first: EpisodeNfoData | None) -> str | None:
    if release.video_tag:
        return release.video_tag
    return first.video_codec if first else None


def _release_aspect_ratio(first: EpisodeNfoData | None) -> str | None:
    if first is None:
        return None
    return first.aspect_ratio_display or first.aspect_ratio


def _release_hdr(release: ReleaseNfoData, first: EpisodeNfoData | None) -> str | None:
    if release.hdr_display:
        return release.hdr_display
    return first.hdr_display if first else None


def _build_prez_data(
    release: ReleaseNfoData,
    *,
    metadata_context: dict | None,
    mediainfo_text: str | None = None,
    poster_url: str | None = None,
    locale: str | None = None,
    banner_audio: str = "",
    banner_information: str = "",
    banner_metadata: str = "",
    banner_release: str = "",
    banner_subtitles: str = "",
    banner_synopsis: str = "",
    banner_technical: str = "",
) -> PrezData:
    """Build presentation data from release and metadata.

    Args:
        release: Release NFO data
        metadata_context: Additional metadata context
        mediainfo_text: MediaInfo text content
        poster_url: Fallback poster URL
        locale: Locale for date formatting
        banner_audio: Banner image URL for the audio section.
        banner_information: Banner image URL for the information section.
        banner_metadata: Banner image URL for the metadata section.
        banner_release: Banner image URL for the release section.
        banner_subtitles: Banner image URL for the subtitles section.
        banner_synopsis: Banner image URL for the synopsis section.
        banner_technical: Banner image URL for the technical section.

    Returns:
        Complete PrezData object ready for template rendering
    """
    metadata = _metadata_object(metadata_context, release)
    first = _first_episode(release)
    base_meta = _extract_base_metadata(
        release, metadata, first, metadata_context, poster_url, locale
    )
    info_fields = _build_info_fields(release, metadata, base_meta)
    metadata_fields, release_fields = _build_metadata_and_release_fields(
        release, metadata, base_meta
    )
    video_fields = _build_video_fields(release, first, base_meta)
    track_sections = _build_track_sections(release)
    return PrezData(
        release=release,
        title=base_meta["display_title"],
        original_title=_dash(base_meta["original_title"]),
        year=_dash(base_meta["year"]),
        heading_title=_dash(base_meta["heading_title"]),
        heading_subtitle=_dash(base_meta["heading_subtitle"]),
        season_label=base_meta["season_label"],
        season_episode=base_meta["season_episode"],
        season_episode_range=base_meta["season_episode_range"],
        subtitle_line=_build_subtitle_line(release, base_meta),
        poster_url=_dash(base_meta["selected_poster_url"]),
        overview=_dash(getattr(metadata, "overview", None)),
        technical_summary=base_meta["technical_summary"],
        release_name=_dash(release.release_title),
        team=_dash(release.team),
        file_size=base_meta["file_size"],
        files_count=str(_release_files_count(release)),
        source=_dash(release.source),
        resolution=_dash(_release_resolution(release, first)),
        video_codec=_dash(_release_video_codec(release, first)),
        video_bitrate=base_meta["video_bitrate"],
        aspect_ratio=_dash(_release_aspect_ratio(first)),
        hdr=_dash(_release_hdr(release, first)),
        tmdb_id=base_meta["tmdb_id"],
        tmdb_url=_dash(base_meta["tmdb_url"]),
        imdb_id="-",
        rating=base_meta["rating"],
        cast=_join_list(getattr(metadata, "cast", None)),
        crew=_join_list(getattr(metadata, "crew", None)),
        mediainfo_text=mediainfo_text.strip() if mediainfo_text else None,
        info_fields=info_fields,
        metadata_fields=metadata_fields,
        release_fields=release_fields,
        video_fields=video_fields,
        audio_tracks=track_sections.audio_tracks,
        subtitle_tracks=track_sections.subtitle_tracks,
        audio_track_groups=track_sections.audio_track_groups,
        subtitle_track_groups=track_sections.subtitle_track_groups,
        badges=_build_badges(release, base_meta),
        banner_audio=banner_audio,
        banner_information=banner_information,
        banner_metadata=banner_metadata,
        banner_release=banner_release,
        banner_subtitles=banner_subtitles,
        banner_synopsis=banner_synopsis,
        banner_technical=banner_technical,
    )


@dataclass(frozen=True, slots=True)
class _TrackSections:
    audio_tracks: tuple[PrezTrack, ...]
    subtitle_tracks: tuple[PrezTrack, ...]
    audio_track_groups: tuple[PrezTrackGroup, ...]
    subtitle_track_groups: tuple[PrezTrackGroup, ...]


def _build_subtitle_line(release: ReleaseNfoData, base_meta: dict[str, Any]) -> str:
    year_value = "-" if release.media_kind == "season_pack" else _dash(base_meta["year"])
    runtime_value = (
        base_meta["average_runtime"]
        if release.media_kind == "season_pack"
        else base_meta["runtime"]
    )
    return " · ".join(
        item for item in (year_value, runtime_value, base_meta["genres"]) if item != "-"
    )


def _build_badges(release: ReleaseNfoData, base_meta: dict[str, Any]) -> tuple[str, ...]:
    values = (
        base_meta["season_episode"],
        release.resolution,
        release.source,
        release.video_tag,
        release.audio_tag,
        release.language_tag,
        base_meta["file_size"],
    )
    return tuple(item for item in values if isinstance(item, str) and _has_value(item))


def _build_track_sections(release: ReleaseNfoData) -> _TrackSections:
    audio_tracks = tuple(
        _to_prez_audio_track(track) for track in _unique_tracks(release.episodes, "audio")
    )
    subtitle_tracks = tuple(
        _to_prez_subtitle_track(track, suffix) for track, suffix in _unique_subtitle_tracks(release)
    )
    return _TrackSections(
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
        audio_track_groups=_group_tracks_by_language(audio_tracks),
        subtitle_track_groups=_group_tracks_by_language(subtitle_tracks),
    )


def _discover_screenshots(folder: Path) -> tuple[str, ...]:  # pyright: ignore[reportUnusedFunction]  # Public helper retained for downstream importers
    if not folder.exists():
        return ()
    candidates: list[Path] = []
    for child in folder.iterdir():
        if _is_screenshot_directory(child):
            candidates.extend(_screenshot_files_in_directory(child))
            continue
        if _is_named_screenshot_file(child):
            candidates.append(child)
    return tuple(str(path) for path in candidates[:12])


def _is_screenshot_directory(path: Path) -> bool:
    return path.is_dir() and path.name.lower() in SCREENSHOT_DIR_NAMES


def _screenshot_files_in_directory(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SCREENSHOT_SUFFIXES
    )


def _is_named_screenshot_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in SCREENSHOT_SUFFIXES:
        return False
    return path.stem.lower().startswith(("screen", "screenshot", "capture", "thumb"))


def _discover_local_poster(folder: Path) -> str | None:
    if not folder.exists():
        return None
    for child in sorted(folder.iterdir()):
        if child.is_file() and child.name.lower() in POSTER_FILENAMES:
            return str(child)
    return None


def _read_mediainfo_text(folder: Path) -> str | None:
    for child in folder.iterdir() if folder.exists() else []:
        if not child.is_file():
            continue
        name = child.name.lower()
        if name in MEDIAINFO_FILENAMES or name.endswith(".mediainfo.txt"):
            text = child.read_text(encoding="utf-8", errors="replace").strip()
            return text or None
    return None


def _generate_mediainfo_text(
    release: ReleaseNfoData, registry: ToolRegistry | None = None
) -> str | None:
    """Generate MediaInfo text output using pymediainfo library.

    Args:
        release: Release NFO data containing episode information
        registry: Tool registry (unused, kept for backward compatibility)

    Returns:
        Formatted MediaInfo text for all episodes, or None if pymediainfo is unavailable
    """
    if MediaInfo is None:
        return None

    sections: list[str] = []
    for episode in release.episodes:
        try:
            text_output = _episode_mediainfo_text(episode)
            if text_output:
                sections.append(f"===== {episode.file_name} =====\n{text_output}")
        except Exception:  # nosec B112
            # Silently skip files that can't be parsed
            continue

    return "\n\n".join(sections).strip() or None


def _episode_mediainfo_text(episode: EpisodeNfoData) -> str | None:
    if MediaInfo is None:
        return None
    media_info_obj = MediaInfo.parse(str(episode.file_path))
    if not media_info_obj or isinstance(media_info_obj, str):
        return None
    return _render_mediainfo_payload(media_info_obj.to_data())


def _render_mediainfo_payload(payload: Any) -> str | None:
    if not payload:
        return None
    if isinstance(payload, dict):  # pyright: ignore[reportUnnecessaryIsInstance]  # Library may return non-dict at runtime
        text_output = _render_mediainfo_dict(payload)
    else:
        text_output = str(payload).strip()
    return text_output or None


def _render_mediainfo_dict(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for track in payload.get("tracks", []):
        track_type = track.get("track_type", "Unknown")
        lines.append(f"{track_type}")
        for key, value in track.items():
            if key == "track_type" or not value:
                continue
            lines.append(f"{key.replace('_', ' ').title():<40}: {value}")
        lines.append("")
    return "\n".join(lines).strip()


def _template_autoescape(kind: str) -> Callable[[str | None], bool]:
    """Return autoescape policy for prez templates.

    HTML templates use Jinja autoescaping even though the shipped template files
    end with ``.jinja2``. BBCode templates remain unescaped plain text.
    """
    if kind == "html":
        html_autoescape = select_autoescape(enabled_extensions=("html", "xml"))
        return lambda template_name: html_autoescape(template_name or "template.html")
    return lambda _template_name: False


def _template_environment(kind: str) -> Environment:
    # Use PackageLoader with multiple search paths to support base templates and generated templates
    from jinja2 import ChoiceLoader

    # For HTML, check generated folder first; for BBCode, use direct path
    if kind == "html":
        loader = ChoiceLoader(
            [
                PackageLoader(
                    "swirrl", f"templates/prez/{kind}/generated"
                ),  # New generated templates
                PackageLoader("swirrl", f"templates/prez/{kind}"),  # Legacy templates
                PackageLoader("swirrl", "templates/prez/base"),
            ]
        )
    else:
        loader = ChoiceLoader(
            [
                PackageLoader("swirrl", f"templates/prez/{kind}"),  # BBCode templates
                PackageLoader("swirrl", "templates/prez/base"),
            ]
        )

    env = Environment(  # nosec B701  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
        loader=loader,
        autoescape=_template_autoescape(kind),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # jinja2's Environment.globals is typed too strictly (a Mapping of utility
    # singletons), but at runtime it accepts arbitrary callables. Cast to a
    # broader dict for type-clean assignment.
    globals_dict: dict[str, Any] = cast(dict[str, Any], env.globals)
    globals_dict["tr"] = tr
    globals_dict["dash"] = _dash
    globals_dict["bb"] = _bbcode_escape
    globals_dict["html_escape"] = escape
    globals_dict["field_url_bbcode"] = _field_url_bbcode
    globals_dict["field_url_html"] = _field_url_html
    globals_dict["bbcode_banner"] = _render_bbcode_banner
    globals_dict["audio_table_bbcode"] = _render_audio_tracks_bbcode
    globals_dict["subtitle_table_bbcode"] = _render_subtitle_tracks_bbcode
    globals_dict["audio_table_html"] = _render_audio_tracks_html
    globals_dict["subtitle_table_html"] = _render_subtitle_tracks_html
    globals_dict["audio_table_grouped_bbcode"] = _render_audio_tracks_grouped_bbcode
    globals_dict["subtitle_table_grouped_bbcode"] = _render_subtitle_tracks_grouped_bbcode
    globals_dict["audio_table_grouped_html"] = _render_audio_tracks_grouped_html
    globals_dict["subtitle_table_grouped_html"] = _render_subtitle_tracks_grouped_html
    globals_dict["mediainfo_spoiler"] = _render_mediainfo_spoiler
    globals_dict["style_css"] = _html_style_css
    globals_dict["body_class"] = _html_body_class
    return env


def _load_template(kind: str, name: str, locale: str):
    normalized = _normalize_template_name(name, kind=kind)
    normalized_locale = _normalize_locale(locale)
    env = _template_environment(kind)
    candidates = (f"{normalized}.{normalized_locale}.jinja2", f"{normalized}.en.jinja2")
    for candidate in candidates:
        try:
            return env.get_template(candidate)
        except Exception:  # nosec B112
            continue
    raise ValueError(f"Unknown {kind} prez template: {name}")


def _field_url_bbcode(field: PrezField) -> str:
    value = _bbcode_escape(field.value)
    if field.url:
        return f"[url={_bbcode_escape(field.url)}]{value}[/url]"
    return value


def _field_url_html(field: PrezField) -> str:
    value = escape(field.value)
    if field.url:
        return f'<a href="{escape(field.url)}" target="_blank" rel="noreferrer">{value}</a>'
    return value


def _track_language_bbcode(track: PrezTrack) -> str:
    prefix = f"[img]{track.flag_url}[/img] " if track.flag_url else ""
    return prefix + _bbcode_escape(track.language)


def _track_language_html(track: PrezTrack) -> str:
    prefix = f'<img class="flag" src="{escape(track.flag_url)}" alt=""> ' if track.flag_url else ""
    return prefix + escape(track.language)


def _render_bbcode_banner(banner_url: str | None) -> str:
    """Render a BBCode banner image if URL is provided."""
    if not banner_url or not banner_url.strip():
        return ""
    return f"[center][img]{_bbcode_escape(banner_url)}[/img][/center]\n"


def _render_audio_tracks_bbcode(tracks: Sequence[PrezTrack]) -> str:
    """Render audio tracks as a single BBCode table with all tracks grouped together.

    This is the NEW global table format with Track # and Language columns.
    """
    header = (
        "[table]\n"
        "[tr][th]"
        + tr("prez.audio.track", default="Track")
        + "[/th][th]"
        + tr("prez.audio.language", default="Language")
        + "[/th][th]"
        + tr("prez.audio.codec", default="Codec")
        + "[/th][th]"
        + tr("prez.audio.channels", default="Channels")
        + "[/th][th]"
        + tr("prez.audio.bitrate", default="Bitrate")
        + "[/th][th]"
        + tr("prez.audio.default", default="Default")
        + "[/th][/tr]"
    )
    if not tracks:
        return (
            header
            + "\n[tr][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][/tr]\n[/table]"
        )

    # Group all tracks in a single table with track numbers
    rows = [
        "[tr]"
        f"[td]{i + 1}[/td]"
        f"[td]{_track_language_bbcode(track)}[/td]"
        f"[td]{_bbcode_escape(track.codec)}[/td]"
        f"[td]{_bbcode_escape(track.channels)}[/td]"
        f"[td]{_bbcode_escape(track.bitrate)}[/td]"
        f"[td]{_bbcode_escape(track.is_default)}[/td]"
        "[/tr]"
        for i, track in enumerate(tracks)
    ]
    return header + "\n" + "\n".join(rows) + "\n[/table]"


def _render_subtitle_tracks_bbcode(tracks: Sequence[PrezTrack]) -> str:
    """Render subtitle tracks as a single BBCode table.

    Columns: Track #, Language, Variant, Format, Default, Forced.
    """
    header = (
        "[table]\n"
        "[tr][th]"
        + tr("prez.subtitles.track", default="Track")
        + "[/th][th]"
        + tr("prez.subtitles.language", default="Language")
        + "[/th][th]"
        + tr("prez.subtitles.variant", default="Variant")
        + "[/th][th]"
        + tr("prez.subtitles.format", default="Format")
        + "[/th][th]"
        + tr("prez.subtitles.default", default="Default")
        + "[/th][th]"
        + tr("prez.subtitles.forced", default="Forced")
        + "[/th][/tr]"
    )
    if not tracks:
        return (
            header
            + "\n[tr][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][/tr]\n[/table]"
        )

    rows = [
        "[tr]"
        f"[td]{i + 1}[/td]"
        f"[td]{_track_language_bbcode(track)}[/td]"
        f"[td]{_bbcode_escape(track.variant)}[/td]"
        f"[td]{_bbcode_escape(track.format_name)}[/td]"
        f"[td]{_bbcode_escape(track.is_default)}[/td]"
        f"[td]{_bbcode_escape(track.is_forced)}[/td]"
        "[/tr]"
        for i, track in enumerate(tracks)
    ]
    return header + "\n" + "\n".join(rows) + "\n[/table]"


def _render_mediainfo_spoiler(mediainfo_text: str | None) -> str:
    if not mediainfo_text:
        return ""
    label = tr("prez.section.mediainfo", default="MediaInfo")
    return f"\n[spoiler={label}]\n{_bbcode_escape(mediainfo_text)}\n[/spoiler]"


def _html_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["-" for _ in headers]]
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>"


def _render_audio_tracks_html(tracks: Sequence[PrezTrack]) -> str:
    rows = [
        [
            _track_language_html(track),
            escape(track.codec),
            escape(track.channels),
            escape(track.bitrate),
            escape(track.is_default),
        ]
        for track in tracks
    ]
    return _html_table(
        [
            tr("prez.audio.language", default="Language"),
            tr("prez.audio.codec", default="Codec"),
            tr("prez.audio.channels", default="Channels"),
            tr("prez.audio.bitrate", default="Bitrate"),
            tr("prez.audio.default", default="Default"),
        ],
        rows,
    )


def _render_subtitle_tracks_html(tracks: Sequence[PrezTrack]) -> str:
    rows = [
        [
            _track_language_html(track),
            escape(track.variant),
            escape(track.format_name),
            escape(track.is_default),
            escape(track.is_forced),
        ]
        for track in tracks
    ]
    return _html_table(
        [
            tr("prez.subtitles.language", default="Language"),
            tr("prez.subtitles.type", default="Type"),
            tr("prez.subtitles.format", default="Format"),
            tr("prez.subtitles.default", default="Default"),
            tr("prez.subtitles.forced", default="Forced"),
        ],
        rows,
    )


def _render_audio_tracks_grouped_bbcode(track_groups: Sequence[PrezTrackGroup]) -> str:
    """Render audio tracks grouped by language in BBCode format."""
    if not track_groups:
        header = (
            "[table]\n"
            "[tr][th]"
            + tr("prez.audio.language", default="Language")
            + "[/th][th]"
            + tr("prez.audio.codec", default="Codec")
            + "[/th][th]"
            + tr("prez.audio.channels", default="Channels")
            + "[/th][th]"
            + tr("prez.audio.bitrate", default="Bitrate")
            + "[/th][th]"
            + tr("prez.audio.default", default="Default")
            + "[/th][/tr]"
        )
        return header + "\n[tr][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][/tr]\n[/table]"

    result_parts = []
    for group in track_groups:
        # Language header row with flag
        lang_display = (
            f"[img]{group.flag_url}[/img] {_bbcode_escape(group.language)}"
            if group.flag_url
            else _bbcode_escape(group.language)
        )

        header = (
            "[table]\n"
            "[tr][th]"
            + tr("prez.audio.language", default="Language")
            + "[/th][th]"
            + tr("prez.audio.codec", default="Codec")
            + "[/th][th]"
            + tr("prez.audio.channels", default="Channels")
            + "[/th][th]"
            + tr("prez.audio.bitrate", default="Bitrate")
            + "[/th][th]"
            + tr("prez.audio.default", default="Default")
            + "[/th][/tr]"
        )

        rows = []
        for i, track in enumerate(group.tracks):
            # Only show language in first row of group
            lang_cell = lang_display if i == 0 else ""
            rows.append(
                "[tr]"
                f"[td]{lang_cell}[/td]"
                f"[td]{_bbcode_escape(track.codec)}[/td]"
                f"[td]{_bbcode_escape(track.channels)}[/td]"
                f"[td]{_bbcode_escape(track.bitrate)}[/td]"
                f"[td]{_bbcode_escape(track.is_default)}[/td]"
                "[/tr]"
            )

        result_parts.append(header + "\n" + "\n".join(rows) + "\n[/table]")

    return "\n\n".join(result_parts)


def _render_subtitle_tracks_grouped_bbcode(track_groups: Sequence[PrezTrackGroup]) -> str:
    """Render subtitle tracks grouped by language in BBCode format."""
    if not track_groups:
        header = (
            "[table]\n"
            "[tr][th]"
            + tr("prez.subtitles.language", default="Language")
            + "[/th][th]"
            + tr("prez.subtitles.type", default="Type")
            + "[/th][th]"
            + tr("prez.subtitles.format", default="Format")
            + "[/th][th]"
            + tr("prez.subtitles.default", default="Default")
            + "[/th][th]"
            + tr("prez.subtitles.forced", default="Forced")
            + "[/th][/tr]"
        )
        return header + "\n[tr][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][/tr]\n[/table]"

    result_parts = []
    for group in track_groups:
        # Language header row with flag
        lang_display = (
            f"[img]{group.flag_url}[/img] {_bbcode_escape(group.language)}"
            if group.flag_url
            else _bbcode_escape(group.language)
        )

        header = (
            "[table]\n"
            "[tr][th]"
            + tr("prez.subtitles.language", default="Language")
            + "[/th][th]"
            + tr("prez.subtitles.type", default="Type")
            + "[/th][th]"
            + tr("prez.subtitles.format", default="Format")
            + "[/th][th]"
            + tr("prez.subtitles.default", default="Default")
            + "[/th][th]"
            + tr("prez.subtitles.forced", default="Forced")
            + "[/th][/tr]"
        )

        rows = []
        for i, track in enumerate(group.tracks):
            # Only show language in first row of group
            lang_cell = lang_display if i == 0 else ""
            rows.append(
                "[tr]"
                f"[td]{lang_cell}[/td]"
                f"[td]{_bbcode_escape(track.variant)}[/td]"
                f"[td]{_bbcode_escape(track.format_name)}[/td]"
                f"[td]{_bbcode_escape(track.is_default)}[/td]"
                f"[td]{_bbcode_escape(track.is_forced)}[/td]"
                "[/tr]"
            )

        result_parts.append(header + "\n" + "\n".join(rows) + "\n[/table]")

    return "\n\n".join(result_parts)


def _render_audio_tracks_grouped_html(track_groups: Sequence[PrezTrackGroup]) -> str:
    """Render audio tracks grouped by language in HTML format.

    Headers appear once at the top of the single unified table.
    Within the table, the language cell is shown only on the first row
    of each group; subsequent rows of the same group leave it empty.
    """
    headers = [
        tr("prez.audio.language", default="Language"),
        tr("prez.audio.codec", default="Codec"),
        tr("prez.audio.channels", default="Channels"),
        tr("prez.audio.bitrate", default="Bitrate"),
        tr("prez.audio.default", default="Default"),
    ]
    if not track_groups:
        return _html_table(headers, [])

    all_rows: list[list[str]] = []
    for group in track_groups:
        for i, track in enumerate(group.tracks):
            lang_cell = _track_language_html(track) if i == 0 else ""
            all_rows.append(
                [
                    lang_cell,
                    escape(track.codec),
                    escape(track.channels),
                    escape(track.bitrate),
                    escape(track.is_default),
                ]
            )

    return _html_table(headers, all_rows)


def _render_subtitle_tracks_grouped_html(track_groups: Sequence[PrezTrackGroup]) -> str:
    """Render subtitle tracks grouped by language in HTML format.

    Headers appear once at the top of the single unified table.
    Within the table, the language cell is shown only on the first row
    of each group; subsequent rows of the same group leave it empty.
    """
    headers = [
        tr("prez.subtitles.language", default="Language"),
        tr("prez.subtitles.type", default="Type"),
        tr("prez.subtitles.format", default="Format"),
        tr("prez.subtitles.default", default="Default"),
        tr("prez.subtitles.forced", default="Forced"),
    ]
    if not track_groups:
        return _html_table(headers, [])

    all_rows: list[list[str]] = []
    for group in track_groups:
        for i, track in enumerate(group.tracks):
            lang_cell = _track_language_html(track) if i == 0 else ""
            all_rows.append(
                [
                    lang_cell,
                    escape(track.variant),
                    escape(track.format_name),
                    escape(track.is_default),
                    escape(track.is_forced),
                ]
            )

    return _html_table(headers, all_rows)


def _html_style_css(style: str) -> str:
    """Get CSS custom properties for a template style/theme.

    Uses the theme loader to fetch theme configurations from YAML files.
    Falls back to hardcoded values if theme loader is unavailable.
    """
    # Try to use the theme loader first
    css = get_html_theme_css(style)
    if css:
        return css

    # Fallback to hardcoded styles if theme loader fails
    styles = {
        "aurora": "--bg:#0f172a;--card:#111c33;--line:#00856f;--text:#e8f2f1;--muted:#a7b7c7;--accent:#6ee7b7;--accent2:#8b5cf6;--hero:linear-gradient(140deg,rgba(17,28,51,.98),rgba(5,25,23,.92));",
        "emerald": "--bg:#071711;--card:#0b231b;--line:#00a37a;--text:#edfdf7;--muted:#a8cabb;--accent:#80ffc8;--accent2:#d6b35b;--hero:linear-gradient(140deg,rgba(4,60,45,.95),rgba(9,24,34,.92));",
        "midnight": "--bg:#080d1d;--card:#11162a;--line:#2954a3;--text:#f2f5ff;--muted:#aab4d8;--accent:#93c5fd;--accent2:#c084fc;--hero:linear-gradient(140deg,rgba(16,26,55,.96),rgba(8,13,29,.92));",
        "cinema": "--bg:#120909;--card:#211111;--line:#a85d28;--text:#fff6ed;--muted:#d1b9a0;--accent:#fbbf24;--accent2:#fb7185;--hero:linear-gradient(140deg,rgba(50,18,18,.95),rgba(16,13,25,.94));",
        "poster": "--bg:#111827;--card:#0b1220;--line:#465a7a;--text:#f8fafc;--muted:#b7c3d5;--accent:#f8fafc;--accent2:#38bdf8;--hero:linear-gradient(160deg,rgba(15,23,42,.88),rgba(0,0,0,.65));",
        "minimal": "--bg:#0b0f14;--card:#111820;--line:#2a3441;--text:#f1f5f9;--muted:#94a3b8;--accent:#e2e8f0;--accent2:#94a3b8;--hero:linear-gradient(140deg,rgba(17,24,32,.98),rgba(8,12,18,.96));",
        "neon": "--bg:#090817;--card:#121027;--line:#00e5ff;--text:#f3e8ff;--muted:#b7a9cf;--accent:#22d3ee;--accent2:#f472b6;--hero:linear-gradient(140deg,rgba(12,13,38,.98),rgba(24,3,34,.88));",
        "mono": "--bg:#101010;--card:#171717;--line:#4b5563;--text:#f5f5f5;--muted:#b3b3b3;--accent:#ffffff;--accent2:#c9c9c9;--hero:linear-gradient(140deg,rgba(25,25,25,.98),rgba(5,5,5,.92));",
        "editorial": "--bg:#100f0d;--card:#1f1b17;--line:#a16207;--text:#fff7ed;--muted:#d6c3ad;--accent:#f59e0b;--accent2:#fb7185;--hero:linear-gradient(130deg,rgba(55,38,20,.95),rgba(14,18,30,.92));",
        "lobby": "--bg:#0e1412;--card:#17211d;--line:#64748b;--text:#f8fafc;--muted:#a8b8b0;--accent:#eab308;--accent2:#22c55e;--hero:linear-gradient(140deg,rgba(25,33,29,.96),rgba(8,14,20,.92));",
        "vertical": "--bg:#0b1020;--card:#121a31;--line:#334155;--text:#eff6ff;--muted:#b6c5dc;--accent:#60a5fa;--accent2:#f97316;--hero:linear-gradient(180deg,rgba(18,26,49,.98),rgba(9,12,24,.94));",
        "terminal": "--bg:#030705;--card:#07110d;--line:#16a34a;--text:#dcfce7;--muted:#86efac;--accent:#22c55e;--accent2:#bef264;--hero:linear-gradient(140deg,rgba(5,18,12,.98),rgba(0,0,0,.94));",
        "magazine": "--bg:#14120f;--card:#201c18;--line:#d97706;--text:#fffaf0;--muted:#d8c4a8;--accent:#fbbf24;--accent2:#38bdf8;--hero:linear-gradient(120deg,rgba(36,28,21,.98),rgba(20,18,15,.92));",
        "split": "--bg:#0c1222;--card:#111827;--line:#475569;--text:#f8fafc;--muted:#cbd5e1;--accent:#93c5fd;--accent2:#f472b6;--hero:linear-gradient(90deg,rgba(15,23,42,.98),rgba(49,46,129,.78));",
        "archive": "--bg:#101010;--card:#191919;--line:#78716c;--text:#f5f5f4;--muted:#c7c0b8;--accent:#d6d3d1;--accent2:#f59e0b;--hero:linear-gradient(140deg,rgba(32,32,32,.98),rgba(16,16,16,.94));",
        "poster_focus": "--bg:#070a12;--card:#101827;--line:#334155;--text:#f8fafc;--muted:#b8c2d6;--accent:#e2e8f0;--accent2:#38bdf8;--hero:linear-gradient(160deg,rgba(12,18,30,.82),rgba(0,0,0,.72));",
        "timeline": "--bg:#0d0b13;--card:#171421;--line:#7c3aed;--text:#faf5ff;--muted:#c4b5fd;--accent:#c084fc;--accent2:#facc15;--hero:linear-gradient(125deg,rgba(35,24,61,.95),rgba(11,13,24,.94));",
        "timeline_noir": "--bg:#09070d;--card:#15111c;--line:#8b5cf6;--text:#fbf7ff;--muted:#c4b5fd;--accent:#a78bfa;--accent2:#f472b6;--hero:linear-gradient(125deg,rgba(32,24,52,.96),rgba(7,7,12,.95));",
        "timeline_amber": "--bg:#140c06;--card:#21170d;--line:#d97706;--text:#fff7ed;--muted:#fed7aa;--accent:#f59e0b;--accent2:#fde68a;--hero:linear-gradient(125deg,rgba(61,35,12,.96),rgba(14,10,7,.94));",
        "timeline_ocean": "--bg:#041017;--card:#0b1d29;--line:#0284c7;--text:#ecfeff;--muted:#a5f3fc;--accent:#38bdf8;--accent2:#5eead4;--hero:linear-gradient(125deg,rgba(9,45,64,.96),rgba(4,13,20,.94));",
    }
    return styles.get(style, styles["aurora"])


def _html_body_class(style: str) -> str:
    return f"prez-style-{_normalize_template_name(style, kind='html')}"


def _render_template(kind: str, template_name: str, locale: str, data: PrezData) -> str:
    template = _load_template(kind, template_name, locale)
    return template.render(data=data, template_name=template_name, locale=locale).rstrip() + "\n"


def render_bbcode(
    release: ReleaseNfoData,
    *,
    metadata_context: dict | None = None,
    screenshots: tuple[str, ...] = (),
    mediainfo_text: str | None = None,
    template_name: str = "classic",
    locale: str = "en",
    poster_url: str | None = None,
    banner_audio: str = "",
    banner_information: str = "",
    banner_metadata: str = "",
    banner_release: str = "",
    banner_subtitles: str = "",
    banner_synopsis: str = "",
    banner_technical: str = "",
) -> str:
    """Render bbcode."""
    del screenshots  # screenshots are intentionally not rendered in public prez outputs.
    normalized_locale = _normalize_locale(locale)
    with temporary_locale(normalized_locale):
        data = _build_prez_data(
            release,
            metadata_context=metadata_context,
            mediainfo_text=mediainfo_text,
            poster_url=poster_url,
            locale=normalized_locale,
            banner_audio=banner_audio,
            banner_information=banner_information,
            banner_metadata=banner_metadata,
            banner_release=banner_release,
            banner_subtitles=banner_subtitles,
            banner_synopsis=banner_synopsis,
            banner_technical=banner_technical,
        )
        return _render_template("bbcode", template_name, normalized_locale, data)


def render_html(
    release: ReleaseNfoData,
    *,
    metadata_context: dict | None = None,
    locale: str = "en",
    screenshots: tuple[str, ...] = (),
    mediainfo_text: str | None = None,
    template_name: str = "aurora",
    poster_url: str | None = None,
    banner_audio: str = "",
    banner_information: str = "",
    banner_metadata: str = "",
    banner_release: str = "",
    banner_subtitles: str = "",
    banner_synopsis: str = "",
    banner_technical: str = "",
) -> str:
    """Render html."""
    del screenshots  # screenshots are intentionally not rendered in public prez outputs.
    normalized_locale = _normalize_locale(locale)
    with temporary_locale(normalized_locale):
        data = _build_prez_data(
            release,
            metadata_context=metadata_context,
            mediainfo_text=mediainfo_text,
            poster_url=poster_url,
            locale=normalized_locale,
            banner_audio=banner_audio,
            banner_information=banner_information,
            banner_metadata=banner_metadata,
            banner_release=banner_release,
            banner_subtitles=banner_subtitles,
            banner_synopsis=banner_synopsis,
            banner_technical=banner_technical,
        )
        return _render_template("html", template_name, normalized_locale, data)


def _resolve_release_and_episodes(
    folder: Path, options: PrezBuildOptions
) -> tuple[ReleaseNfoData, list[EpisodeNfoData]]:
    if options.release is not None:
        return options.release, options.release.episodes
    episodes = scan_nfo_folder(folder)
    if not episodes:
        raise ValueError(
            tr(
                "nfo.error.no_mkv",
                default="No MKV files found in folder: {folder}",
                folder=folder,
            )
        )
    return build_release_nfo(folder, episodes), episodes


def _resolve_mediainfo_mode(options: PrezBuildOptions) -> str:
    mediainfo_mode = (options.mediainfo_mode or "none").strip().lower()
    if options.include_mediainfo and mediainfo_mode == "none":
        mediainfo_mode = "spoiler"
    if mediainfo_mode not in MEDIAINFO_MODES:
        return "none"
    return mediainfo_mode


def _resolve_mediainfo_text(
    folder: Path, release: ReleaseNfoData, options: PrezBuildOptions, mediainfo_mode: str
) -> str | None:
    if mediainfo_mode not in {"spoiler", "only"}:
        return options.mediainfo_text
    if options.mediainfo_text is not None:
        return options.mediainfo_text
    return _read_mediainfo_text(folder) or _generate_mediainfo_text(release)


def _resolve_render_plan(
    options: PrezBuildOptions, mediainfo_mode: str, html_template: str, bbcode_template: str
) -> list[tuple[str, str, str]]:
    if mediainfo_mode == "only":
        return [("mediainfo", ".mediainfo.txt", "")]
    return _render_plan_from_formats(options.formats, html_template, bbcode_template)


def _render_plan_from_formats(
    formats: Sequence[str], html_template: str, bbcode_template: str
) -> list[tuple[str, str, str]]:
    plan: list[tuple[str, str, str]] = []
    for fmt in formats:
        plan.append(_render_plan_item(fmt, html_template, bbcode_template))
    return plan


def _render_plan_item(fmt: str, html_template: str, bbcode_template: str) -> tuple[str, str, str]:
    if fmt == "html":
        return fmt, ".html", html_template
    if fmt == "bbcode":
        return fmt, ".bbcode.txt", bbcode_template
    raise ValueError(f"Unsupported prez format: {fmt}")


def _render_output_content(
    fmt: str,
    *,
    release: ReleaseNfoData,
    options: PrezBuildOptions,
    locale: str,
    mediainfo_text: str | None,
    template_name: str,
    poster_url: str | None,
) -> str:
    if fmt == "mediainfo":
        return mediainfo_text or ""
    if fmt == "html":
        return render_html(
            release,
            metadata_context=options.metadata_context,
            locale=locale,
            mediainfo_text=mediainfo_text,
            template_name=template_name,
            poster_url=poster_url,
            banner_audio=options.banner_audio,
            banner_information=options.banner_information,
            banner_metadata=options.banner_metadata,
            banner_release=options.banner_release,
            banner_subtitles=options.banner_subtitles,
            banner_synopsis=options.banner_synopsis,
            banner_technical=options.banner_technical,
        )
    return render_bbcode(
        release,
        metadata_context=options.metadata_context,
        mediainfo_text=mediainfo_text,
        template_name=template_name,
        locale=locale,
        poster_url=poster_url,
        banner_audio=options.banner_audio,
        banner_information=options.banner_information,
        banner_metadata=options.banner_metadata,
        banner_release=options.banner_release,
        banner_subtitles=options.banner_subtitles,
        banner_synopsis=options.banner_synopsis,
        banner_technical=options.banner_technical,
    )


def _render_outputs(
    *,
    release: ReleaseNfoData,
    options: PrezBuildOptions,
    write: bool,
    output_dir: Path,
    base_name: str,
    render_plan: Sequence[tuple[str, str, str]],
    locale: str,
    mediainfo_text: str | None,
    poster_url: str | None,
) -> list[Path]:
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    with temporary_locale(locale):
        for fmt, suffix, template_name in render_plan:
            output_stem = f"{base_name}.{template_name}" if template_name else base_name
            target = output_dir / f"{output_stem}{suffix}"
            rendered = _render_output_content(
                fmt,
                release=release,
                options=options,
                locale=locale,
                mediainfo_text=mediainfo_text,
                template_name=template_name,
                poster_url=poster_url,
            )
            if write:
                target.write_text(rendered, encoding="utf-8")
            outputs.append(target)
    return outputs


def _build_prez_report(
    *,
    folder: Path,
    episodes: Sequence[EpisodeNfoData],
    outputs: Sequence[Path],
    write: bool,
    render_plan: Sequence[tuple[str, str, str]],
    html_template: str,
    bbcode_template: str,
    mediainfo_mode: str,
) -> OperationReport:
    report = OperationReport(tool="prez")
    report.scanned = len(episodes)
    report.processed = len(episodes)
    report.modified = len(outputs) if write else 0
    report.outputs.extend(str(path) for path in outputs if write)
    report.add_detail(
        file=None,
        action="prez",
        status="written" if write else "planned",
        message=tr(
            "prez.message.written",
            default="Presentation generated." if write else "Presentation generation planned.",
        ),
        before={"folder": str(folder)},
        after={
            "outputs": [str(path) for path in outputs],
            "formats": [item[0] for item in render_plan],
            "html_template": html_template,
            "bbcode_template": bbcode_template,
            "mediainfo_mode": mediainfo_mode,
        },
    )
    return report


class PrezService:
    """Service for prez."""

    def build(
        self,
        folder: Path,
        *,
        options: PrezBuildOptions,
        write: bool = True,
    ) -> tuple[OperationReport, PrezBuildResult]:
        """Handle build."""
        release, episodes = _resolve_release_and_episodes(folder, options)
        output_dir = options.output_dir or folder
        base_name = _safe_output_name(release.release_title)
        mediainfo_mode = _resolve_mediainfo_mode(options)
        mediainfo_text = _resolve_mediainfo_text(folder, release, options, mediainfo_mode)
        poster_url = options.poster_url or _discover_local_poster(folder)
        html_template, bbcode_template = _apply_preset(options)
        render_plan = _resolve_render_plan(options, mediainfo_mode, html_template, bbcode_template)
        locale = _normalize_locale(options.locale)
        outputs = _render_outputs(
            release=release,
            options=options,
            write=write,
            output_dir=output_dir,
            base_name=base_name,
            render_plan=render_plan,
            locale=locale,
            mediainfo_text=mediainfo_text,
            poster_url=poster_url,
        )
        report = _build_prez_report(
            folder=folder,
            episodes=episodes,
            outputs=outputs,
            write=write,
            render_plan=render_plan,
            html_template=html_template,
            bbcode_template=bbcode_template,
            mediainfo_mode=mediainfo_mode,
        )
        return report, PrezBuildResult(release=release, outputs=tuple(outputs))
