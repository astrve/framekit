"""Upload module for automatic torrent uploads to private trackers.

Supports multiple tracker types:
- UNIT3D (c411, BeyondHD, Blutopia, etc.)
- Gazelle (RED, OPS, etc.)
- Custom trackers

Features:
- Multi-tracker architecture with adapters
- Auto-discovery of tracker APIs
- Secure API key storage in vault
- Retry logic with exponential backoff
- Comprehensive validation
- Integration with pipeline module
"""

from .adapters import (
    AdapterError,
    AuthenticationError,
    C411Adapter,
    CustomAdapter,
    DiscoveryError,
    GazelleAdapter,
    TrackerAdapter,
    UNIT3DAdapter,
    UploadError,
    ValidationError,
)
from .discovery import DiscoveryService
from .models import DiscoveryResult, TorrentFile, TorrentMetadata, TrackerConfig, UploadResult
from .service import UploadService

__all__ = [
    # Exceptions
    "AdapterError",
    "AuthenticationError",
    "C411Adapter",
    "CustomAdapter",
    "DiscoveryError",
    "DiscoveryResult",
    "DiscoveryService",
    "GazelleAdapter",
    "TorrentFile",
    "TorrentMetadata",
    # Adapters
    "TrackerAdapter",
    # Models
    "TrackerConfig",
    "UNIT3DAdapter",
    "UploadError",
    "UploadResult",
    # Services
    "UploadService",
    "ValidationError",
]
