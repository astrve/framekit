"""Tracker adapters for upload module.

Provides adapters for different tracker types:
- UNIT3D: BeyondHD, Blutopia, etc.
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
from .custom import CustomAdapter
from .custom_json_api_v1 import CustomJsonApiAdapter
from .gazelle import GazelleAdapter
from .unit3d import UNIT3DAdapter

__all__ = [
    "AdapterError",
    "AuthenticationError",
    "CustomJsonApiAdapter",
    "CustomAdapter",
    "DiscoveryError",
    "GazelleAdapter",
    "TrackerAdapter",
    "UNIT3DAdapter",
    "UploadError",
    "ValidationError",
]
