"""Duplicate checker for preventing duplicate torrent uploads.

Checks for existing torrents on trackers using IMDB/TMDB IDs and normalized names.
"""

import re
from dataclasses import dataclass, field

from loguru import logger

from swirrl.core.http import HttpError

from .adapters.base import TrackerAdapter
from .metadata_extractor import ReleaseParser
from .models import TorrentMetadata


@dataclass
class DupeCheckResult:
    """Result of duplicate check operation."""

    has_dupes: bool
    dupes: list[dict] = field(default_factory=list)  # [{"id": 123, "name": "...", "url": "..."}]
    confidence: str = "low"  # "high" (IMDB/TMDB) | "medium" (name) | "low"

    def add_dupe(self, torrent_id: int, name: str, url: str):
        """Add a duplicate torrent to the result."""
        self.dupes.append({"id": torrent_id, "name": name, "url": url})
        self.has_dupes = True


class DupeChecker:
    """Service for checking duplicate torrents on trackers."""

    def __init__(self, adapter: TrackerAdapter):
        """Initialize duplicate checker.

        Args:
            adapter: Tracker adapter instance
        """
        self.adapter = adapter
        self.logger = logger.bind(tracker=adapter.config.name)

    def check(self, metadata: TorrentMetadata) -> DupeCheckResult:
        """Check for duplicate torrents on tracker.

        Searches by:
        1. IMDB ID if present (high confidence)
        2. TMDB ID if present (high confidence)
        3. Normalized name (medium confidence)

        Args:
            metadata: Torrent metadata to check

        Returns:
            DupeCheckResult with list of found torrents
        """
        result = DupeCheckResult(has_dupes=False)
        try:
            # Determine tracker type and search accordingly
            tracker_type = self.adapter.config.type
            if tracker_type == "unit3d":
                return self._search_unit3d(metadata)
            if tracker_type == "gazelle":
                return self._search_gazelle(metadata)
            self.logger.warning(
                f"Duplicate checking not supported for tracker type: {tracker_type}"
            )
            return result

        except Exception as e:
            self.logger.warning(f"Duplicate check failed: {e}")
            # Don't fail the upload on dupe check errors
            return result

    def _name_based_search(self, metadata: TorrentMetadata) -> bool:
        return not metadata.imdb_id and not metadata.tmdb_id

    def _coerce_torrent_id(self, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    def _add_if_match(
        self,
        result: DupeCheckResult,
        metadata: TorrentMetadata,
        torrent_id: int,
        torrent_name: str,
        torrent_url: str,
    ) -> None:
        if self._name_based_search(metadata) and not self._is_similar_name(
            metadata.name, torrent_name
        ):
            return
        result.add_dupe(torrent_id, torrent_name, torrent_url)
        self.logger.info(f"Found duplicate: {torrent_name} (ID: {torrent_id})")

    def _log_dupe_summary(self, result: DupeCheckResult) -> None:
        if result.has_dupes:
            self.logger.warning(f"Found {len(result.dupes)} potential duplicate(s)")
            return
        self.logger.info("No duplicates found")

    def _unit3d_params(
        self, metadata: TorrentMetadata, result: DupeCheckResult
    ) -> dict[str, str | int]:
        if metadata.imdb_id:
            result.confidence = "high"
            self.logger.info(f"Checking duplicates by IMDB ID: {metadata.imdb_id}")
            return {"imdbId": metadata.imdb_id}
        if metadata.tmdb_id:
            result.confidence = "high"
            self.logger.info(f"Checking duplicates by TMDB ID: {metadata.tmdb_id}")
            return {"tmdbId": metadata.tmdb_id}
        normalized_name = self._normalize_for_comparison(metadata.name)
        result.confidence = "medium"
        self.logger.info(f"Checking duplicates by name: {normalized_name}")
        return {"name": normalized_name}

    def _gazelle_search_string(self, metadata: TorrentMetadata, result: DupeCheckResult) -> str:
        if metadata.imdb_id:
            result.confidence = "high"
            self.logger.info(f"Checking duplicates by IMDB ID: {metadata.imdb_id}")
            return metadata.imdb_id
        if metadata.tmdb_id:
            result.confidence = "high"
            self.logger.info(f"Checking duplicates by TMDB ID: {metadata.tmdb_id}")
            return f"tmdb:{metadata.tmdb_id}"
        search_str = self._normalize_for_comparison(metadata.name)
        result.confidence = "medium"
        self.logger.info(f"Checking duplicates by name: {search_str}")
        return search_str

    def _parse_unit3d_torrents(self, payload: object) -> list[dict]:
        if isinstance(payload, dict):
            data = payload.get("data", [])
            return data if isinstance(data, list) else []
        if isinstance(payload, list):
            return payload
        return []

    def _parse_gazelle_torrents(self, payload: object) -> list[dict]:
        if not isinstance(payload, dict) or payload.get("status") != "success":
            return []
        response = payload.get("response", {})
        if not isinstance(response, dict):
            return []
        results = response.get("results", [])
        return results if isinstance(results, list) else []

    def _search_unit3d(self, metadata: TorrentMetadata) -> DupeCheckResult:
        """Search for duplicates on UNIT3D tracker.

        Args:
            metadata: Torrent metadata

        Returns:
            DupeCheckResult
        """
        result = DupeCheckResult(has_dupes=False)

        try:
            params = self._unit3d_params(metadata, result)

            # Make API request
            api_base = f"{self.adapter.config.url.rstrip('/')}/api"
            # NOTE: per-call timeout is configured at HttpClient construction
            # time; the get() method does not accept a timeout keyword.
            response = self.adapter.client.get(
                f"{api_base}/torrents/filter",
                headers=self.adapter.get_headers(),
                params=params,
            )

            if response.status_code != 200:
                self.logger.warning(f"Duplicate check returned status {response.status_code}")
                return result

            torrents = self._parse_unit3d_torrents(response.json())

            # Add found duplicates
            for torrent in torrents:
                torrent_id = self._coerce_torrent_id(torrent.get("id"))
                if torrent_id is None:
                    continue
                torrent_name = torrent.get("name", "Unknown")
                torrent_url = f"{self.adapter.config.url}/torrents/{torrent_id}"
                self._add_if_match(result, metadata, torrent_id, torrent_name, torrent_url)
            self._log_dupe_summary(result)

        except HttpError as e:
            self.logger.warning(f"HTTP error during duplicate check: {e}")
        except Exception as e:
            self.logger.warning(f"Error during duplicate check: {e}")

        return result

    def _search_gazelle(self, metadata: TorrentMetadata) -> DupeCheckResult:
        """Search for duplicates on Gazelle tracker.

        Args:
            metadata: Torrent metadata

        Returns:
            DupeCheckResult
        """
        result = DupeCheckResult(has_dupes=False)

        try:
            search_str = self._gazelle_search_string(metadata, result)

            # Make API request
            api_base = f"{self.adapter.config.url.rstrip('/')}/ajax.php"
            # NOTE: per-call timeout is configured at HttpClient construction
            # time; the get() method does not accept a timeout keyword.
            response = self.adapter.client.get(
                api_base,
                headers=self.adapter.get_headers(),
                params={"action": "browse", "searchstr": search_str},
            )

            if response.status_code != 200:
                self.logger.warning(f"Duplicate check returned status {response.status_code}")
                return result

            results = self._parse_gazelle_torrents(response.json())
            for torrent in results:
                torrent_id = self._coerce_torrent_id(torrent.get("torrentId"))
                if torrent_id is None:
                    continue
                torrent_name = torrent.get("groupName", "Unknown")
                torrent_url = f"{self.adapter.config.url}/torrents.php?id={torrent_id}"
                self._add_if_match(result, metadata, torrent_id, torrent_name, torrent_url)
            self._log_dupe_summary(result)

        except HttpError as e:
            self.logger.warning(f"HTTP error during duplicate check: {e}")
        except Exception as e:
            self.logger.warning(f"Error during duplicate check: {e}")

        return result

    def _normalize_for_comparison(self, name: str) -> str:
        """Normalize release name for comparison by removing technical details.

        Strips group, codec, source, resolution using ReleaseParser patterns.

        Args:
            name: Release name to normalize

        Returns:
            Normalized name
        """
        normalized = name

        # Remove group (usually at the end after a dash)
        normalized = ReleaseParser.GROUP_PATTERN.sub("", normalized)

        # Remove resolution
        for pattern in ReleaseParser.RESOLUTION_PATTERNS.values():
            normalized = pattern.sub("", normalized)

        # Remove source
        for pattern in ReleaseParser.SOURCE_PATTERNS.values():
            normalized = pattern.sub("", normalized)

        # Remove codec
        for pattern in ReleaseParser.CODEC_PATTERNS.values():
            normalized = pattern.sub("", normalized)

        # Remove audio
        for pattern in ReleaseParser.AUDIO_PATTERNS.values():
            normalized = pattern.sub("", normalized)

        # Remove HDR
        for pattern in ReleaseParser.HDR_PATTERNS.values():
            normalized = pattern.sub("", normalized)

        # Clean up extra spaces and dots
        normalized = re.sub(r"[.\s]+", " ", normalized)
        normalized = normalized.strip()

        return normalized

    def _is_similar_name(self, name1: str, name2: str) -> bool:
        """Check if two release names are similar enough to be considered duplicates.

        Args:
            name1: First release name
            name2: Second release name

        Returns:
            True if names are similar
        """
        # Normalize both names
        norm1 = self._normalize_for_comparison(name1).lower()
        norm2 = self._normalize_for_comparison(name2).lower()

        # Check if one contains the other (allowing for minor differences)
        if norm1 in norm2 or norm2 in norm1:
            return True

        # Calculate simple similarity (Jaccard similarity on words)
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return False

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        similarity = intersection / union if union > 0 else 0

        # Consider similar if > 70% word overlap
        return similarity > 0.7
