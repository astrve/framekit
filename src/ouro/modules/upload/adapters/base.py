"""Base adapter interface for tracker uploads.

Defines the abstract interface that all tracker adapters must implement.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from loguru import logger

from ouro.core.http import HttpClient, HttpClientConfig

from ..mapper import MetadataMapper
from ..models import DiscoveryResult, TorrentFile, TorrentMetadata, TrackerConfig, UploadResult


class TrackerAdapter(ABC):
    """Abstract base class for tracker adapters."""

    def __init__(self, config: TrackerConfig):
        """Initialize adapter with tracker configuration.

        Note: HTTP client is lazily initialized on first use and automatically
        cleaned up on deletion. For explicit cleanup, call close() method.

        Args:
            config: Tracker configuration
        """
        self.config = config
        self.logger = logger.bind(tracker=config.name)
        self._client: HttpClient | None = None

    @property
    def client(self) -> HttpClient:
        """Get or create HTTP client with lazy initialization and HTTP/2 support."""
        if self._client is None:
            http_config = HttpClientConfig(
                timeout_seconds=float(self.config.timeout),
                user_agent="Ouro/2.0.0",
                http2=True,  # Enable HTTP/2 for better performance
                max_connections=20,
                max_keepalive_connections=10,
            )
            self._client = HttpClient(
                base_url=self.config.url.rstrip("/"),
                config=http_config,
            )
        return self._client

    @abstractmethod
    def discover_api(self) -> DiscoveryResult:
        """Discover API endpoints and available IDs.

        Returns:
            DiscoveryResult with categories, types, resolutions, etc.
        """

    @abstractmethod
    def upload_torrent(
        self,
        torrent_file: TorrentFile,
        metadata: TorrentMetadata,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadResult:
        """Upload torrent to tracker.

        Args:
            torrent_file: Torrent file to upload
            metadata: Torrent metadata
            progress_callback: Optional callback for progress updates (bytes_uploaded, total_bytes)

        Returns:
            UploadResult with success status and details
        """

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate API credentials.

        Returns:
            True if credentials are valid, False otherwise
        """

    def get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Dictionary of HTTP headers
        """
        return {"User-Agent": "Ouro/1.0", "Accept": "application/json"}

    def get_category_id(self, category: str) -> int | None:
        """Get category ID from category name.

        Args:
            category: Category name

        Returns:
            Category ID or None if not found
        """
        return self.config.categories.get(category)

    def get_type_id(self, type_name: str) -> int | None:
        """Get type ID from type name.

        Args:
            type_name: Type name (e.g., "1080p", "2160p")

        Returns:
            Type ID or None if not found
        """
        return self.config.types.get(type_name)

    def get_resolution_id(self, resolution: str) -> int | None:
        """Get resolution ID from resolution string.

        Args:
            resolution: Resolution string (e.g., "1920x1080")

        Returns:
            Resolution ID or None if not found
        """
        return self.config.resolutions.get(resolution)

    def validate_metadata(self, metadata: TorrentMetadata) -> tuple[bool, list[str]]:
        """Validate metadata before upload.

        Uses MetadataMapper to automatically resolve generic values to tracker-specific IDs.

        Args:
            metadata: Torrent metadata to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Use MetadataMapper to auto-resolve metadata
        mapper = MetadataMapper()
        config_dict = {
            "categories": self.config.categories,
            "types": self.config.types,
            "resolutions": self.config.resolutions,
        }

        # Convert metadata to dict for mapping
        metadata_dict = {
            "category": metadata.category,
            "type": metadata.type,
            "resolution": metadata.resolution,
        }

        # Auto-map metadata
        mapped = mapper.auto_map_metadata(metadata_dict, config_dict)

        # Update metadata with mapped values
        metadata.category = mapped.get("category", metadata.category)
        metadata.type = mapped.get("type", metadata.type)
        metadata.resolution = mapped.get("resolution", metadata.resolution)

        # Check category
        if not self.get_category_id(metadata.category):
            errors.append(f"Invalid category: {metadata.category}")

        # Check type
        if not self.get_type_id(metadata.type):
            errors.append(f"Invalid type: {metadata.type}")

        # Check resolution
        if not self.get_resolution_id(metadata.resolution):
            errors.append(f"Invalid resolution: {metadata.resolution}")

        return len(errors) == 0, errors

    def log_redacted(self, message: str):
        """Log message with API key redacted.

        Args:
            message: Message to log
        """
        # Redact API key from message
        redacted = message.replace(self.config.api_key, "[REDACTED]")
        self.logger.info(redacted)

    def build_upload_url(self, endpoint: str) -> str:
        """Build full URL for API endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Full URL
        """
        base_url = self.config.url.rstrip("/")
        endpoint = endpoint.lstrip("/")
        return f"{base_url}/{endpoint}"

    def close(self) -> None:
        """Explicitly close HTTP client and release resources."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        self.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *_):
        """Context manager exit."""
        self.close()


class AdapterError(Exception):
    """Base exception for adapter errors."""


class AuthenticationError(AdapterError):
    """Raised when authentication fails."""


class ValidationError(AdapterError):
    """Raised when validation fails."""


class UploadError(AdapterError):
    """Raised when upload fails."""


class DiscoveryError(AdapterError):
    """Raised when API discovery fails."""
