"""Custom tracker adapter template.

Template for implementing custom tracker adapters.
Users can extend this class to support non-standard trackers.
"""

from collections.abc import Callable
from typing import Any

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from framekit.core.http import HttpError

from ..models import DiscoveryResult, TorrentFile, TorrentMetadata, TrackerConfig, UploadResult
from .base import AuthenticationError, TrackerAdapter


class CustomAdapter(TrackerAdapter):
    """Template adapter for custom trackers.

    Override methods as needed to implement custom tracker logic.
    """

    def __init__(self, config: TrackerConfig):
        """Initialize custom adapter."""
        super().__init__(config)
        self.api_base = f"{config.url.rstrip('/')}/api"

    def get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests.

        Override this method to customize headers.
        Common patterns:
        - Bearer token: headers["Authorization"] = f"Bearer {self.config.api_key}"
        - API key header: headers["X-API-Key"] = self.config.api_key
        - Custom header: headers["X-Custom-Auth"] = self.config.api_key
        """
        headers = super().get_headers()
        headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def validate_credentials(self) -> bool:
        """Validate API credentials.

        Override this method to implement credential validation.
        """
        try:
            response = self.client.get(
                f"{self.api_base}/user",
                headers=self.get_headers(),
                timeout=30,
            )
            if response.status_code == 401:
                return False
            # HttpClient already validates status codes
            return True
        except HttpError as e:
            self.logger.error(f"Credential validation failed: {e}")
            return False

    def discover_api(self) -> DiscoveryResult:
        """Discover API endpoints and available IDs.

        Override this method to implement API discovery.
        """
        result = DiscoveryResult(tracker_type="custom", tracker_url=self.config.url)
        try:
            result.categories = self._fetch_categories()
            result.types = self._fetch_types()
            result.resolutions = self._fetch_resolutions()
            result.required_fields = ["torrent", "name", "description", "category_id"]
            result.optional_fields = ["tmdb", "imdb", "tvdb", "anonymous"]
        except Exception as e:
            result.add_error(f"Discovery failed: {e!s}")
            self.logger.error(f"API discovery failed: {e}")
        return result

    def _fetch_categories(self) -> dict[str, int]:
        """Fetch categories from API.

        Override this method to implement category fetching.
        """
        try:
            response = self.client.get(
                f"{self.api_base}/categories",
                headers=self.get_headers(),
                timeout=30,
            )
            # HttpClient already validates status codes
            data = response.json()
            categories: dict[str, int] = {}
            if isinstance(data, list):
                for cat in data:
                    categories[cat.get("name", "")] = cat.get("id", 0)
            return categories
        except Exception as e:
            self.logger.error(f"Failed to fetch categories: {e}")
            return {}

    def _fetch_types(self) -> dict[str, int]:
        """Fetch types from API. Override to implement."""
        return {}

    def _fetch_resolutions(self) -> dict[str, int]:
        """Fetch resolutions from API. Override to implement."""
        return {}

    def upload_torrent(
        self,
        torrent_file: TorrentFile,
        metadata: TorrentMetadata,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadResult:
        """Upload torrent to tracker.

        Override this method to implement torrent upload.
        """
        import time

        result = UploadResult(success=False, tracker=self.config.name)
        start_time = time.time()

        try:
            if not self.validate_credentials():
                result.add_error("Invalid API credentials")
                return result

            if not torrent_file.validate():
                result.add_error("Invalid torrent file")
                return result

            is_valid, errors = self.validate_metadata(metadata)
            if not is_valid:
                for error in errors:
                    result.add_error(error)
                return result

            upload_data = self._build_upload_data(metadata)

            with open(torrent_file.path, "rb") as torrent_fp:
                files = {"torrent": (torrent_file.name, torrent_fp, "application/x-bittorrent")}

                try:
                    for attempt in Retrying(
                        stop=stop_after_attempt(self.config.retry_attempts),
                        wait=wait_exponential(multiplier=self.config.retry_delay, min=1, max=60),
                        retry=retry_if_exception_type((HttpError,)),
                        reraise=True,
                    ):
                        with attempt:
                            self.logger.info(
                                f"Upload attempt {attempt.retry_state.attempt_number}"
                                f"/{self.config.retry_attempts}"
                            )
                            torrent_fp.seek(0)

                            response = self.client.post(
                                f"{self.api_base}/upload",
                                headers=self.get_headers(),
                                data=upload_data,
                                files=files,
                                timeout=300,
                            )

                            if response.status_code == 401:
                                raise AuthenticationError("Authentication failed")

                            # HttpClient already validates status codes
                            data = response.json()
                            result.success = True
                            result.torrent_id = data.get("id")
                            result.url = f"{self.config.url}/torrents/{result.torrent_id}"
                            result.message = "Upload successful"

                except HttpError as e:
                    self.logger.warning(
                        f"Upload failed after {self.config.retry_attempts} attempts: {e}"
                    )
                    result.add_error(
                        f"Upload failed after {self.config.retry_attempts} attempts: {e!s}"
                    )

        except Exception as e:
            result.add_error(f"Unexpected error: {e!s}")
            self.logger.exception(f"Upload failed: {e}")

        result.upload_time = time.time() - start_time
        return result

    def _build_upload_data(self, metadata: TorrentMetadata) -> dict[str, Any]:
        """Build upload data dictionary.

        Override this method to customize the upload payload.
        """
        data: dict[str, Any] = {
            "name": metadata.name,
            "description": metadata.description,
            "category_id": self.get_category_id(metadata.category),
        }
        if metadata.tmdb_id:
            data["tmdb"] = metadata.tmdb_id
        if metadata.imdb_id:
            data["imdb"] = metadata.imdb_id
        if metadata.tvdb_id:
            data["tvdb"] = metadata.tvdb_id
        data.update(self.config.defaults)
        return data
