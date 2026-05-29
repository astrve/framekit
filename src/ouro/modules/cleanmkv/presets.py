from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

try:
    import yaml  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - yaml is a hard dep elsewhere
    yaml = None  # type: ignore[assignment]

try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename fallback when pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(
        filename: str, replacement_text: str = "_", platform: str | None = None
    ) -> str:
        """Sanitize a filename by replacing characters illegal on most filesystems.

        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        The platform argument is ignored.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


from ouro.core.i18n import tr
from ouro.core.languages import is_valid_language_filter
from ouro.core.models.cleanmkv import CleanPreset
from ouro.core.paths import get_cleanmkv_presets_dir, get_presets_dir
from ouro.modules.cleanmkv.planner import BUILTIN_PRESETS

VALID_SUBTITLE_VARIANTS = {"forced", "full", "sdh"}


def _ensure_tuple_of_strings(value, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(
            tr(
                "cleanmkv.error.field_must_be_string_list",
                default="{field} must be a list of strings.",
                field=field_name,
            )
        )

    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                tr(
                    "cleanmkv.error.field_non_empty_strings",
                    default="{field} must only contain non-empty strings.",
                    field=field_name,
                )
            )
        cleaned.append(item.strip())

    return tuple(cleaned)


def _safe_preset_filename(name: str) -> str:
    cleaned = sanitize_filename(
        name.strip(),
        replacement_text="_",
        platform="universal",
    ).strip(" ._")
    return cleaned or "preset"


def validate_preset(preset: CleanPreset) -> CleanPreset:
    """Validate preset."""
    if not preset.name.strip():
        raise ValueError(
            tr("cleanmkv.error.preset_name_empty", default="Preset name cannot be empty.")
        )

    _validate_language_filters(
        preset.keep_audio_filters,
        error_key="cleanmkv.error.invalid_audio_filter",
        default_message="Invalid audio filter in preset: {value}",
    )
    _validate_language_filters(
        preset.keep_subtitle_filters,
        error_key="cleanmkv.error.invalid_subtitle_filter",
        default_message="Invalid subtitle filter in preset: {value}",
    )
    _validate_subtitle_variants(
        preset.keep_subtitle_variants,
        error_key="cleanmkv.error.invalid_subtitle_variant",
        default_message="Invalid subtitle variant in preset: {value}",
    )
    _validate_optional_language_filter(
        preset.default_audio_filter,
        error_key="cleanmkv.error.invalid_default_audio_filter",
        default_message="Invalid default audio filter: {value}",
    )
    _validate_optional_language_filter(
        preset.default_subtitle_filter,
        error_key="cleanmkv.error.invalid_default_subtitle_filter",
        default_message="Invalid default subtitle filter: {value}",
    )
    _validate_optional_subtitle_variant(
        preset.default_subtitle_variant,
        error_key="cleanmkv.error.invalid_default_subtitle_variant",
        default_message="Invalid default subtitle variant: {value}",
    )
    return preset


def _validate_language_filters(
    values: tuple[str, ...],
    *,
    error_key: str,
    default_message: str,
) -> None:
    for value in values:
        if not is_valid_language_filter(value):
            raise ValueError(tr(error_key, default=default_message, value=value))


def _validate_optional_language_filter(
    value: str | None,
    *,
    error_key: str,
    default_message: str,
) -> None:
    if value and not is_valid_language_filter(value):
        raise ValueError(tr(error_key, default=default_message, value=value))


def _validate_subtitle_variants(
    values: tuple[str, ...],
    *,
    error_key: str,
    default_message: str,
) -> None:
    for value in values:
        if value not in VALID_SUBTITLE_VARIANTS:
            raise ValueError(tr(error_key, default=default_message, value=value))


def _validate_optional_subtitle_variant(
    value: str | None,
    *,
    error_key: str,
    default_message: str,
) -> None:
    if value and value not in VALID_SUBTITLE_VARIANTS:
        raise ValueError(tr(error_key, default=default_message, value=value))


def preset_from_dict(data: dict) -> CleanPreset:
    """Handle preset from dict."""
    keep_audio_filters = data.get("keep_audio_filters", data.get("keep_audio_languages", []))
    default_audio_filter = data.get("default_audio_filter", data.get("default_audio_language"))
    keep_subtitle_filters = data.get(
        "keep_subtitle_filters", data.get("keep_subtitle_languages", [])
    )
    default_subtitle_filter = data.get(
        "default_subtitle_filter", data.get("default_subtitle_language")
    )

    preset = CleanPreset(
        name=str(data.get("name", "")).strip(),
        keep_audio_filters=_ensure_tuple_of_strings(keep_audio_filters, "keep_audio_filters"),
        default_audio_filter=(str(default_audio_filter).strip() if default_audio_filter else None),
        keep_subtitle_filters=_ensure_tuple_of_strings(
            keep_subtitle_filters, "keep_subtitle_filters"
        ),
        keep_subtitle_variants=_ensure_tuple_of_strings(
            data.get("keep_subtitle_variants", []), "keep_subtitle_variants"
        ),
        default_subtitle_filter=(
            str(default_subtitle_filter).strip() if default_subtitle_filter else None
        ),
        default_subtitle_variant=(
            str(data["default_subtitle_variant"]).strip()
            if data.get("default_subtitle_variant")
            else None
        ),
        audio_default_explicit=bool(data.get("audio_default_explicit", False)),
        subtitle_default_explicit=bool(data.get("subtitle_default_explicit", False)),
    )
    return validate_preset(preset)


def preset_to_dict(preset: CleanPreset) -> dict:
    """Handle preset to dict."""
    return asdict(preset)


def _unwrap_preset_payload(data: dict, *, preferred_key: str | None = None) -> dict:
    """Normalize preset payloads to a flat dict of preset fields.

    Some on-disk presets store the preset fields under a single top-level
    key matching the preset name (e.g. ``{"anime_multi_fr": {...}}``). When
    the outer dict already contains preset fields directly (``name`` /
    ``keep_audio_filters``), it is returned unchanged.

    ``preferred_key`` lets the caller (typically the loader) request a
    specific entry when several presets share a single YAML file.
    """
    if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]  # Defensive guard: YAML may yield non-dict at top level
        return data

    preset_field_markers = {
        "name",
        "keep_audio_filters",
        "keep_audio_languages",
        "keep_subtitle_filters",
        "keep_subtitle_languages",
        "keep_subtitle_variants",
    }
    if any(marker in data for marker in preset_field_markers):
        return data

    if preferred_key and preferred_key in data and isinstance(data[preferred_key], dict):
        return data[preferred_key]

    if len(data) == 1:
        only_value = next(iter(data.values()))
        if isinstance(only_value, dict):
            return only_value

    return data


def load_preset_file(path: str | Path, *, preset_key: str | None = None) -> CleanPreset:
    """Load preset file."""
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        if yaml is None:
            raise ValueError(
                tr(
                    "cleanmkv.error.preset_yaml_unsupported",
                    default="YAML preset support requires PyYAML to be installed.",
                )
            )
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(
            tr(
                "cleanmkv.error.preset_file_object",
                default="Preset file must contain a JSON object.",
            )
        )

    payload = _unwrap_preset_payload(data, preferred_key=preset_key or file_path.stem)
    return preset_from_dict(payload)


def save_preset_file(preset: CleanPreset, path: str | Path) -> Path:
    """Save preset file."""
    validated = validate_preset(preset)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(preset_to_dict(validated), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return file_path


def save_named_preset(preset: CleanPreset, name: str) -> Path:
    """Save a preset with the given name.

    Presets are saved to Presets/CleanMKV/ in the project directory.
    This provides better organization and makes presets portable with the project.

    Args:
        preset: The preset to save
        name: Display name for the preset

    Returns:
        Path to the saved preset file
    """
    display_name = name.strip()
    if not display_name:
        raise ValueError(
            tr("cleanmkv.error.preset_save_name_empty", default="Preset save name cannot be empty.")
        )

    safe_filename = _safe_preset_filename(display_name)
    # Use new project-level Presets/CleanMKV/ directory
    target = get_cleanmkv_presets_dir() / f"{safe_filename}.json"

    return save_preset_file(
        CleanPreset(
            name=display_name,
            keep_audio_filters=preset.keep_audio_filters,
            default_audio_filter=preset.default_audio_filter,
            keep_subtitle_filters=preset.keep_subtitle_filters,
            keep_subtitle_variants=preset.keep_subtitle_variants,
            default_subtitle_filter=preset.default_subtitle_filter,
            default_subtitle_variant=preset.default_subtitle_variant,
            audio_default_explicit=preset.audio_default_explicit,
            subtitle_default_explicit=preset.subtitle_default_explicit,
        ),
        target,
    )


def list_available_presets() -> dict[str, list[str]]:
    """List all available presets (builtin and external).

    Searches both the new Presets/CleanMKV/ directory and the legacy
    config/presets/ directory for backward compatibility.

    Returns:
        Dictionary with 'builtin' and 'external' preset lists
    """
    builtin = sorted(BUILTIN_PRESETS.keys())

    external: set[str] = set()

    def _scan(directory: Path) -> None:
        if not directory.exists():
            return
        for pattern in ("*.json", "*.yaml", "*.yml"):
            external.update(p.stem for p in directory.glob(pattern))

    # Check new project-level Presets/CleanMKV/ directory and legacy location.
    _scan(get_cleanmkv_presets_dir())
    _scan(get_presets_dir())

    return {
        "builtin": builtin,
        "external": sorted(external),
    }


def load_named_external_preset(name: str) -> CleanPreset:
    """Load an external preset by name.

    Searches both the new Presets/CleanMKV/ directory and the legacy
    config/presets/ directory for backward compatibility.

    Args:
        name: Name of the preset to load

    Returns:
        The loaded preset

    Raises:
        ValueError: If the preset is not found
    """
    safe_filename = _safe_preset_filename(name)

    for directory in (get_cleanmkv_presets_dir(), get_presets_dir()):
        for ext in (".json", ".yaml", ".yml"):
            candidate = directory / f"{safe_filename}{ext}"
            if candidate.exists():
                return load_preset_file(candidate, preset_key=safe_filename)

    raise ValueError(
        tr(
            "cleanmkv.error.external_preset_not_found",
            default="External preset not found: {name}",
            name=name,
        )
    )
