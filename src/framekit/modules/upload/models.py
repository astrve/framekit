"""Upload module data models.

Defines data structures for tracker configuration, torrent metadata,
upload results, and API discovery.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrackerConfig(BaseModel):
    """Configuration for a BitTorrent tracker."""

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    name: str
    type: str  # "unit3d", "gazelle", "custom", "c411"
    url: str
    api_key: str
    categories: dict[str, int] = Field(default_factory=dict)
    types: dict[str, int] = Field(default_factory=dict)
    resolutions: dict[str, int] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)
    retry_attempts: int = 3
    retry_delay: int = 5
    timeout: int = 300
    rate_limit_requests: int = 10
    rate_limit_period: int = 60

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in ("unit3d", "gazelle", "custom", "c411"):
            raise ValueError(f"Invalid tracker type: {v}")
        return v

    @field_validator("url")
    @classmethod
    def _check_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid tracker URL: {v}")
        return v

    @field_validator("retry_attempts")
    @classmethod
    def _check_retry(cls, v: int) -> int:
        if v < 1:
            raise ValueError("retry_attempts must be at least 1")
        return v

    @field_validator("timeout")
    @classmethod
    def _check_timeout(cls, v: int) -> int:
        if v < 1:
            raise ValueError("timeout must be at least 1 second")
        return v


class TorrentMetadata(BaseModel):
    """Metadata for torrent upload."""

    model_config = ConfigDict(validate_assignment=True)

    name: str
    description: str  # BBCode format
    category: str
    type: str  # Resolution type (1080p, 2160p, etc.)
    resolution: str  # Actual resolution (1920x1080, etc.)

    # Optional IDs
    tmdb_id: int | None = None
    imdb_id: str | None = None
    tvdb_id: int | None = None
    mal_id: int | None = None

    # Upload options
    anonymous: bool = False
    stream: bool = True
    sd: bool = False
    internal: bool = False

    # Additional metadata (Phase 1 additions)
    source: str | None = None  # BluRay, WEB-DL, HDTV, etc.
    codec: str | None = None  # x265, x264, etc.
    audio: str | None = None  # Atmos, TrueHD, DTS, etc.
    hdr: str | None = None  # HDR10, DV, etc.
    tags: list[str] = Field(default_factory=list)
    image_url: str | None = None

    # Optional file attachment for trackers requiring an NFO upload.
    nfo_path: str | None = None

    # C411-specific payload fields.
    c411_category_id: int | None = None
    c411_subcategory_id: int | None = None
    c411_options: dict[str, Any] = Field(default_factory=dict)
    c411_description_format: str | None = None
    c411_uploader_note: str | None = None
    c411_draft: bool = False
    tmdb_data: dict[str, Any] | None = None
    rawg_data: dict[str, Any] | None = None

    @field_validator("name", "description", "category")
    @classmethod
    def _not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Field cannot be empty")
        return v

    @field_validator("imdb_id", mode="before")
    @classmethod
    def _normalize_imdb(cls, v: object) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if not s.startswith("tt"):
            return f"tt{s}"
        return s


@dataclass
class UploadResult:
    """Result of a torrent upload operation."""

    success: bool
    tracker: str
    torrent_id: int | None = None
    url: str | None = None
    message: str = ""
    errors: list[str] = field(default_factory=list)
    upload_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    # Phase 1 additions
    verified: bool = False
    verification_message: str = ""

    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        self.success = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "tracker": self.tracker,
            "torrent_id": self.torrent_id,
            "url": self.url,
            "message": self.message,
            "errors": self.errors,
            "upload_time": self.upload_time,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class DiscoveryResult:
    """Result of tracker API discovery."""

    tracker_type: str
    tracker_url: str
    categories: dict[str, int] = field(default_factory=dict)
    types: dict[str, int] = field(default_factory=dict)
    resolutions: dict[str, int] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    api_version: str | None = None
    success: bool = True
    errors: list[str] = field(default_factory=list)

    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
        self.success = False

    def to_config(self, name: str, api_key: str) -> TrackerConfig:
        """Convert discovery result to tracker configuration."""
        return TrackerConfig(
            name=name,
            type=self.tracker_type,
            url=self.tracker_url,
            api_key=api_key,
            categories=self.categories,
            types=self.types,
            resolutions=self.resolutions,
            defaults={"anonymous": False, "stream": True, "sd": False, "internal": False},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tracker_type": self.tracker_type,
            "tracker_url": self.tracker_url,
            "categories": self.categories,
            "types": self.types,
            "resolutions": self.resolutions,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "api_version": self.api_version,
            "success": self.success,
            "errors": self.errors,
        }


@dataclass
class TorrentFile:
    """Represents a torrent file for upload."""

    path: Path
    name: str
    size: int
    info_hash: str | None = None
    announce_url: str | None = None

    def __post_init__(self):
        """Validate torrent file after initialization."""
        if not self.path.exists():
            raise FileNotFoundError(f"Torrent file not found: {self.path}")

        if not self.path.suffix == ".torrent":
            raise ValueError(f"Invalid torrent file extension: {self.path.suffix}")

        self.size = self.path.stat().st_size
        self.name = self.path.name

    def validate(self) -> bool:
        """Validate torrent file structure."""
        try:
            # ``bencode-open`` ships ``loads`` rather than the older
            # ``bencode.bdecode`` API. Keep the import local so non-torrent
            # environments only fail when validation is actually used.
            from bencode_open import loads as bdecode

            with open(self.path, "rb") as f:
                data = cast(dict[bytes, Any], bdecode(f.read()))

            # Check required fields
            if b"info" not in data:
                return False

            if b"announce" in data:
                self.announce_url = data[b"announce"].decode("utf-8")

            return True
        except Exception:
            return False
