from __future__ import annotations

# ruff: noqa: I001

import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

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
        """
        Sanitize a filename by replacing characters illegal on most filesystems.
        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


from framekit.core.i18n import temporary_locale, tr
from framekit.core.models.nfo import EpisodeNfoData, ReleaseNfoData, TrackNfoData
from framekit.core.reporting import OperationReport
from framekit.core.tools import ToolRegistry
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.formatting import format_bytes_human, format_duration_ms_human
from framekit.modules.nfo.scanner import scan_nfo_folder
from framekit.modules.prez.models import PrezData, PrezField, PrezTrack

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
HTML_TEMPLATE_NAMES = (
    "aurora",
    "emerald",
    "midnight",
    "cinema",
    "poster",
    "minimal",
    "neon",
    "mono",
    "editorial",
    "lobby",
    "vertical",
    "terminal",
    "magazine",
    "split",
    "dossier",
    "poster_focus",
    "timeline",
    "timeline_noir",
    "timeline_amber",
    "timeline_ocean",
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
HTML_STYLE_ALIASES = {
    "default": "aurora",
    "premium": "poster_focus",
    "tracker": "aurora",
    "poster-focus": "poster_focus",
    "timeline-noir": "timeline_noir",
    "timeline-amber": "timeline_amber",
    "timeline-ocean": "timeline_ocean",
}
BBCODE_STYLE_ALIASES = {"default": "classic", "premium": "cinematic"}
PREZ_PRESETS: dict[str, dict[str, str]] = {
    "default": {
        "format": "both",
        "html_template": "aurora",
        "bbcode_template": "classic",
        "mediainfo_mode": "none",
        "detail_level": "standard",
        "show_tmdb": "true",
        "show_mediainfo": "false",
    },
    "tracker": {
        "format": "bbcode",
        "html_template": "dossier",
        "bbcode_template": "tracker",
        "mediainfo_mode": "spoiler",
        "detail_level": "tracker",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "compact": {
        "format": "bbcode",
        "html_template": "minimal",
        "bbcode_template": "compact",
        "mediainfo_mode": "none",
        "detail_level": "compact",
        "show_tmdb": "true",
        "show_mediainfo": "false",
    },
    "detailed": {
        "format": "both",
        "html_template": "editorial",
        "bbcode_template": "detailed",
        "mediainfo_mode": "spoiler",
        "detail_level": "detailed",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "technical": {
        "format": "both",
        "html_template": "terminal",
        "bbcode_template": "technical",
        "mediainfo_mode": "spoiler",
        "detail_level": "technical",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "premium": {
        "format": "both",
        "html_template": "poster_focus",
        "bbcode_template": "cinematic",
        "mediainfo_mode": "spoiler",
        "detail_level": "premium",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "timeline": {
        "format": "both",
        "html_template": "timeline",
        "bbcode_template": "detailed",
        "mediainfo_mode": "spoiler",
        "detail_level": "timeline",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "timeline_noir": {
        "format": "both",
        "html_template": "timeline_noir",
        "bbcode_template": "detailed",
        "mediainfo_mode": "spoiler",
        "detail_level": "timeline",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "timeline_amber": {
        "format": "both",
        "html_template": "timeline_amber",
        "bbcode_template": "detailed",
        "mediainfo_mode": "spoiler",
        "detail_level": "timeline",
        "show_tmdb": "true",
        "show_mediainfo": "true",
    },
    "timeline_ocean": {
        "format": "both",
        "html_template": "timeline_ocean",
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


@dataclass(frozen=True, slots=True)
class PrezBuildResult:
    release: ReleaseNfoData
    outputs: tuple[Path, ...]


def available_html_templates() -> tuple[str, ...]:
    return HTML_TEMPLATE_NAMES


def available_bbcode_templates() -> tuple[str, ...]:
    return BBCODE_TEMPLATE_NAMES


def available_prez_presets() -> tuple[str, ...]:
    return tuple(PREZ_PRESETS)


HTML_TEMPLATE_DESCRIPTIONS = {
    "aurora": "Balanced card layout with blue-green accents.",
    "emerald": "Premium green card layout for polished general releases.",
    "midnight": "Dark cinematic cards with blue highlights.",
    "cinema": "Warm theatrical cards for movie-style releases.",
    "poster": "Poster-led cards with compact metadata.",
    "minimal": "Sober compact cards with low visual noise.",
    "neon": "High-contrast neon presentation.",
    "mono": "Monochrome technical card layout.",
    "editorial": "Editorial long-form layout with a magazine feel.",
    "lobby": "Streaming-lobby organization with strong release focus.",
    "vertical": "Vertical reading flow for detailed presentations.",
    "terminal": "Technical console-style organization.",
    "magazine": "Magazine-style editorial spread.",
    "split": "Split hero layout for poster and metadata balance.",
    "dossier": "Structured dossier for complete release details.",
    "poster_focus": "Premium poster-first layout.",
    "timeline": "Timeline layout with balanced poster block.",
    "timeline_noir": "Timeline layout with noir violet accents.",
    "timeline_amber": "Timeline layout with warm amber accents.",
    "timeline_ocean": "Timeline layout with blue ocean accents.",
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

HTML_TEMPLATE_CATEGORIES = {
    "aurora": "Boxes",
    "emerald": "Boxes",
    "midnight": "Boxes",
    "cinema": "Boxes",
    "poster": "Boxes",
    "minimal": "Boxes",
    "neon": "Boxes",
    "mono": "Boxes",
    "editorial": "Vertical",
    "lobby": "Vertical",
    "vertical": "Vertical",
    "terminal": "Vertical",
    "magazine": "Vertical",
    "split": "Vertical",
    "dossier": "Vertical",
    "poster_focus": "Vertical",
    "timeline": "Timeline",
    "timeline_noir": "Timeline",
    "timeline_amber": "Timeline",
    "timeline_ocean": "Timeline",
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


def describe_html_template(name: str) -> str:
    normalized = _normalize_template_name(name, kind="html")
    return HTML_TEMPLATE_DESCRIPTIONS.get(normalized, normalized)


def describe_bbcode_template(name: str) -> str:
    normalized = _normalize_template_name(name, kind="bbcode")
    return BBCODE_TEMPLATE_DESCRIPTIONS.get(normalized, normalized)


def template_category(name: str, *, kind: str) -> str:
    if kind == "html":
        return HTML_TEMPLATE_CATEGORIES.get(_normalize_template_name(name, kind=kind), "Other")
    return BBCODE_TEMPLATE_CATEGORIES.get(_normalize_template_name(name, kind=kind), "Other")


def _normalize_locale(locale: str | None) -> str:
    value = (locale or "en").strip().lower().split("-", 1)[0]
    return value if value in PREZ_LOCALES else "en"


def _normalize_template_name(name: str | None, *, kind: str) -> str:
    raw = (name or "").strip().lower().replace("-", "_")
    if kind == "html":
        raw = HTML_STYLE_ALIASES.get(raw, raw)
        return raw if raw in HTML_TEMPLATE_NAMES else "aurora"
    raw = BBCODE_STYLE_ALIASES.get(raw, raw)
    return raw if raw in BBCODE_TEMPLATE_NAMES else "classic"


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


def _metadata_title(context: dict | None, release: ReleaseNfoData | None = None) -> str | None:
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
    return isinstance(value, str) and "themoviedb.org" in value


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
        title = _metadata_attr(metadata, "title") or release.title_display or release.release_title
        return _dash(title), "-"

    series_title = (
        _metadata_attr(metadata, "series_title")
        or release.series_title
        or release.title_display
        or release.release_title
    )
    episode_title = "-"
    if release.media_kind == "single_episode":
        first = _first_episode(release)
        episode_title = (
            _metadata_attr(metadata, "episode_title")
            or (first.episode_title if first else None)
            or "-"
        )
    return _dash(series_title), _dash(episode_title)


def _season_episode(release: ReleaseNfoData) -> str:
    if release.media_kind == "movie":
        return "-"

    codes = [episode.episode_code.upper() for episode in release.episodes if episode.episode_code]
    if not codes:
        return release.season or "-"

    if release.media_kind == "single_episode" or len(codes) == 1:
        return codes[0]

    seasons = {code[:3] for code in codes if code.startswith("S") and "E" in code}
    if len(seasons) == 1:
        season = next(iter(seasons))
        episode_numbers: list[int] = []
        for code in codes:
            try:
                episode_numbers.append(int(code.split("E", 1)[1]))
            except (IndexError, ValueError):
                continue
        if episode_numbers:
            return f"{season}E{min(episode_numbers):02d}-{season}E{max(episode_numbers):02d}"
        return season

    return ", ".join(codes)


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
        except Exception:
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

    local_minutes = [
        round(episode.duration_ms / 60_000)
        for episode in release.episodes
        if episode.duration_ms and episode.duration_ms > 0
    ]
    if local_minutes:
        return _format_runtime_minutes(round(sum(local_minutes) / len(local_minutes)))

    release_codes = {episode.episode_code for episode in release.episodes if episode.episode_code}
    metadata_minutes: list[int] = []
    for episode in getattr(metadata, "episode_summaries", []) or []:
        code = _episode_code_from_metadata(episode)
        runtime = getattr(episode, "runtime_minutes", None)
        if runtime and (not release_codes or code in release_codes):
            metadata_minutes.append(runtime)

    if metadata_minutes:
        return _format_runtime_minutes(round(sum(metadata_minutes) / len(metadata_minutes)))

    runtime = _runtime_minutes_from_metadata(metadata)
    return _format_runtime_minutes(runtime)


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

    results: list[tuple[TrackNfoData, str | None]] = []
    for track, indexes, codes in by_key.values():
        suffix = _episode_suffix(codes) if episode_count and len(indexes) < episode_count else ""
        results.append((track, suffix or None))
    return tuple(results)


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
    for value in (
        release.resolution,
        release.source,
        release.video_tag,
        _format_audio_summary(release),
        release.language_tag,
        release.hdr_display,
    ):
        if value:
            parts.append(str(value))
    parts.append(format_bytes_human(release.total_size_bytes))
    return " · ".join(part for part in parts if part and part != "-")


def _country_from_language(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("_", "-")
    if not normalized:
        return None
    if "(" in normalized and ")" in normalized:
        region = normalized.split("(", 1)[1].split(")", 1)[0].strip().lower()
        if len(region) == 2:
            return "gb" if region == "uk" else region
    if normalized in _FLAG_BY_LANGUAGE:
        return _FLAG_BY_LANGUAGE[normalized]
    if "-" in normalized and len(normalized.split("-", 1)[1]) == 2:
        region = normalized.split("-", 1)[1]
        return "gb" if region == "uk" else region
    if len(normalized) == 2:
        return "gb" if normalized == "en" else normalized
    return None


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


def _build_prez_data(
    release: ReleaseNfoData,
    *,
    metadata_context: dict | None,
    mediainfo_text: str | None = None,
    poster_url: str | None = None,
    locale: str | None = None,
) -> PrezData:
    metadata = _metadata_object(metadata_context, release)
    first = _first_episode(release)
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
    selected_poster_url = _metadata_attr(metadata, "poster_url", "still_url") or poster_url

    runtime_field = (
        _field(
            "average_runtime",
            "prez.label.average_runtime",
            "Average runtime per episode",
            average_runtime,
        )
        if release.media_kind == "season_pack"
        else _field("runtime", "prez.label.runtime", "Runtime", runtime)
    )

    info_fields = _fields(
        (
            _field("title", "prez.label.title", "Title", title, wide=True),
            _field(
                "episode_title",
                "prez.label.episode_title",
                "Episode title",
                heading_subtitle,
                wide=True,
            ),
            _field(
                "original_title",
                "prez.label.original_title",
                "Original title",
                original_title,
                wide=True,
            ),
            _field(
                "season_episode", "prez.label.season_episode", "Season / Episode", season_episode
            ),
            _field(
                "genres",
                "prez.label.genres",
                "Genres",
                genres,
                wide=True,
            ),
            _field(
                "episode_completeness",
                "prez.label.episode_completeness",
                "Episode completeness",
                release.episode_completeness
                if release.media_kind in {"single_episode", "season_pack", "special_pack"}
                else None,
                wide=bool(release.missing_episode_codes),
            ),
            _field(
                "release_date",
                "prez.label.release_date",
                "Release date",
                release_date,
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
    metadata_fields = _fields((_field("rating", "prez.label.rating", "Rating", rating),))
    metadata_fields = metadata_fields + _tmdb_fields(metadata, release)
    release_fields = _fields(
        (
            _field("team", "prez.label.team", "Team", release.team),
            _field("release", "prez.label.release", "Release", release.release_title, wide=True),
            _field("file_size", "prez.label.file_size", "Size", file_size),
            _field(
                "files_count",
                "prez.label.files_count",
                "Files count",
                str(len(release.episodes) or 1),
            ),
        )
    )
    video_fields = _fields(
        (
            _field("source", "prez.label.source", "Source", release.source),
            _field(
                "resolution",
                "prez.label.resolution",
                "Resolution",
                release.resolution or (first.resolution if first else None),
            ),
            _field(
                "video_codec",
                "prez.label.video_codec",
                "Video codec",
                release.video_tag or (first.video_codec if first else None),
            ),
            _field(
                "video_bitrate",
                "prez.label.average_video_bitrate"
                if release.media_kind == "season_pack"
                else "prez.label.video_bitrate",
                "Average video bitrate" if release.media_kind == "season_pack" else "Video bitrate",
                video_bitrate,
            ),
            _field(
                "aspect_ratio",
                "prez.label.aspect_ratio",
                "Aspect ratio",
                first.aspect_ratio_display or first.aspect_ratio if first else None,
            ),
            _field(
                "hdr",
                "prez.label.hdr",
                "HDR",
                release.hdr_display or (first.hdr_display if first else None),
            ),
        )
    )

    badges: tuple[str, ...] = tuple(
        item
        for item in (
            season_episode,
            release.resolution,
            release.source,
            release.video_tag,
            release.audio_tag,
            release.language_tag,
            file_size,
        )
        if isinstance(item, str) and _has_value(item)
    )

    return PrezData(
        release=release,
        title=display_title,
        original_title=_dash(original_title),
        year=_dash(year),
        heading_title=_dash(heading_title),
        heading_subtitle=_dash(heading_subtitle),
        season_label=season_label,
        season_episode=season_episode,
        season_episode_range=season_episode_range,
        subtitle_line=" · ".join(
            item
            for item in (
                "-" if release.media_kind == "season_pack" else _dash(year),
                average_runtime if release.media_kind == "season_pack" else runtime,
                genres,
            )
            if item != "-"
        ),
        poster_url=_dash(selected_poster_url),
        overview=_dash(getattr(metadata, "overview", None)),
        technical_summary=technical_summary,
        release_name=_dash(release.release_title),
        team=_dash(release.team),
        file_size=file_size,
        files_count=str(len(release.episodes) or 1),
        source=_dash(release.source),
        resolution=_dash(release.resolution or (first.resolution if first else None)),
        video_codec=_dash(release.video_tag or (first.video_codec if first else None)),
        video_bitrate=video_bitrate,
        aspect_ratio=_dash(first.aspect_ratio_display or first.aspect_ratio if first else None),
        hdr=_dash(release.hdr_display or (first.hdr_display if first else None)),
        tmdb_id=tmdb_id,
        tmdb_url=_dash(tmdb_url),
        imdb_id="-",
        rating=rating,
        cast=_join_list(getattr(metadata, "cast", None)),
        crew=_join_list(getattr(metadata, "crew", None)),
        mediainfo_text=mediainfo_text.strip() if mediainfo_text else None,
        info_fields=info_fields,
        metadata_fields=metadata_fields,
        release_fields=release_fields,
        video_fields=video_fields,
        audio_tracks=tuple(
            _to_prez_audio_track(track) for track in _unique_tracks(release.episodes, "audio")
        ),
        subtitle_tracks=tuple(
            _to_prez_subtitle_track(track, suffix)
            for track, suffix in _unique_subtitle_tracks(release)
        ),
        badges=badges,
    )


def _discover_screenshots(folder: Path) -> tuple[str, ...]:
    candidates: list[Path] = []
    for child in folder.iterdir() if folder.exists() else []:
        if child.is_dir() and child.name.lower() in SCREENSHOT_DIR_NAMES:
            candidates.extend(
                sorted(
                    path
                    for path in child.iterdir()
                    if path.is_file() and path.suffix.lower() in SCREENSHOT_SUFFIXES
                )
            )
        elif child.is_file() and child.suffix.lower() in SCREENSHOT_SUFFIXES:
            lowered = child.stem.lower()
            if lowered.startswith(("screen", "screenshot", "capture", "thumb")):
                candidates.append(child)
    return tuple(str(path) for path in candidates[:12])


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
    registry = registry or ToolRegistry()
    binary = registry.resolve_tool_path("mediainfo")
    if not binary:
        return None

    sections: list[str] = []
    for episode in release.episodes:
        try:
            result = subprocess.run(
                [binary, str(episode.file_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = (result.stdout or result.stderr or "").strip()
        if output:
            sections.append(f"===== {episode.file_name} =====\n{output}")
    return "\n\n".join(sections).strip() or None


def _template_environment(kind: str) -> Environment:
    env = Environment(
        loader=PackageLoader("framekit", f"templates/prez/{kind}"),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"))
        if kind == "html"
        else False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        tr=tr,
        dash=_dash,
        bb=_bbcode_escape,
        html_escape=escape,
        field_url_bbcode=_field_url_bbcode,
        field_url_html=_field_url_html,
        audio_table_bbcode=_render_audio_tracks_bbcode,
        subtitle_table_bbcode=_render_subtitle_tracks_bbcode,
        audio_table_html=_render_audio_tracks_html,
        subtitle_table_html=_render_subtitle_tracks_html,
        mediainfo_spoiler=_render_mediainfo_spoiler,
        style_css=_html_style_css,
        body_class=_html_body_class,
    )
    return env


def _load_template(kind: str, name: str, locale: str):
    normalized = _normalize_template_name(name, kind=kind)
    normalized_locale = _normalize_locale(locale)
    env = _template_environment(kind)
    candidates = (f"{normalized}.{normalized_locale}.jinja2", f"{normalized}.en.jinja2")
    for candidate in candidates:
        try:
            return env.get_template(candidate)
        except Exception:
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


def _render_audio_tracks_bbcode(tracks: Sequence[PrezTrack]) -> str:
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
    if not tracks:
        return header + "\n[tr][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][/tr]\n[/table]"
    rows = [
        "[tr]"
        f"[td]{_track_language_bbcode(track)}[/td]"
        f"[td]{_bbcode_escape(track.codec)}[/td]"
        f"[td]{_bbcode_escape(track.channels)}[/td]"
        f"[td]{_bbcode_escape(track.bitrate)}[/td]"
        f"[td]{_bbcode_escape(track.is_default)}[/td]"
        "[/tr]"
        for track in tracks
    ]
    return header + "\n" + "\n".join(rows) + "\n[/table]"


def _render_subtitle_tracks_bbcode(tracks: Sequence[PrezTrack]) -> str:
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
    if not tracks:
        return header + "\n[tr][td]-[/td][td]-[/td][td]-[/td][td]-[/td][td]-[/td][/tr]\n[/table]"
    rows = [
        "[tr]"
        f"[td]{_track_language_bbcode(track)}[/td]"
        f"[td]{_bbcode_escape(track.variant)}[/td]"
        f"[td]{_bbcode_escape(track.format_name)}[/td]"
        f"[td]{_bbcode_escape(track.is_default)}[/td]"
        f"[td]{_bbcode_escape(track.is_forced)}[/td]"
        "[/tr]"
        for track in tracks
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


def _html_style_css(style: str) -> str:
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
        "dossier": "--bg:#101010;--card:#191919;--line:#78716c;--text:#f5f5f4;--muted:#c7c0b8;--accent:#d6d3d1;--accent2:#f59e0b;--hero:linear-gradient(140deg,rgba(32,32,32,.98),rgba(16,16,16,.94));",
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
) -> str:
    del screenshots  # screenshots are intentionally not rendered in public prez outputs.
    normalized_locale = _normalize_locale(locale)
    with temporary_locale(normalized_locale):
        data = _build_prez_data(
            release,
            metadata_context=metadata_context,
            mediainfo_text=mediainfo_text,
            poster_url=poster_url,
            locale=normalized_locale,
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
) -> str:
    del screenshots  # screenshots are intentionally not rendered in public prez outputs.
    normalized_locale = _normalize_locale(locale)
    with temporary_locale(normalized_locale):
        data = _build_prez_data(
            release,
            metadata_context=metadata_context,
            mediainfo_text=mediainfo_text,
            poster_url=poster_url,
            locale=normalized_locale,
        )
        return _render_template("html", template_name, normalized_locale, data)


class PrezService:
    def build(
        self,
        folder: Path,
        *,
        options: PrezBuildOptions,
        write: bool = True,
    ) -> tuple[OperationReport, PrezBuildResult]:
        if options.release is not None:
            release = options.release
            episodes = release.episodes
        else:
            episodes = scan_nfo_folder(folder)
            if not episodes:
                raise ValueError(
                    tr(
                        "nfo.error.no_mkv",
                        default="No MKV files found in folder: {folder}",
                        folder=folder,
                    )
                )
            release = build_release_nfo(folder, episodes)
        output_dir = options.output_dir or folder
        base_name = _safe_output_name(release.release_title)
        outputs: list[Path] = []
        mediainfo_mode = (options.mediainfo_mode or "none").strip().lower()
        if options.include_mediainfo and mediainfo_mode == "none":
            mediainfo_mode = "spoiler"
        if mediainfo_mode not in MEDIAINFO_MODES:
            mediainfo_mode = "none"

        mediainfo_text = options.mediainfo_text
        if mediainfo_mode in {"spoiler", "only"} and mediainfo_text is None:
            mediainfo_text = _read_mediainfo_text(folder) or _generate_mediainfo_text(release)

        poster_url = options.poster_url or _discover_local_poster(folder)
        html_template, bbcode_template = _apply_preset(options)
        render_plan: list[tuple[str, str, str]] = []
        if mediainfo_mode == "only":
            render_plan.append(("mediainfo", ".mediainfo.txt", ""))
        else:
            for fmt in options.formats:
                if fmt == "html":
                    render_plan.append((fmt, ".html", html_template))
                elif fmt == "bbcode":
                    render_plan.append((fmt, ".bbcode.txt", bbcode_template))
                else:
                    raise ValueError(f"Unsupported prez format: {fmt}")

        if write:
            output_dir.mkdir(parents=True, exist_ok=True)

        locale = _normalize_locale(options.locale)
        with temporary_locale(locale):
            for fmt, suffix, template_name in render_plan:
                output_stem = f"{base_name}.{template_name}" if template_name else base_name
                target = output_dir / f"{output_stem}{suffix}"
                if fmt == "mediainfo":
                    rendered = mediainfo_text or ""
                elif fmt == "html":
                    rendered = render_html(
                        release,
                        metadata_context=options.metadata_context,
                        locale=locale,
                        mediainfo_text=mediainfo_text,
                        template_name=template_name,
                        poster_url=poster_url,
                    )
                else:
                    rendered = render_bbcode(
                        release,
                        metadata_context=options.metadata_context,
                        mediainfo_text=mediainfo_text,
                        template_name=template_name,
                        locale=locale,
                        poster_url=poster_url,
                    )
                if write:
                    target.write_text(rendered, encoding="utf-8")
                outputs.append(target)

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
        return report, PrezBuildResult(release=release, outputs=tuple(outputs))
