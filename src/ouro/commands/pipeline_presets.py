"""Pipeline preset management functions.

This module handles loading, listing, and selecting pipeline presets.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ouro.core.i18n import tr
from ouro.core.paths import get_config_dir, get_pipeline_presets_dir
from ouro.ui.console import print_error, print_warning
from ouro.ui.unified_selector import SelectorDivider, SelectorEntry, SelectorOption
from ouro.ui.unified_selector import select_one as _select_one


def get_pipeline_preset_dirs() -> list[Path]:
    """Return candidate preset directories: CWD first, then user config dir.

    Returns:
        List of preset directory paths
    """
    return [get_pipeline_presets_dir(), get_pipeline_presets_dir(get_config_dir())]


def load_pipeline_preset(preset_name: str) -> dict | None:
    """Load a pipeline preset from CWD or user config dir.

    Args:
        preset_name: Name of the preset (without .yaml extension)

    Returns:
        Preset configuration dict or None if not found
    """
    for preset_dir in get_pipeline_preset_dirs():
        preset_file = preset_dir / f"{preset_name}.yaml"
        if not preset_file.exists():
            continue
        try:
            with open(preset_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict) and preset_name in data:
                    return data[preset_name]
                if isinstance(data, dict) and "name" in data:
                    return data
        except Exception:
            return None
    return None


def list_pipeline_presets() -> list[str]:
    """List available pipeline presets from CWD and user config dir (deduplicated).

    Returns:
        Sorted list of preset names
    """
    seen: set[str] = set()
    for preset_dir in get_pipeline_preset_dirs():
        if not preset_dir.exists():
            continue
        for file in preset_dir.glob("*.yaml"):
            if file.stem not in ("example",) and file.stem not in seen:
                seen.add(file.stem)
    return sorted(seen)


def select_pipeline_preset() -> str | None:
    """Interactive preset selector for pipeline presets.

    Returns:
        Selected preset name or None if cancelled
    """
    available_presets = list_pipeline_presets()

    if not available_presets:
        print_warning(
            tr(
                "pipeline.preset.none_available",
                default="No pipeline presets found in Presets/Pipeline/",
            )
        )
        return None

    entries: list[SelectorEntry] = []
    entries.append(
        SelectorDivider(tr("pipeline.preset.available", default="Available Pipeline Presets"))
    )

    for preset_name in available_presets:
        preset_data = load_pipeline_preset(preset_name)
        description = ""
        if preset_data:
            description = preset_data.get("description", "")

        entries.append(
            SelectorOption(
                value=preset_name,
                label=preset_data.get("name", preset_name) if preset_data else preset_name,
                hint=description,
                selected=preset_name == "default",
            )
        )

    try:
        result = select_one(
            title=tr("pipeline.preset.select", default="Select pipeline preset"),
            entries=entries,
            page_size=12,
        )
        return result
    except KeyboardInterrupt:
        return None


def load_preset_config(preset_name: str) -> dict | None:
    """Load preset configuration from YAML file (legacy compatibility).

    This function is kept for backward compatibility. New code should use
    load_pipeline_preset() instead.

    Args:
        preset_name: Name of the preset (without .yaml extension)

    Returns:
        Preset configuration dict or None if not found
    """
    return load_pipeline_preset(preset_name)


# Legacy alias for backward compatibility
_select_pipeline_preset = select_pipeline_preset


def _load_preset_config_legacy(preset_name: str) -> dict | None:
    """Load preset configuration from YAML file (old implementation).

    Kept for reference but not used. Use load_pipeline_preset() instead.

    Args:
        preset_name: Name of the preset (without .yaml extension)

    Returns:
        Preset configuration dict or None if not found
    """
    import yaml as _yaml

    presets_dir = get_pipeline_presets_dir()
    preset_path = presets_dir / f"{preset_name}.yaml"

    if not preset_path.exists():
        print_error(
            tr(
                "pipeline.preset.not_found",
                default="Preset not found: {name}",
                name=preset_name,
            )
        )
        return None

    try:
        with open(preset_path, encoding="utf-8") as f:
            return _yaml.safe_load(f)
    except Exception as e:
        print_error(
            tr(
                "pipeline.preset.load_error",
                default="Failed to load preset {name}: {error}",
                name=preset_name,
                error=str(e),
            )
        )
        return None
    """Load preset configuration from YAML file.

    Args:
        preset_name: Name of the preset (without .yaml extension)

    Returns:
        Preset configuration dict or None if not found
    """
    import yaml

    presets_dir = get_pipeline_presets_dir()
    preset_path = presets_dir / f"{preset_name}.yaml"

    if not preset_path.exists():
        print_error(
            tr(
                "pipeline.preset.not_found",
                default="Preset not found: {name}",
                name=preset_name,
            )
        )
        return None

    try:
        with open(preset_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print_error(
            tr(
                "pipeline.preset.load_error",
                default="Failed to load preset {name}: {error}",
                name=preset_name,
                error=str(e),
            )
        )
        return None


select_one = _select_one  # backwards-compatible patch target for tests
