"""UNIT3D tracker adapter.

Supports UNIT3D-based trackers like c411.org, BeyondHD, Blutopia, etc.
"""

from collections.abc import Callable
from typing import Any

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from framekit.core.http import HttpAuthError, HttpError

from ..models import DiscoveryResult, TorrentFile, TorrentMetadata, TrackerConfig, UploadResult
from .base import AuthenticationError, TrackerAdapter


class UNIT3DAdapter(TrackerAdapter):
    """Adapter for UNIT3D-based trackers."""

    def __init__(self, config: TrackerConfig):
        """Initialize UNIT3D adapter."""
        super().__init__(config)
        self.api_base = f"{config.url.rstrip('/')}/api"

    def get_headers(self) -> dict[str, str]:
        """Get HTTP headers with API key."""
        headers = super().get_headers()
        headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def validate_credentials(self) -> bool:
        """Validate API credentials by testing connection."""
        try:
            response = self.client.get(
                f"{self.api_base}/user",
                headers=self.get_headers(),
                timeout=30,
            )
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            # HttpClient already validates status codes
            return True
        except HttpAuthError as exc:
            raise AuthenticationError("Invalid API key") from exc
        except HttpError as e:
            self.logger.error(f"Credential validation failed: {e}")
            return False

    def discover_api(self) -> DiscoveryResult:
        """Discover UNIT3D API endpoints and IDs."""
        result = DiscoveryResult(tracker_type="unit3d", tracker_url=self.config.url)
        try:
            categories = self._fetch_categories()
            if categories:
                result.categories = categories
            else:
                result.add_error("Failed to fetch categories")

            types = self._fetch_types()
            if types:
                result.types = types
            else:
                result.add_error("Failed to fetch types")

            resolutions = self._fetch_resolutions()
            if resolutions:
                result.resolutions = resolutions
            else:
                result.add_error("Failed to fetch resolutions")

            result.required_fields = ["torrent", "name", "description", "category_id", "type_id"]
            result.optional_fields = [
                "tmdb",
                "imdb",
                "tvdb",
                "mal",
                "anonymous",
                "stream",
                "sd",
                "internal",
            ]

            try:
                response = self.client.get(
                    f"{self.api_base}/version",
                    headers=self.get_headers(),
                    timeout=30,
                )
                if 200 <= response.status_code < 300:
                    data = response.json()
                    result.api_version = data.get("version", "unknown")
            except Exception:  # nosec B110
                pass

        except Exception as e:
            result.add_error(f"Discovery failed: {e!s}")
            self.logger.error(f"API discovery failed: {e}")

        return result

    def _fetch_categories(self) -> dict[str, int]:
        """Fetch categories from API."""
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
            elif isinstance(data, dict) and "data" in data:
                for cat in data["data"]:
                    categories[cat.get("name", "")] = cat.get("id", 0)
            return categories
        except Exception as e:
            self.logger.error(f"Failed to fetch categories: {e}")
            return {}

    def _fetch_types(self) -> dict[str, int]:
        """Fetch types from API."""
        try:
            response = self.client.get(
                f"{self.api_base}/types",
                headers=self.get_headers(),
                timeout=30,
            )
            # HttpClient already validates status codes
            data = response.json()
            types: dict[str, int] = {}
            if isinstance(data, list):
                for typ in data:
                    types[typ.get("name", "")] = typ.get("id", 0)
            elif isinstance(data, dict) and "data" in data:
                for typ in data["data"]:
                    types[typ.get("name", "")] = typ.get("id", 0)
            return types
        except Exception as e:
            self.logger.error(f"Failed to fetch types: {e}")
            return {}

    def _fetch_resolutions(self) -> dict[str, int]:
        """Fetch resolutions from API."""
        try:
            response = self.client.get(
                f"{self.api_base}/resolutions",
                headers=self.get_headers(),
                timeout=30,
            )
            # HttpClient already validates status codes
            data = response.json()
            resolutions: dict[str, int] = {}
            if isinstance(data, list):
                for res in data:
                    resolutions[res.get("name", "")] = res.get("id", 0)
            elif isinstance(data, dict) and "data" in data:
                for res in data["data"]:
                    resolutions[res.get("name", "")] = res.get("id", 0)
            return resolutions
        except Exception as e:
            self.logger.error(f"Failed to fetch resolutions: {e}")
            return {}

    def upload_torrent(
        self,
        torrent_file: TorrentFile,
        metadata: TorrentMetadata,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadResult:
        """Upload torrent to UNIT3D tracker."""
        import time

        result = UploadResult(success=False, tracker=self.config.name)
        start_time = time.time()

        try:
            if not self._validate_upload_prerequisites(result, torrent_file, metadata):
                return result

            upload_data = self._build_upload_data(metadata)
            file_size = torrent_file.path.stat().st_size

            # Use HttpClient with multipart support
            with open(torrent_file.path, "rb") as torrent_fp:
                files = {"torrent": (torrent_file.name, torrent_fp, "application/x-bittorrent")}
                self._attempt_upload(
                    result=result,
                    torrent_fp=torrent_fp,
                    files=files,
                    upload_data=upload_data,
                    file_size=file_size,
                    progress_callback=progress_callback,
                )

        except Exception as e:
            result.add_error(f"Unexpected error: {e!s}")
            self.logger.exception(f"Upload failed: {e}")

        result.upload_time = time.time() - start_time
        return result

    def _validate_upload_prerequisites(
        self,
        result: UploadResult,
        torrent_file: TorrentFile,
        metadata: TorrentMetadata,
    ) -> bool:
        if not self.validate_credentials():
            result.add_error("Invalid API credentials")
            return False
        if not torrent_file.validate():
            result.add_error("Invalid torrent file")
            return False
        is_valid, errors = self.validate_metadata(metadata)
        if is_valid:
            return True
        for error in errors:
            result.add_error(error)
        return False

    def _handle_validation_errors(
        self, result: UploadResult, response_payload: dict[str, Any]
    ) -> None:
        errors = response_payload.get("errors", {})
        if not isinstance(errors, dict):
            result.add_error("Upload rejected: validation failed")
            return
        for field, messages in errors.items():
            if isinstance(messages, list):
                for msg in messages:
                    result.add_error(f"{field}: {msg}")
            else:
                result.add_error(f"{field}: {messages}")

    def _apply_success(self, result: UploadResult, payload: dict[str, Any]) -> None:
        result.success = True
        result.torrent_id = payload.get("id")
        result.url = f"{self.config.url}/torrents/{result.torrent_id}"
        result.message = "Upload successful"

    def _attempt_upload(
        self,
        *,
        result: UploadResult,
        torrent_fp: Any,
        files: dict[str, tuple[str, Any, str]],
        upload_data: dict[str, Any],
        file_size: int,
        progress_callback: Callable[[int, int], None] | None,
    ) -> None:
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
                    if progress_callback:
                        progress_callback(0, file_size)

                    response = self.client.post(
                        f"{self.api_base}/torrents",
                        headers=self.get_headers(),
                        data=upload_data,
                        files=files,
                        timeout=300,
                    )
                    if progress_callback:
                        progress_callback(file_size, file_size)

                    if response.status_code == 401:
                        raise AuthenticationError("Authentication failed")
                    if response.status_code == 422:
                        payload = response.json()
                        if isinstance(payload, dict):
                            self._handle_validation_errors(result, payload)
                        else:
                            result.add_error("Upload rejected: validation failed")
                        return

                    payload = response.json()
                    if isinstance(payload, dict):
                        self._apply_success(result, payload)
                    else:
                        result.add_error("Upload failed: invalid server response")
                    return
        except HttpError as e:
            self.logger.warning(f"Upload failed after {self.config.retry_attempts} attempts: {e}")
            result.add_error(f"Upload failed after {self.config.retry_attempts} attempts: {e!s}")

    def _build_upload_data(self, metadata: TorrentMetadata) -> dict[str, Any]:
        """Build upload data dictionary."""
        from ..bbcode_templates import detect_bbcode_completeness, render_template
        from ..metadata_extractor import ReleaseParser

        # Enrich description if needed
        description = metadata.description
        if not detect_bbcode_completeness(description):
            # Parse release for additional metadata
            parsed = ReleaseParser.parse(metadata.name)
            description = render_template("unit3d", metadata, parsed)

        data: dict[str, Any] = {
            "name": metadata.name,
            "description": description,
            "category_id": self.get_category_id(metadata.category),
            "type_id": self.get_type_id(metadata.type),
            "anonymous": 1 if metadata.anonymous else 0,
            "stream": 1 if metadata.stream else 0,
            "sd": 1 if metadata.sd else 0,
        }

        optional_ids = {
            "tmdb": metadata.tmdb_id,
            "imdb": metadata.imdb_id,
            "tvdb": metadata.tvdb_id,
            "mal": metadata.mal_id,
        }
        data.update({key: value for key, value in optional_ids.items() if value})
        if metadata.internal:
            data["internal"] = 1
        if metadata.tags:
            data["tags"] = ",".join(metadata.tags)
        if metadata.hdr:
            data["hdr"] = metadata.hdr
        return data
