"""Metadata extraction from release names and NFO files.

Parses release names to extract technical metadata and parses NFO files
to extract IDs and additional information.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class ParsedRelease:
    """Parsed release name with extracted metadata."""

    title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    resolution: str | None = None
    source: str | None = None
    codec: str | None = None
    audio: str | None = None
    hdr: str | None = None
    group: str | None = None

    # Confidence scores for each field (0.0-1.0)
    confidence: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize confidence scores."""
        if not self.confidence:
            self.confidence = {}


@dataclass
class NFOData:
    """Parsed NFO file data."""

    imdb_id: str | None = None
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    title: str | None = None
    year: int | None = None
    genre: list[str] = field(default_factory=list)
    synopsis: str | None = None

    # Additional metadata
    director: str | None = None
    cast: list[str] = field(default_factory=list)
    runtime: int | None = None
    rating: float | None = None


class ReleaseParser:
    """Parser for extracting metadata from release names."""

    # Resolution patterns
    RESOLUTION_PATTERNS = {
        "2160p": re.compile(r"\b(2160p|4k|uhd)\b", re.IGNORECASE),
        "1080p": re.compile(r"\b1080p\b", re.IGNORECASE),
        "1080i": re.compile(r"\b1080i\b", re.IGNORECASE),
        "720p": re.compile(r"\b720p\b", re.IGNORECASE),
        "576p": re.compile(r"\b576p\b", re.IGNORECASE),
        "480p": re.compile(r"\b480p\b", re.IGNORECASE),
    }

    # Source patterns
    SOURCE_PATTERNS = {
        "BluRay": re.compile(r"\b(bluray|blu-ray|bdrip|brrip)\b", re.IGNORECASE),
        "REMUX": re.compile(r"\bremux\b", re.IGNORECASE),
        "WEB-DL": re.compile(r"\b(web-dl|webdl)\b", re.IGNORECASE),
        "WEBRip": re.compile(r"\bwebrip\b", re.IGNORECASE),
        "HDTV": re.compile(r"\b(hdtv|pdtv)\b", re.IGNORECASE),
        "DVD": re.compile(r"\b(dvd|dvdrip)\b", re.IGNORECASE),
    }

    # Codec patterns
    CODEC_PATTERNS = {
        "x265": re.compile(r"\b(x265|h\.?265|hevc)\b", re.IGNORECASE),
        "x264": re.compile(r"\b(x264|h\.?264|avc)\b", re.IGNORECASE),
        "XviD": re.compile(r"\bxvid\b", re.IGNORECASE),
        "AV1": re.compile(r"\bav1\b", re.IGNORECASE),
    }

    # Audio patterns
    AUDIO_PATTERNS = {
        "Atmos": re.compile(r"\batmos\b", re.IGNORECASE),
        "TrueHD": re.compile(r"\btruehd\b", re.IGNORECASE),
        "DTS-HD MA": re.compile(r"\bdts-hd\.?ma\b", re.IGNORECASE),
        "DTS-HD": re.compile(r"\bdts-hd\b", re.IGNORECASE),
        "DTS": re.compile(r"\bdts\b", re.IGNORECASE),
        "DD+": re.compile(r"\b(dd\+|ddp|e-?ac-?3)\b", re.IGNORECASE),
        "DD": re.compile(r"\b(dd|ac-?3)\b", re.IGNORECASE),
        "AAC": re.compile(r"\baac\b", re.IGNORECASE),
        "FLAC": re.compile(r"\bflac\b", re.IGNORECASE),
        "MP3": re.compile(r"\bmp3\b", re.IGNORECASE),
    }

    # HDR patterns
    HDR_PATTERNS = {
        "HDR10+": re.compile(r"\bhdr10\+\b", re.IGNORECASE),
        "HDR10": re.compile(r"\bhdr10\b", re.IGNORECASE),
        "HDR": re.compile(r"\bhdr\b", re.IGNORECASE),
        "DV": re.compile(r"\b(dv|dolby\.?vision)\b", re.IGNORECASE),
        "HLG": re.compile(r"\bhlg\b", re.IGNORECASE),
    }

    # Year pattern
    YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")

    # Season/Episode patterns
    SEASON_EPISODE_PATTERN = re.compile(r"\bs(\d{1,2})e(\d{1,2})\b", re.IGNORECASE)
    SEASON_PATTERN = re.compile(r"\bs(\d{1,2})\b", re.IGNORECASE)

    # Group pattern (usually at the end after a dash)
    GROUP_PATTERN = re.compile(r"-([A-Za-z0-9]+)$")

    @classmethod
    def parse(cls, release_name: str) -> ParsedRelease:
        """Parse release name to extract metadata.

        Args:
            release_name: Release name to parse

        Returns:
            ParsedRelease with extracted metadata and confidence scores
        """
        result = ParsedRelease()
        cls._extract_technical_tags(release_name, result)
        cls._extract_temporal_tags(release_name, result)
        cls._extract_group_tag(release_name, result)
        cls._extract_title(release_name, result)
        cls._log_parse_result(release_name, result)
        return result

    @classmethod
    def _extract_technical_tags(cls, release_name: str, result: ParsedRelease) -> None:
        result.resolution = cls._first_match_key(release_name, cls.RESOLUTION_PATTERNS)
        cls._set_confidence_if_present(result, "resolution", result.resolution)

        result.source = cls._first_match_key(release_name, cls.SOURCE_PATTERNS)
        cls._set_confidence_if_present(result, "source", result.source)

        result.codec = cls._first_match_key(release_name, cls.CODEC_PATTERNS)
        cls._set_confidence_if_present(result, "codec", result.codec)

        result.audio = cls._first_match_key(release_name, cls.AUDIO_PATTERNS)
        cls._set_confidence_if_present(result, "audio", result.audio)

        result.hdr = cls._first_match_key(release_name, cls.HDR_PATTERNS)
        cls._set_confidence_if_present(result, "hdr", result.hdr)

    @classmethod
    def _extract_temporal_tags(cls, release_name: str, result: ParsedRelease) -> None:
        year_match = cls.YEAR_PATTERN.search(release_name)
        if year_match:
            result.year = int(year_match.group(1))
            result.confidence["year"] = 1.0

        season, episode, confidence = cls._parse_season_episode(release_name)
        if season is not None:
            result.season = season
            result.confidence["season"] = confidence
        if episode is not None:
            result.episode = episode
            result.confidence["episode"] = 1.0

    @classmethod
    def _extract_group_tag(cls, release_name: str, result: ParsedRelease) -> None:
        group_match = cls.GROUP_PATTERN.search(release_name)
        if group_match:
            result.group = group_match.group(1)
            result.confidence["group"] = 1.0

    @classmethod
    def _extract_title(cls, release_name: str, result: ParsedRelease) -> None:
        title = cls._clean_title(release_name, result)
        if title:
            result.title = title
            result.confidence["title"] = 0.7

    @classmethod
    def _first_match_key(
        cls, release_name: str, patterns: dict[str, re.Pattern[str]]
    ) -> str | None:
        for name, pattern in patterns.items():
            if pattern.search(release_name):
                return name
        return None

    @staticmethod
    def _set_confidence_if_present(result: ParsedRelease, key: str, value: str | None) -> None:
        if value:
            result.confidence[key] = 1.0

    @classmethod
    def _parse_season_episode(cls, release_name: str) -> tuple[int | None, int | None, float]:
        se_match = cls.SEASON_EPISODE_PATTERN.search(release_name)
        if se_match:
            return int(se_match.group(1)), int(se_match.group(2)), 1.0

        s_match = cls.SEASON_PATTERN.search(release_name)
        if s_match:
            return int(s_match.group(1)), None, 0.8
        return None, None, 0.0

    @classmethod
    def _clean_title(cls, release_name: str, result: ParsedRelease) -> str:
        title = release_name
        if result.group:
            title = title.rsplit("-", 1)[0]

        title = cls._remove_technical_tags(title)
        title = cls._remove_temporal_tags(title, result)
        return cls._normalize_title(title)

    @classmethod
    def _remove_technical_tags(cls, title: str) -> str:
        for pattern_dict in (
            cls.RESOLUTION_PATTERNS,
            cls.SOURCE_PATTERNS,
            cls.CODEC_PATTERNS,
            cls.AUDIO_PATTERNS,
            cls.HDR_PATTERNS,
        ):
            for pattern in pattern_dict.values():
                title = pattern.sub("", title)
        return title

    @classmethod
    def _remove_temporal_tags(cls, title: str, result: ParsedRelease) -> str:
        if result.year:
            title = title.replace(str(result.year), "")
        if result.season is not None:
            title = cls.SEASON_EPISODE_PATTERN.sub("", title)
            title = cls.SEASON_PATTERN.sub("", title)
        return title

    @staticmethod
    def _normalize_title(title: str) -> str:
        title = re.sub(r"[._]", " ", title)
        title = re.sub(r"\s+", " ", title)
        return title.strip(" -.")

    @staticmethod
    def _log_parse_result(release_name: str, result: ParsedRelease) -> None:
        logger.debug(f"Parsed release: {release_name}")
        logger.debug(f"  Title: {result.title}")
        logger.debug(f"  Year: {result.year}")
        logger.debug(f"  Resolution: {result.resolution}")
        logger.debug(f"  Source: {result.source}")
        logger.debug(f"  Codec: {result.codec}")
        logger.debug(f"  Audio: {result.audio}")
        logger.debug(f"  HDR: {result.hdr}")
        logger.debug(f"  Group: {result.group}")
        return


