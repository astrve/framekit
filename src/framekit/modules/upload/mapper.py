"""Fuzzy metadata mapper for tracker uploads.

Maps generic metadata values (like "Movies", "1080p", "1920x1080") to exact
tracker-specific IDs using fuzzy matching, aliases, and normalization.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from loguru import logger


class MetadataMapper:
    """Fuzzy mapper for resolving metadata to tracker-specific IDs."""

    # Resolution aliases mapping canonical names to variants
    RESOLUTION_ALIASES = {
        "2160p": [
            "2160p",
            "4k",
            "uhd",
            "ultra hd",
            "3840x2160",
            "3840×2160",
            "4096x2160",
            "4096×2160",
        ],
        "1080p": ["1080p", "fhd", "full hd", "1920x1080", "1920×1080"],
        "1080i": ["1080i", "1920x1080i", "1920×1080i"],
        "720p": ["720p", "hd", "1280x720", "1280×720"],
        "576p": ["576p", "pal", "720x576", "720×576"],
        "480p": ["480p", "ntsc", "sd", "720x480", "720×480", "854x480", "854×480"],
        "other": ["other", "unknown"],
    }

    # Source aliases mapping canonical names to variants
    SOURCE_ALIASES = {
        "BluRay": ["bluray", "blu-ray", "blu ray", "bdrip", "brrip", "bd"],
        "REMUX": ["remux", "blu-ray remux", "bluray remux"],
        "WEB-DL": ["web-dl", "webdl", "web dl"],
        "WEBRip": ["webrip", "web-rip", "web rip"],
        "HDTV": ["hdtv", "hd-tv", "pdtv"],
        "DVD": ["dvd", "dvdrip", "dvd-rip"],
        "Other": ["other", "unknown"],
    }

    # Type aliases for common upload types
    TYPE_ALIASES = {
        "Blu-ray Remux": ["bluray remux", "blu-ray remux", "bd remux", "remux"],
        "Encode": ["encode", "encoded", "x264", "x265", "h264", "h265", "hevc"],
        "WEB Remux": ["web remux", "webdl remux"],
        "WEB-DL": ["web-dl", "webdl", "web dl"],
        "WEBRip": ["webrip", "web-rip", "web rip"],
        "HDTV": ["hdtv", "hd-tv", "pdtv"],
        "DVD": ["dvd", "dvdrip"],
        "Other": ["other", "unknown"],
    }

    # Category aliases
    CATEGORY_ALIASES = {
        "Movie": ["movie", "movies", "film", "films"],
        "TV": ["tv", "tv show", "tv shows", "television", "series"],
        "Documentary": ["documentary", "documentaries", "docu", "docs"],
        "Sport": ["sport", "sports"],
        "Music": ["music", "concert", "concerts"],
        "Anime": ["anime", "animation"],
    }

    def __init__(self):
        """Initialize the metadata mapper."""
        self.logger = logger.bind(component="metadata_mapper")

    @staticmethod
    def normalize(s: str) -> str:
        """Normalize string for comparison.

        Converts to lowercase, removes accents, strips punctuation and extra spaces.

        Args:
            s: String to normalize

        Returns:
            Normalized string
        """
        if not s:
            return ""

        # Convert to lowercase
        s = s.lower()

        # Remove accents
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))

        # Remove punctuation and extra spaces
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s)

        return s.strip()

    def _exact_match(self, query_lower: str, candidates: dict[str, int]) -> tuple[str, int] | None:
        for key, value in candidates.items():
            if key.lower() == query_lower:
                self.logger.debug(f"Exact match: '{query_lower}' -> '{key}' (ID: {value})")
                return key, value
        return None

    def _normalized_match(
        self,
        query_norm: str,
        candidates: dict[str, int],
    ) -> tuple[str, int] | None:
        for key, value in candidates.items():
            if self.normalize(key) == query_norm:
                self.logger.debug(f"Normalized match: '{query_norm}' -> '{key}' (ID: {value})")
                return key, value
        return None

    def _fuzzy_match_score(
        self,
        query: str,
        query_norm: str,
        candidates: dict[str, int],
        threshold: float,
    ) -> tuple[str, int] | None:
        best_match: tuple[str, int] | None = None
        best_score = threshold
        for key, value in candidates.items():
            score = SequenceMatcher(None, query_norm, self.normalize(key)).ratio()
            if score <= best_score:
                continue
            best_score = score
            best_match = (key, value)
        if best_match:
            self.logger.debug(
                f"Fuzzy match: '{query}' -> '{best_match[0]}' "
                f"(ID: {best_match[1]}, score: {best_score:.2f})"
            )
        return best_match

    def _partial_match(
        self,
        query: str,
        query_norm: str,
        candidates: dict[str, int],
    ) -> tuple[str, int] | None:
        for key, value in candidates.items():
            key_norm = self.normalize(key)
            if query_norm in key_norm or key_norm in query_norm:
                self.logger.debug(f"Partial match: '{query}' -> '{key}' (ID: {value})")
                return key, value
        return None

    def fuzzy_match(
        self, query: str, candidates: dict[str, int], threshold: float = 0.6
    ) -> tuple[str, int] | None:
        """Find best match for query in candidates using fuzzy matching.

        Priority order:
        1. Exact match (case-insensitive)
        2. Normalized match (strip accents, punctuation, spaces)
        3. Alias match (check if query is in ALIASES)
        4. Fuzzy match via SequenceMatcher if score > threshold
        5. Partial match (substring containment)

        Args:
            query: Query string to match
            candidates: Dictionary of candidate strings to IDs
            threshold: Minimum similarity score for fuzzy match (0.0-1.0)

        Returns:
            Tuple of (matched_key, id) or None if no match found
        """
        if not query or not candidates:
            return None

        query_lower = query.lower()
        query_norm = self.normalize(query)
        exact = self._exact_match(query_lower, candidates)
        if exact:
            return exact
        normalized = self._normalized_match(query_norm, candidates)
        if normalized:
            return normalized
        fuzzy = self._fuzzy_match_score(query, query_norm, candidates, threshold)
        if fuzzy:
            return fuzzy
        partial = self._partial_match(query, query_norm, candidates)
        if partial:
            return partial
        self.logger.debug(f"No match found for: '{query}'")
        return None

    def resolve_via_aliases(
        self, query: str, aliases: dict[str, list[str]], candidates: dict[str, int]
    ) -> tuple[str, int] | None:
        """Resolve query via alias dictionary.

        Args:
            query: Query string
            aliases: Dictionary mapping canonical names to alias lists
            candidates: Dictionary of candidate strings to IDs

        Returns:
            Tuple of (matched_key, id) or None
        """
        query_norm = self.normalize(query)

        # Check each alias group
        for canonical, alias_list in aliases.items():
            for alias in alias_list:
                if self.normalize(alias) == query_norm:
                    # Found in aliases, now match canonical to candidates
                    result = self.fuzzy_match(canonical, candidates, threshold=0.5)
                    if result:
                        self.logger.debug(
                            f"Alias match: '{query}' -> '{alias}' -> '{result[0]}' (ID: {result[1]})"
                        )
                        return result

        return None

    def resolve_resolution(self, raw: str, candidates: dict[str, int]) -> tuple[str, int] | None:
        """Resolve resolution string to tracker ID.

        Args:
            raw: Raw resolution string (e.g., "1920x1080", "4k", "1080p")
            candidates: Dictionary of available resolutions to IDs

        Returns:
            Tuple of (matched_key, id) or None
        """
        # Try alias resolution first
        result = self.resolve_via_aliases(raw, self.RESOLUTION_ALIASES, candidates)
        if result:
            return result

        # Fall back to fuzzy match
        return self.fuzzy_match(raw, candidates, threshold=0.6)

    def resolve_source(self, raw: str, candidates: dict[str, int]) -> tuple[str, int] | None:
        """Resolve source string to tracker ID.

        Args:
            raw: Raw source string (e.g., "BluRay", "WEB-DL")
            candidates: Dictionary of available sources to IDs

        Returns:
            Tuple of (matched_key, id) or None
        """
        # Try alias resolution first
        result = self.resolve_via_aliases(raw, self.SOURCE_ALIASES, candidates)
        if result:
            return result

        # Fall back to fuzzy match
        return self.fuzzy_match(raw, candidates, threshold=0.6)

    def resolve_type(self, raw: str, candidates: dict[str, int]) -> tuple[str, int] | None:
        """Resolve type string to tracker ID.

        Args:
            raw: Raw type string
            candidates: Dictionary of available types to IDs

        Returns:
            Tuple of (matched_key, id) or None
        """
        # Try alias resolution first
        result = self.resolve_via_aliases(raw, self.TYPE_ALIASES, candidates)
        if result:
            return result

        # Fall back to fuzzy match
        return self.fuzzy_match(raw, candidates, threshold=0.6)

    def resolve_category(self, raw: str, candidates: dict[str, int]) -> tuple[str, int] | None:
        """Resolve category string to tracker ID.

        Args:
            raw: Raw category string
            candidates: Dictionary of available categories to IDs

        Returns:
            Tuple of (matched_key, id) or None
        """
        # Try alias resolution first
        result = self.resolve_via_aliases(raw, self.CATEGORY_ALIASES, candidates)
        if result:
            return result

        # Fall back to fuzzy match
        return self.fuzzy_match(raw, candidates, threshold=0.6)

    def auto_map_metadata(
        self, metadata: dict[str, Any], config: dict[str, dict[str, int]]
    ) -> dict[str, Any]:
        """Automatically map metadata fields to tracker-specific values.

        Creates a copy of metadata with resolved values. Logs all replacements
        and unresolved fields.

        Args:
            metadata: Original metadata dictionary
            config: Tracker configuration with categories, types, resolutions dicts

        Returns:
            New metadata dictionary with resolved values
        """
        result = metadata.copy()

        # Resolve category
        if "category" in metadata and "categories" in config:
            raw_category = metadata["category"]
            match = self.resolve_category(raw_category, config["categories"])
            if match:
                result["category"] = match[0]
                self.logger.info(
                    f"Mapped category: '{raw_category}' -> '{match[0]}' (ID: {match[1]})"
                )
            else:
                self.logger.warning(f"Could not resolve category: '{raw_category}'")

        # Resolve type
        if "type" in metadata and "types" in config:
            raw_type = metadata["type"]
            match = self.resolve_type(raw_type, config["types"])
            if match:
                result["type"] = match[0]
                self.logger.info(f"Mapped type: '{raw_type}' -> '{match[0]}' (ID: {match[1]})")
            else:
                self.logger.warning(f"Could not resolve type: '{raw_type}'")

        # Resolve resolution
        if "resolution" in metadata and "resolutions" in config:
            raw_resolution = metadata["resolution"]
            match = self.resolve_resolution(raw_resolution, config["resolutions"])
            if match:
                result["resolution"] = match[0]
                self.logger.info(
                    f"Mapped resolution: '{raw_resolution}' -> '{match[0]}' (ID: {match[1]})"
                )
            else:
                self.logger.warning(f"Could not resolve resolution: '{raw_resolution}'")

        return result
