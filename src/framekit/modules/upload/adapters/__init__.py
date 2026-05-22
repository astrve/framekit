"""Tracker adapters for upload module.

Provides adapters for different tracker types:
- UNIT3D: c411, BeyondHD, Blutopia, etc.
- Gazelle: RED, OPS, etc.
- Custom: Template for custom trackers
"""

from .base import (
    AdapterError,
    AuthenticationError,
    DiscoveryError,
    TrackerAdapter,
    UploadError,
    ValidationError,
)
from .c411 import C411Adapter
from .custom import CustomAdapter
from .gazelle import GazelleAdapter
from .unit3d import UNIT3DAdapter

__all__ = [
    "AdapterError",
    "AuthenticationError",
    "C411Adapter",
    "CustomAdapter",
    "DiscoveryError",
    "GazelleAdapter",
    "TrackerAdapter",
    "UNIT3DAdapter",
    "UploadError",
    "ValidationError",
]
