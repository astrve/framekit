from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename fallback when pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(
        filename: str, replacement_text: str = "_", platform: str | None = None
    ) -> str:
        """
        Sanitize a filename by replacing characters illegal on most filesystems.
        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        The platform argument is ignored.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


from framekit.core.i18n import tr
from framekit.core.languages import is_valid_language_filter
from framekit.core.models.cleanmkv import CleanPreset
from framekit.core.paths import get_presets_dir
from framekit.modules.cleanmkv.planner import BUILTIN_PRESETS

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
    if not preset.name.strip():
        raise ValueError(
            tr("cleanmkv.error.preset_name_empty", default="Preset name cannot be empty.")
        )

    for filter_value in preset.keep_audio_filters:
        if not is_valid_language_filter(filter_value):
            raise ValueError(
                tr(
                    "cleanmkv.error.invalid_audio_filter",
                    default="Invalid audio filter in preset: {value}",
                    value=filter_value,
                )
            )

    for filter_value in preset.keep_subtitle_filters:
        if not is_valid_language_filter(filter_value):
            raise ValueError(
                tr(
                    "cleanmkv.error.invalid_subtitle_filter",
                    default="Invalid subtitle filter in preset: {value}",
                    value=filter_value,
                )
            )

    for variant in preset.keep_subtitle_variants:
        if variant not in VALID_SUBTITLE_VARIANTS:
            raise ValueError(
                tr(
                    "cleanmkv.error.invalid_subtitle_variant",
                    default="Invalid subtitle variant in preset: {value}",
                    value=variant,
                )
            )

    if preset.default_audio_filter and not is_valid_language_filter(preset.default_audio_filter):
        raise ValueError(
            tr(
                "cleanmkv.error.invalid_default_audio_filter",
                default="Invalid default audio filter: {value}",
                value=preset.default_audio_filter,
            )
        )

    if preset.default_subtitle_filter and not is_valid_language_filter(
        preset.default_subtitle_filter
    ):
        raise ValueError(
            tr(
                "cleanmkv.error.invalid_default_subtitle_filter",
                default="Invalid default subtitle filter: {value}",
                value=preset.default_subtitle_filter,
            )
        )

    if (
        preset.default_subtitle_variant
        and preset.default_subtitle_variant not in VALID_SUBTITLE_VARIANTS
    ):
        raise ValueError(
            tr(
                "cleanmkv.error.invalid_default_subtitle_variant",
                default="Invalid default subtitle variant: {value}",
                value=preset.default_subtitle_variant,
            )
        )

    return preset


def preset_from_dict(data: dict) -> CleanPreset:
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
    return asdict(preset)


def load_preset_file(path: str | Path) -> CleanPreset:
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(
            tr(
                "cleanmkv.error.preset_file_object",
                default="Preset file must contain a JSON object.",
            )
        )

    return preset_from_dict(data)


def save_preset_file(preset: CleanPreset, path: str | Path) -> Path:
    validated = validate_preset(preset)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(preset_to_dict(validated), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return file_path


def save_named_preset(preset: CleanPreset, name: str) -> Path:
    display_name = name.strip()
    if not display_name:
        raise ValueError(
            tr("cleanmkv.error.preset_save_name_empty", default="Preset save name cannot be empty.")
        )

    safe_filename = _safe_preset_filename(display_name)
    target = get_presets_dir() / f"{safe_filename}.json"

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
    builtin = sorted(BUILTIN_PRESETS.keys())

    presets_dir = get_presets_dir()
    external: list[str] = []
    if presets_dir.exists():
        external = sorted(p.stem for p in presets_dir.glob("*.json"))

    return {
        "builtin": builtin,
        "external": external,
    }


def load_named_external_preset(name: str) -> CleanPreset:
    safe_filename = _safe_preset_filename(name)
    path = get_presets_dir() / f"{safe_filename}.json"
    if not path.exists():
        raise ValueError(
            tr(
                "cleanmkv.error.external_preset_not_found",
                default="External preset not found: {name}",
                name=name,
            )
        )
    return load_preset_file(path)
