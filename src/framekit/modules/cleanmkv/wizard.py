from __future__ import annotations

from framekit.core.i18n import tr
from framekit.core.languages import (
    language_filter_display_label,
    language_filter_short_label,
)
from framekit.core.models.cleanmkv import CleanPreset, MkvFileScan, TrackInfo
from framekit.modules.cleanmkv.tracks import (
    track_reference_hint,
    track_reference_key,
    track_reference_label,
)
from framekit.ui.selector import SelectorDivider, SelectorOption, select_many, select_one

LANGUAGE_FILTER_CHOICES = [
    "french",
    "french:canada",
    "english",
    "english:us",
    "english:uk",
    "japanese",
    "spanish",
    "spanish:latam",
    "italian",
    "german",
    "portuguese",
    "russian",
    "turkish",
    "polish",
    "arabic",
    "indonesian",
]

SUBTITLE_VARIANTS = [
    "forced",
    "full",
    "sdh",
]


def _variant_display_label(value: str) -> str:
    if value == "sdh":
        return "SDH"
    return tr(f"cleanmkv.subtitle_variant.{value}", default=value.replace("_", " ").title())


def _language_entries(enabled_values: tuple[str, ...] = ()) -> list[SelectorOption[str]]:
    return [
        SelectorOption(
            value=value,
            label=language_filter_display_label(value),
            hint=language_filter_short_label(value),
            selected=False,
        )
        for value in LANGUAGE_FILTER_CHOICES
    ]


def _variant_entries(enabled_values: tuple[str, ...] = ()) -> list[SelectorOption[str]]:
    return [
        SelectorOption(
            value=value,
            label=_variant_display_label(value),
            hint=tr("cleanmkv.subtitle_variant_hint", default="subtitle variant"),
            selected=False,
        )
        for value in SUBTITLE_VARIANTS
    ]


def run_cleanmkv_wizard() -> CleanPreset:
    keep_audio_filters = tuple(
        select_many(
            title=tr("cleanmkv.wizard.audio_filters", default="Audio Filters"),
            entries=[
                SelectorDivider(
                    tr("cleanmkv.wizard.languages_variants", default="Languages / Variants")
                ),
                *_language_entries(),
            ],
            page_size=12,
            minimal_count=0,
        )
    )

    default_audio_candidates = (
        list(keep_audio_filters) if keep_audio_filters else LANGUAGE_FILTER_CHOICES
    )
    default_audio_filter = select_one(
        title=tr("cleanmkv.wizard.default_audio_filter", default="Default Audio Filter"),
        entries=[
            SelectorDivider(tr("common.default", default="Default")),
            SelectorOption(
                value=None,
                label=tr("common.none", default="None"),
                hint=tr("cleanmkv.wizard.no_default_track", default="no default track"),
            ),
            *[
                SelectorOption(
                    value=value,
                    label=language_filter_display_label(value),
                    hint=language_filter_short_label(value),
                )
                for value in default_audio_candidates
            ],
        ],
        page_size=12,
    )

    keep_subtitle_filters = tuple(
        select_many(
            title=tr("cleanmkv.wizard.subtitle_filters", default="Subtitle Filters"),
            entries=[
                SelectorDivider(
                    tr("cleanmkv.wizard.languages_variants", default="Languages / Variants")
                ),
                *_language_entries(),
            ],
            page_size=12,
            minimal_count=0,
        )
    )

    keep_subtitle_variants = tuple(
        select_many(
            title=tr("cleanmkv.wizard.subtitle_variants", default="Subtitle Variants"),
            entries=[
                SelectorDivider(tr("cleanmkv.wizard.variants", default="Variants")),
                *_variant_entries(("forced", "full")),
            ],
            page_size=6,
            minimal_count=0,
        )
    )

    if keep_subtitle_filters:
        default_subtitle_filter = select_one(
            title=tr("cleanmkv.wizard.default_subtitle_filter", default="Default Subtitle Filter"),
            entries=[
                SelectorDivider(tr("common.default", default="Default")),
                SelectorOption(
                    value=None,
                    label=tr("common.none", default="None"),
                    hint=tr("cleanmkv.wizard.no_default_subtitle", default="no default subtitle"),
                ),
                *[
                    SelectorOption(
                        value=value,
                        label=language_filter_display_label(value),
                        hint=language_filter_short_label(value),
                    )
                    for value in keep_subtitle_filters
                ],
            ],
            page_size=12,
        )
    else:
        default_subtitle_filter = None

    if default_subtitle_filter and keep_subtitle_variants:
        default_subtitle_variant = select_one(
            title=tr(
                "cleanmkv.wizard.default_subtitle_variant", default="Default Subtitle Variant"
            ),
            entries=[
                SelectorDivider(tr("common.default", default="Default")),
                SelectorOption(
                    value=None,
                    label=tr("common.none", default="None"),
                    hint=tr("cleanmkv.wizard.no_default_subtitle", default="no default subtitle"),
                ),
                *[
                    SelectorOption(
                        value=value,
                        label=_variant_display_label(value),
                        hint=tr("cleanmkv.subtitle_variant_hint", default="subtitle variant"),
                    )
                    for value in keep_subtitle_variants
                ],
            ],
            page_size=6,
        )
    else:
        default_subtitle_variant = None

    return CleanPreset(
        name="wizard",
        keep_audio_filters=keep_audio_filters,
        default_audio_filter=default_audio_filter,
        keep_subtitle_filters=keep_subtitle_filters,
        keep_subtitle_variants=keep_subtitle_variants,
        default_subtitle_filter=default_subtitle_filter,
        default_subtitle_variant=default_subtitle_variant,
    )


