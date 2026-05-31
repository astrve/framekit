"""Gazelle tracker adapter.

Supports Gazelle-based trackers like RED, OPS, etc.
"""

from collections.abc import Callable
from typing import Any

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from swirrl.core.http import HttpAuthError, HttpError

from ..models import DiscoveryResult, TorrentFile, TorrentMetadata, TrackerConfig, UploadResult
from .base import AuthenticationError, TrackerAdapter


class GazelleAdapter(TrackerAdapter):
    """Adapter for Gazelle-based trackers."""

    def __init__(self, config: TrackerConfig):
        """Initialize Gazelle adapter."""
        super().__init__(config)
        self.api_base = f"{config.url.rstrip('/')}/ajax.php"

    def get_headers(self) -> dict[str, str]:
        """Get HTTP headers with API key."""
        headers = super().get_headers()
        headers["Authorization"] = self.config.api_key
        return headers

    def validate_credentials(self) -> bool:
        """Validate API credentials by testing connection."""
        try:
            response = self.client.get(
                f"{self.api_base}?action=index",
                headers=self.get_headers(),
                timeout=30,
            )
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            # HttpClient already validates status codes
            data = response.json()
            return data.get("status") == "success"
        except HttpAuthError as exc:
            raise AuthenticationError("Invalid API key") from exc
        except HttpError as e:
            self.logger.error(f"Credential validation failed: {e}")
            return False

    def discover_api(self) -> DiscoveryResult:
        """Discover Gazelle API endpoints and IDs."""
        result = DiscoveryResult(tracker_type="gazelle", tracker_url=self.config.url)
        try:
            response = self.client.get(
                f"{self.api_base}?action=index",
                headers=self.get_headers(),
                timeout=30,
            )
            # HttpClient already validates status codes
            data = response.json()

            result.categories = {
                "Music": 1,
                "Applications": 2,
                "E-Books": 3,
                "Audiobooks": 4,
                "E-Learning Videos": 5,
                "Comedy": 6,
                "Comics": 7,
            }
            result.required_fields = ["file_input", "title", "tags", "image", "desc", "category"]
            result.optional_fields = [
                "remaster_year",
                "remaster_title",
                "remaster_record_label",
                "remaster_catalogue_number",
                "format",
                "bitrate",
                "media",
                "release_desc",
            ]

            if "response" in data:
                result.api_version = data["response"].get("version", "unknown")

        except Exception as e:
            result.add_error(f"Discovery failed: {e!s}")
            self.logger.error(f"API discovery failed: {e}")

        return result

    def upload_torrent(
        self,
        torrent_file: TorrentFile,
        metadata: TorrentMetadata,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadResult:
        """Upload torrent to Gazelle tracker."""
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

            # Use HttpClient with multipart support
            with open(torrent_file.path, "rb") as torrent_fp:
                files = {"file_input": (torrent_file.name, torrent_fp, "application/x-bittorrent")}

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
                                f"{self.api_base}?action=upload",
                                headers=self.get_headers(),
                                data=upload_data,
                                files=files,
                                timeout=300,
                            )

                            if response.status_code == 401:
                                raise AuthenticationError("Authentication failed")

                            # HttpClient already validates status codes
                            data = response.json()
                            if data.get("status") == "success":
                                result.success = True
                                result.torrent_id = data.get("response", {}).get("torrentid")
                                result.url = (
                                    f"{self.config.url}/torrents.php?id={result.torrent_id}"
                                )
                                result.message = "Upload successful"
                            else:
                                error_msg = data.get("error", "Unknown error")
                                result.add_error(f"Upload failed: {error_msg}")

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
        """Build upload data dictionary for Gazelle."""
        from ..bbcode_templates import detect_bbcode_completeness, render_template
        from ..metadata_extractor import ReleaseParser

        # Enrich description if needed
        description = metadata.description
        if not detect_bbcode_completeness(description):
            # Parse release for additional metadata
            parsed = ReleaseParser.parse(metadata.name)
            description = render_template("gazelle", metadata, parsed)

        data: dict[str, Any] = {
            "title": metadata.name,
            "desc": description,
            "category": self.get_category_id(metadata.category) or 1,
            "tags": ",".join(metadata.tags) if metadata.tags else "",
        }

        # Add cover image URL if available
        if metadata.image_url:
            data["image"] = metadata.image_url

        # Add defaults from config
        defaults = self.config.defaults
        if "remaster_year" in defaults:
            data["remaster_year"] = defaults["remaster_year"]
        if "remaster_title" in defaults:
            data["remaster_title"] = defaults["remaster_title"]

        return data