class NFOParser:
    """Parser for extracting metadata from NFO files."""

    # ID patterns
    IMDB_PATTERN = re.compile(r"imdb\.com/title/(tt\d+)", re.IGNORECASE)
    TMDB_PATTERN = re.compile(r"themoviedb\.org/(?:movie|tv)/(\d+)", re.IGNORECASE)
    TVDB_PATTERN = re.compile(r"thetvdb\.com/.*?series/(\d+)", re.IGNORECASE)

    # Alternative ID patterns
    IMDB_ID_PATTERN = re.compile(r"\b(tt\d{7,})\b", re.IGNORECASE)
    TMDB_ID_PATTERN = re.compile(r"tmdb[:\s]+(\d+)", re.IGNORECASE)
    TVDB_ID_PATTERN = re.compile(r"tvdb[:\s]+(\d+)", re.IGNORECASE)

    # Metadata patterns
    YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
    TITLE_PATTERN = re.compile(r"^(?:title|name)[:\s]+(.+)$", re.IGNORECASE | re.MULTILINE)
    GENRE_PATTERN = re.compile(r"genre[s]?[:\s]+(.+)$", re.IGNORECASE | re.MULTILINE)
    DIRECTOR_PATTERN = re.compile(r"director[:\s]+(.+)$", re.IGNORECASE | re.MULTILINE)
    RUNTIME_PATTERN = re.compile(r"runtime[:\s]+(\d+)", re.IGNORECASE)
    RATING_PATTERN = re.compile(r"rating[:\s]+([\d.]+)", re.IGNORECASE)

    @classmethod
    def parse(cls, nfo_path: Path | str) -> NFOData:
        """Parse NFO file to extract metadata.

        Args:
            nfo_path: Path to NFO file

        Returns:
            NFOData with extracted metadata
        """
        result = NFOData()

        if not nfo_path:
            return result

        nfo_path = Path(nfo_path)
        if not nfo_path.exists():
            logger.warning(f"NFO file not found: {nfo_path}")
            return result

        try:
            content = nfo_path.read_text(encoding="utf-8", errors="ignore")
            cls._extract_ids(content, result)
            cls._extract_metadata(content, result)
            cls._extract_synopsis(content, result)
            cls._log_nfo_result(nfo_path, result)

        except Exception as e:
            logger.error(f"Failed to parse NFO file {nfo_path}: {e}")

        return result

    @classmethod
    def _extract_ids(cls, content: str, result: NFOData) -> None:
        result.imdb_id = cls._match_first(content, cls.IMDB_PATTERN, cls.IMDB_ID_PATTERN)
        result.tmdb_id = cls._match_first_int(content, cls.TMDB_PATTERN, cls.TMDB_ID_PATTERN)
        result.tvdb_id = cls._match_first_int(content, cls.TVDB_PATTERN, cls.TVDB_ID_PATTERN)

    @classmethod
    def _extract_metadata(cls, content: str, result: NFOData) -> None:
        result.title = cls._match_line_value(content, cls.TITLE_PATTERN)
        result.director = cls._match_line_value(content, cls.DIRECTOR_PATTERN)
        result.year = cls._match_first_int(content, cls.YEAR_PATTERN)
        result.runtime = cls._match_first_int(content, cls.RUNTIME_PATTERN)
        result.rating = cls._match_first_float(content, cls.RATING_PATTERN)
        result.genre = cls._extract_genres(content)

    @classmethod
    def _extract_genres(cls, content: str) -> list[str]:
        genre_match = cls.GENRE_PATTERN.search(content)
        if not genre_match:
            return []
        genres = genre_match.group(1).strip()
        return [genre.strip() for genre in re.split(r"[,/|]", genres) if genre.strip()]

    @classmethod
    def _extract_synopsis(cls, content: str, result: NFOData) -> None:
        for pattern in cls._synopsis_patterns():
            synopsis_match = pattern.search(content)
            if not synopsis_match:
                continue
            synopsis = cls._normalize_synopsis(synopsis_match.group(1))
            if synopsis:
                result.synopsis = synopsis
                return

    @staticmethod
    def _synopsis_patterns() -> tuple[re.Pattern[str], ...]:
        return (
            re.compile(
                r"(?:synopsis|plot|overview|description)[:\s]+(.+?)(?:\n\n|\Z)",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(r"(?:story)[:\s]+(.+?)(?:\n\n|\Z)", re.IGNORECASE | re.DOTALL),
        )

    @staticmethod
    def _normalize_synopsis(raw_synopsis: str) -> str | None:
        synopsis = re.sub(r"\s+", " ", raw_synopsis.strip())
        if len(synopsis) <= 50:
            return None
        return synopsis

    @classmethod
    def _match_first(cls, content: str, *patterns: re.Pattern[str]) -> str | None:
        for pattern in patterns:
            match = pattern.search(content)
            if match:
                return match.group(1)
        return None

    @classmethod
    def _match_first_int(cls, content: str, *patterns: re.Pattern[str]) -> int | None:
        value = cls._match_first(content, *patterns)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @classmethod
    def _match_first_float(cls, content: str, *patterns: re.Pattern[str]) -> float | None:
        value = cls._match_first(content, *patterns)
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _match_line_value(content: str, pattern: re.Pattern[str]) -> str | None:
        match = pattern.search(content)
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _log_nfo_result(nfo_path: Path, result: NFOData) -> None:
        logger.debug(f"Parsed NFO: {nfo_path.name}")
        logger.debug(f"  IMDB: {result.imdb_id}")
        logger.debug(f"  TMDB: {result.tmdb_id}")
        logger.debug(f"  TVDB: {result.tvdb_id}")
        logger.debug(f"  Title: {result.title}")
        logger.debug(f"  Year: {result.year}")