def _track_entry_counts(
    scans: list[MkvFileScan], *, kind: str
) -> dict[str, tuple[TrackInfo, set[str]]]:
    result: dict[str, tuple[TrackInfo, set[str]]] = {}
    for scan in scans:
        tracks = scan.audio_tracks if kind == "audio" else scan.subtitle_tracks
        for track in tracks:
            ref = track_reference_key(track)
            if ref not in result:
                result[ref] = (track, set())
            result[ref][1].add(str(scan.path))
    return result


def _track_entries(
    scans: list[MkvFileScan],
    *,
    kind: str,
    enabled_values: tuple[str, ...] = (),
) -> list[SelectorOption[str]]:
    total = len(scans)
    entries: list[SelectorOption[str]] = []
    for ref, (track, paths) in sorted(
        _track_entry_counts(scans, kind=kind).items(),
        key=lambda item: (track_reference_label(item[1][0]).lower(), item[0]),
    ):
        entries.append(
            SelectorOption(
                value=ref,
                label=track_reference_label(track),
                hint=track_reference_hint(track, available_count=len(paths), total_count=total),
                selected=False,
            )
        )
    return entries


def _default_refs(scans: list[MkvFileScan], *, kind: str) -> tuple[str, ...]:
    refs: list[str] = []
    for scan in scans:
        tracks = scan.audio_tracks if kind == "audio" else scan.subtitle_tracks
        for track in tracks:
            if track.is_default:
                ref = track_reference_key(track)
                if ref not in refs:
                    refs.append(ref)
    return tuple(refs)


def _all_refs(scans: list[MkvFileScan], *, kind: str) -> tuple[str, ...]:
    return tuple(_track_entry_counts(scans, kind=kind).keys())


def _first_existing_ref(candidates: tuple[str, ...], allowed: tuple[str, ...]) -> str | None:
    allowed_set = set(allowed)
    for ref in candidates:
        if ref in allowed_set:
            return ref
    return allowed[0] if allowed else None


def run_cleanmkv_track_selector(scans: list[MkvFileScan]) -> CleanPreset:
    audio_defaults = _all_refs(scans, kind="audio")
    subtitle_defaults = _all_refs(scans, kind="subtitle")

    keep_audio_refs = tuple(
        select_many(
            title=tr("cleanmkv.selector.audio_tracks", default="Audio Tracks Found"),
            entries=[
                SelectorDivider(
                    tr("cleanmkv.selector.current_audio", default="Current audio tracks")
                ),
                *_track_entries(scans, kind="audio", enabled_values=audio_defaults),
            ],
            page_size=12,
            minimal_count=1,
        )
    )

    default_audio_ref = select_one(
        title=tr("cleanmkv.selector.default_audio", default="Default Audio Track"),
        entries=[
            SelectorDivider(tr("common.default", default="Default")),
            *[
                SelectorOption(
                    value=option.value,
                    label=option.label,
                    hint=option.hint,
                    selected=False,
                )
                for option in _track_entries(scans, kind="audio")
                if option.value in keep_audio_refs
            ],
        ],
        page_size=12,
    )

    keep_subtitle_refs = tuple(
        select_many(
            title=tr("cleanmkv.selector.subtitle_tracks", default="Subtitle Tracks Found"),
            entries=[
                SelectorDivider(
                    tr("cleanmkv.selector.current_subtitles", default="Current subtitle tracks")
                ),
                *_track_entries(scans, kind="subtitle", enabled_values=subtitle_defaults),
            ],
            page_size=12,
            minimal_count=0,
        )
    )

    if keep_subtitle_refs:
        default_subtitle_ref = select_one(
            title=tr("cleanmkv.selector.default_subtitle", default="Default Subtitle Track"),
            entries=[
                SelectorDivider(tr("common.default", default="Default")),
                SelectorOption(
                    value=None,
                    label=tr("common.none", default="None"),
                    hint=tr("cleanmkv.wizard.no_default_subtitle", default="no default subtitle"),
                    selected=False,
                ),
                *[
                    SelectorOption(
                        value=option.value,
                        label=option.label,
                        hint=option.hint,
                        selected=False,
                    )
                    for option in _track_entries(scans, kind="subtitle")
                    if option.value in keep_subtitle_refs
                ],
            ],
            page_size=12,
        )
    else:
        default_subtitle_ref = None

    return CleanPreset(
        name="selector",
        keep_audio_filters=(),
        default_audio_filter=None,
        keep_subtitle_filters=(),
        keep_subtitle_variants=(),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
        keep_audio_track_refs=keep_audio_refs,
        default_audio_track_ref=default_audio_ref,
        keep_subtitle_track_refs=keep_subtitle_refs,
        default_subtitle_track_ref=default_subtitle_ref,
    )
