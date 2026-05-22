"""Upload presets management for storing and applying metadata configurations.

Provides a system for saving, loading, and applying preset configurations
to streamline the upload process with commonly used metadata patterns.
"""

from dataclasses import asdict, dataclass, field

import yaml

from framekit.core.paths import get_config_dir
from framekit.modules.upload.models import TorrentMetadata


@dataclass
class UploadPreset:
    """Preset configuration for upload metadata."""

    name: str
    description: str = ""
    category: str = ""
    type: str = ""
    resolution: str = ""
    anonymous: bool = False
    stream: bool = True
    tags: list[str] = field(default_factory=list)
    image_host: str = ""


class PresetManager:
    """Manage upload presets stored in framekit.yaml."""

    def __init__(self):
        self.config_path = get_config_dir() / "framekit.yaml"

    def _load_config(self) -> dict:
        """Load framekit.yaml configuration."""
        if not self.config_path.exists():
            return {}
        with open(self.config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save_config(self, config: dict) -> None:
        """Save configuration to framekit.yaml."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)

    def list_presets(self) -> list[UploadPreset]:
        """List all saved presets."""
        config = self._load_config()
        presets_data = config.get("upload", {}).get("presets", [])
        return [UploadPreset(**p) for p in presets_data]

    def get_preset(self, name: str) -> UploadPreset | None:
        """Get a preset by name."""
        presets = self.list_presets()
        for preset in presets:
            if preset.name == name:
                return preset
        return None

    def save_preset(self, preset: UploadPreset) -> None:
        """Save or update a preset."""
        config = self._load_config()
        if "upload" not in config:
            config["upload"] = {}
        if "presets" not in config["upload"]:
            config["upload"]["presets"] = []

        # Remove existing preset with same name
        config["upload"]["presets"] = [
            p for p in config["upload"]["presets"] if p.get("name") != preset.name
        ]

        # Add new preset
        config["upload"]["presets"].append(asdict(preset))
        self._save_config(config)

    def delete_preset(self, name: str) -> bool:
        """Delete a preset by name. Returns True if deleted."""
        config = self._load_config()
        if "upload" not in config or "presets" not in config["upload"]:
            return False

        original_count = len(config["upload"]["presets"])
        config["upload"]["presets"] = [
            p for p in config["upload"]["presets"] if p.get("name") != name
        ]

        if len(config["upload"]["presets"]) < original_count:
            self._save_config(config)
            return True
        return False

    def apply_to_metadata(self, preset: UploadPreset, metadata: TorrentMetadata) -> TorrentMetadata:
        """Apply preset to metadata. Existing metadata values take priority.

        Returns a new TorrentMetadata instance.
        """
        return TorrentMetadata(
            name=metadata.name,
            description=metadata.description,
            category=metadata.category or preset.category,
            type=metadata.type or preset.type,
            resolution=metadata.resolution or preset.resolution,
            tmdb_id=metadata.tmdb_id,
            imdb_id=metadata.imdb_id,
            tvdb_id=metadata.tvdb_id,
            anonymous=preset.anonymous,  # Use preset value
            stream=preset.stream,  # Use preset value
            source=metadata.source,
            codec=metadata.codec,
            audio=metadata.audio,
            hdr=metadata.hdr,
            tags=metadata.tags or preset.tags,
        )
