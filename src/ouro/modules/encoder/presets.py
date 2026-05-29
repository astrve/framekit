"""Preset management for the Encoder module."""

from pathlib import Path
from typing import Any

import yaml

from .models import (
    AdvancedConfig,
    AudioConfig,
    ChapterConfig,
    EncodePreset,
    MetadataConfig,
    SubtitleConfig,
    VideoConfig,
)


class PresetLoader:
    """Load and manage encoding presets."""

    def __init__(self, presets_dir: Path | None = None):
        """Initialize preset loader.

        Args:
            presets_dir: Directory containing preset files. If None, uses default.
        """
        if presets_dir is None:
            from ouro.core.paths import get_project_presets_dir

            self.presets_dir = get_project_presets_dir() / "Encoder"
        else:
            self.presets_dir = Path(presets_dir)

    def load_preset(self, preset_path: Path) -> EncodePreset:
        """Load a preset from a YAML file.

        Args:
            preset_path: Path to the preset YAML file

        Returns:
            EncodePreset object

        Raises:
            FileNotFoundError: If preset file doesn't exist
            ValueError: If preset format is invalid
        """
        if not preset_path.exists():
            raise FileNotFoundError(f"Preset file not found: {preset_path}")

        with open(preset_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return self._parse_preset(data)

    def load_preset_by_name(self, name: str) -> EncodePreset:
        """Load a preset by name or alias (searches in presets directory).

        Args:
            name: Preset name or alias (e.g., 'films', 'f265', 'series_h264')

        Returns:
            EncodePreset object

        Raises:
            FileNotFoundError: If preset not found
        """
        # Try to find the preset file by exact name first
        for direction in ["h264_to_h265", "h265_to_h264"]:
            preset_path = self.presets_dir / direction / f"{name}.yaml"
            if preset_path.exists():
                return self.load_preset(preset_path)

        # Try to find by alias
        preset_path = self._find_preset_by_alias(name)
        if preset_path:
            return self.load_preset(preset_path)

        raise FileNotFoundError(f"Preset '{name}' not found in {self.presets_dir}")

    def _find_preset_by_alias(self, alias: str) -> Path | None:
        """Find a preset file by alias.

        Args:
            alias: Preset alias to search for

        Returns:
            Path to preset file if found, None otherwise
        """
        for direction in ["h264_to_h265", "h265_to_h264"]:
            direction_path = self.presets_dir / direction
            if direction_path.exists():
                for preset_file in direction_path.glob("*.yaml"):
                    try:
                        with open(preset_file, encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                        aliases = data.get("aliases", [])
                        if alias in aliases:
                            return preset_file
                    except Exception:  # nosec B112
                        continue
        return None

    def list_presets(self) -> dict[str, list[str]]:
        """List all available presets.

        Returns:
            Dictionary with direction as key and list of preset names as value
        """
        presets = {"h264_to_h265": [], "h265_to_h264": []}

        for direction in presets:
            direction_path = self.presets_dir / direction
            if direction_path.exists():
                for preset_file in direction_path.glob("*.yaml"):
                    presets[direction].append(preset_file.stem)

        return presets

    def get_preset_info(self, name: str) -> dict[str, Any]:
        """Get basic information about a preset without loading it fully.

        Args:
            name: Preset name or alias

        Returns:
            Dictionary with name, description, source_codec, target_codec, aliases
        """
        # Try exact name first
        for direction in ["h264_to_h265", "h265_to_h264"]:
            preset_path = self.presets_dir / direction / f"{name}.yaml"
            if preset_path.exists():
                with open(preset_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return {
                    "name": data.get("name", name),
                    "description": data.get("description", ""),
                    "source_codec": data.get("source_codec", ""),
                    "target_codec": data.get("target_codec", ""),
                    "encoder": data.get("encoder", ""),
                    "aliases": data.get("aliases", []),
                }

        # Try by alias
        preset_path = self._find_preset_by_alias(name)
        if preset_path:
            with open(preset_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return {
                "name": data.get("name", preset_path.stem),
                "description": data.get("description", ""),
                "source_codec": data.get("source_codec", ""),
                "target_codec": data.get("target_codec", ""),
                "encoder": data.get("encoder", ""),
                "aliases": data.get("aliases", []),
            }

        raise FileNotFoundError(f"Preset '{name}' not found")

    def list_all_aliases(self) -> dict[str, list[str]]:
        """List all available aliases for all presets.

        Returns:
            Dictionary mapping preset names to their aliases
        """
        aliases_map = {}

        for direction in ["h264_to_h265", "h265_to_h264"]:
            direction_path = self.presets_dir / direction
            if direction_path.exists():
                for preset_file in direction_path.glob("*.yaml"):
                    try:
                        with open(preset_file, encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                        preset_name = preset_file.stem
                        aliases = data.get("aliases", [])
                        if aliases:
                            aliases_map[preset_name] = aliases
                    except Exception:  # nosec B112
                        continue

        return aliases_map

    def _parse_preset(self, data: dict[str, Any]) -> EncodePreset:
        """Parse preset data from dictionary.

        Args:
            data: Preset data dictionary

        Returns:
            EncodePreset object

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        required_fields = ["name", "description", "source_codec", "target_codec", "encoder"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Parse video config
        video_data = data.get("video", {})
        video = VideoConfig(
            crf=video_data.get("crf", 23),
            preset=video_data.get("preset", "medium"),
            tune=video_data.get("tune"),
            profile=video_data.get("profile", "main"),
            level=video_data.get("level", "4.1"),
            pix_fmt=video_data.get("pix_fmt", "yuv420p"),
        )

        # Parse audio config
        audio_data = data.get("audio", {})
        audio = AudioConfig(
            copy=audio_data.get("copy", True),
            codec=audio_data.get("codec"),
            bitrate=audio_data.get("bitrate"),
        )

        # Parse subtitle config
        subtitle_data = data.get("subtitles", {})
        subtitles = SubtitleConfig(copy=subtitle_data.get("copy", True))

        # Parse metadata config
        metadata_data = data.get("metadata", {})
        metadata = MetadataConfig(preserve=metadata_data.get("preserve", True))

        # Parse chapter config
        chapter_data = data.get("chapters", {})
        chapters = ChapterConfig(preserve=chapter_data.get("preserve", True))

        # Parse advanced config
        advanced_data = data.get("advanced", {})
        advanced = AdvancedConfig(
            two_pass=advanced_data.get("two_pass", False),
            x264_params=advanced_data.get("x264_params", []),
            x265_params=advanced_data.get("x265_params", []),
        )

        return EncodePreset(
            name=data["name"],
            description=data["description"],
            source_codec=data["source_codec"],
            target_codec=data["target_codec"],
            encoder=data["encoder"],
            video=video,
            audio=audio,
            subtitles=subtitles,
            metadata=metadata,
            chapters=chapters,
            advanced=advanced,
        )

    def create_preset_template(self, output_path: Path, preset_type: str = "h264_to_h265") -> None:
        """Create a preset template file.

        Args:
            output_path: Path where to save the template
            preset_type: Type of preset ('h264_to_h265' or 'h265_to_h264')
        """
        if preset_type == "h264_to_h265":
            template = {
                "name": "Custom h264 to h265",
                "description": "Custom preset for h264 to h265 encoding",
                "source_codec": "h264",
                "target_codec": "h265",
                "encoder": "libx265",
                "video": {
                    "crf": 20,
                    "preset": "medium",
                    "tune": None,
                    "profile": "main10",
                    "level": "5.1",
                    "pix_fmt": "yuv420p10le",
                },
                "audio": {"copy": True},
                "subtitles": {"copy": True},
                "metadata": {"preserve": True},
                "chapters": {"preserve": True},
                "advanced": {"two_pass": False, "x265_params": ["aq-mode=3", "aq-strength=0.8"]},  # nosec B105
            }
        else:  # h265_to_h264
            template = {
                "name": "Custom h265 to h264",
                "description": "Custom preset for h265 to h264 encoding",
                "source_codec": "h265",
                "target_codec": "h264",
                "encoder": "libx264",
                "video": {
                    "crf": 20,
                    "preset": "medium",
                    "tune": None,
                    "profile": "high",
                    "level": "4.1",
                    "pix_fmt": "yuv420p",
                },
                "audio": {"copy": True},
                "subtitles": {"copy": True},
                "metadata": {"preserve": True},
                "chapters": {"preserve": True},
                "advanced": {"two_pass": False, "x264_params": ["aq-mode=3", "aq-strength=0.8"]},  # nosec B105
            }

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(template, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
