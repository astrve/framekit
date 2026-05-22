from __future__ import annotations

from framekit.core.i18n import tr
from framekit.core.languages import (
    language_filter_display_label,
    language_filter_short_label,
)
from framekit.core.models.cleanmkv import CleanPreset, MkvFileScan, TrackInfo
from framekit.modules.cleanmkv.tracks import (
    track_display_grouping_key,
    track_grouped_label,
    track_reference_hint,
    track_reference_key,
)
from framekit.ui.unified_selector import SelectionItem, UnifiedSelector

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


def _select_many_values(
    *,
    title: str,
    items: list[SelectionItem[str]],
    page_size: int,
    allow_empty: bool,
) -> tuple[str, ...]:
    result = UnifiedSelector[str](
        title=title,
        items=items,
        multi=True,
        page_size=page_size,
        allow_empty=allow_empty,
    ).select()
    return tuple(result.items)


def _select_one_value(
    *,
    title: str,
    items: list[SelectionItem[str | None]],
    page_size: int,
) -> str | None:
    result = UnifiedSelector[str | None](
        title=title,
        items=items,
        multi=False,
        page_size=page_size,
    ).select()
    return result.value


def _language_entries(
    enabled_values: tuple[str, ...] = (),
    *,
    group: str | None = None,
) -> list[SelectionItem[str]]:
    return [
        SelectionItem(
            value=value,
            label=language_filter_display_label(value),
            description=language_filter_short_label(value),
            preselected=value in enabled_values,
            group=group,
        )
        for value in LANGUAGE_FILTER_CHOICES
    ]


def _variant_entries(
    enabled_values: tuple[str, ...] = (),
    *,
    group: str | None = None,
) -> list[SelectionItem[str]]:
    return [
        SelectionItem(
            value=value,
            label=_variant_display_label(value),
            description=tr("cleanmkv.subtitle_variant_hint", default="subtitle variant"),
            preselected=value in enabled_values,
            group=group,
        )
        for value in SUBTITLE_VARIANTS
    ]


def run_cleanmkv_wizard() -> CleanPreset:
    """Run cleanmkv wizard."""
    keep_audio_filters = _select_many_values(
        title=tr("cleanmkv.wizard.audio_filters", default="Audio Filters"),
        items=_language_entries(
            group=tr("cleanmkv.wizard.languages_variants", default="Languages / Variants")
        ),
        page_size=12,
        allow_empty=True,
    )

    default_audio_candidates = (
        list(keep_audio_filters) if keep_audio_filters else LANGUAGE_FILTER_CHOICES
    )
    default_audio_filter = _select_one_value(
        title=tr("cleanmkv.wizard.default_audio_filter", default="Default Audio Filter"),
        items=[
            SelectionItem(
                value=None,
                label=tr("common.none", default="None"),
                description=tr("cleanmkv.wizard.no_default_track", default="no default track"),
                group=tr("common.default", default="Default"),
            ),
            *[
                SelectionItem(
                    value=value,
                    label=language_filter_display_label(value),
                    description=language_filter_short_label(value),
                    group=tr("common.default", default="Default"),
                )
                for value in default_audio_candidates
            ],
        ],
        page_size=12,
    )

    keep_subtitle_filters = _select_many_values(
        title=tr("cleanmkv.wizard.subtitle_filters", default="Subtitle Filters"),
        items=_language_entries(
            group=tr("cleanmkv.wizard.languages_variants", default="Languages / Variants")
        ),
        page_size=12,
        allow_empty=True,
    )

    keep_subtitle_variants = _select_many_values(
        title=tr("cleanmkv.wizard.subtitle_variants", default="Subtitle Variants"),
        items=_variant_entries(
            ("forced", "full"),
            group=tr("cleanmkv.wizard.variants", default="Variants"),
        ),
        page_size=6,
        allow_empty=True,
    )

    if keep_subtitle_filters:
        default_subtitle_filter = _select_one_value(
            title=tr("cleanmkv.wizard.default_subtitle_filter", default="Default Subtitle Filter"),
            items=[
                SelectionItem(
                    value=None,
                    label=tr("common.none", default="None"),
                    description=tr(
                        "cleanmkv.wizard.no_default_subtitle", default="no default subtitle"
                    ),
                    group=tr("common.default", default="Default"),
                ),
                *[
                    SelectionItem(
                        value=value,
                        label=language_filter_display_label(value),
                        description=language_filter_short_label(value),
                        group=tr("common.default", default="Default"),
                    )
                    for value in keep_subtitle_filters
                ],
            ],
            page_size=12,
        )
    else:
        default_subtitle_filter = None

    if default_subtitle_filter and keep_subtitle_variants:
        default_subtitle_variant = _select_one_value(
            title=tr(
                "cleanmkv.wizard.default_subtitle_variant", default="Default Subtitle Variant"
            ),
            items=[
                SelectionItem(
                    value=None,
                    label=tr("common.none", default="None"),
                    description=tr(
                        "cleanmkv.wizard.no_default_subtitle", default="no default subtitle"
                    ),
                    group=tr("common.default", default="Default"),
                ),
                *[
                    SelectionItem(
                        value=value,
                        label=_variant_display_label(value),
                        description=tr(
                            "cleanmkv.subtitle_variant_hint", default="subtitle variant"
                        ),
                        group=tr("common.default", default="Default"),
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
        # Wizard prompts always include a "None" entry for the default
        # subtitle track when subtitles are kept; treat a missing default
        # as an explicit user decision instead of letting the planner
        # fall back to the source file's is_default flag.
        audio_default_explicit=True,
        subtitle_default_explicit=bool(keep_subtitle_filters),
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


def _track_display_groups(
    scans: list[MkvFileScan], *, kind: str
) -> dict[str, tuple[list[str], list[TrackInfo], set[str]]]:
    """Group tracks for display purposes.

    Returns a dict mapping display_group_key -> (track_refs, tracks, paths)
    where tracks with the same language/role but different codecs are grouped together.
    """
    # First, get all individual track references
    track_counts = _track_entry_counts(scans, kind=kind)

    # Group by display key (language+role, not codec)
    display_groups: dict[str, tuple[list[str], list[TrackInfo], set[str]]] = {}

    for ref, (track, paths) in track_counts.items():
        display_key = track_display_grouping_key(track)

        if display_key not in display_groups:
            display_groups[display_key] = ([], [], set())

        display_groups[display_key][0].append(ref)  # track_refs
        display_groups[display_key][1].append(track)  # tracks
        display_groups[display_key][2].update(paths)  # paths

    return display_groups


def _track_entries(
    scans: list[MkvFileScan],
    *,
    kind: str,
    enabled_values: tuple[str, ...] = (),
    select_all: bool = False,
) -> list[SelectionItem[str]]:
    total = len(scans)
    entries: list[SelectionItem[str]] = []

    # Get display groups (tracks grouped by language+role)
    display_groups = _track_display_groups(scans, kind=kind)

    for _display_key, (track_refs, tracks, paths) in sorted(
        display_groups.items(),
        key=lambda item: (track_grouped_label(item[1][1]).lower(), item[0]),
    ):
        # For display: use grouped label showing all codecs
        # For multi-grouped tracks (multiple codecs), include file count
        label = track_grouped_label(
            tracks,
            available_count=len(paths),
            total_count=total,
        )

        # For selection value: use comma-separated refs if multiple tracks in group
        # This allows selecting all tracks in the group at once
        value = ",".join(track_refs)

        # Use first track for hint
        hint = track_reference_hint(tracks[0], available_count=len(paths), total_count=total)

        entries.append(
            SelectionItem(
                value=value,
                label=label,
                description=hint,
                preselected=bool(select_all),
            )
        )
    return entries


def _default_refs(scans: list[MkvFileScan], *, kind: str) -> tuple[str, ...]:  # pyright: ignore[reportUnusedFunction]  # Utility helper kept for downstream wizards
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


def _first_existing_ref(candidates: tuple[str, ...], allowed: tuple[str, ...]) -> str | None:  # pyright: ignore[reportUnusedFunction]  # Utility helper kept for downstream wizards
    allowed_set = set(allowed)
    for ref in candidates:
        if ref in allowed_set:
            return ref
    return allowed[0] if allowed else None


def _expand_grouped_refs(grouped_refs: tuple[str, ...]) -> tuple[str, ...]:
    """Expand comma-separated track references from grouped selections.

    When tracks are grouped for display (e.g., "ref1,ref2,ref3"), this function
    expands them back to individual references for the preset.
    """
    expanded = []
    for ref in grouped_refs:
        if "," in ref:
            # This is a grouped reference, expand it
            expanded.extend(ref.split(","))
        else:
            # Single reference
            expanded.append(ref)
    return tuple(expanded)


def run_cleanmkv_track_selector(scans: list[MkvFileScan]) -> CleanPreset:
    """Run cleanmkv track selector."""
    audio_defaults = _all_refs(scans, kind="audio")
    subtitle_defaults = _all_refs(scans, kind="subtitle")

    # Pre-check every detected audio/subtitle track so the user only has to
    # un-tick the ones to drop — typically faster than ticking each one in.
    keep_audio_refs = _select_many_values(
        title=tr("cleanmkv.selector.audio_tracks", default="Audio Tracks Found"),
        items=[
            SelectionItem(
                value=entry.value,
                label=entry.label,
                description=entry.description,
                preselected=entry.preselected,
                group=tr("cleanmkv.selector.current_audio", default="Current audio tracks"),
            )
            for entry in _track_entries(
                scans, kind="audio", enabled_values=audio_defaults, select_all=True
            )
        ],
        page_size=12,
        allow_empty=False,
    )

    default_audio_ref = _select_one_value(
        title=tr("cleanmkv.selector.default_audio", default="Default Audio Track"),
        items=[
            SelectionItem(
                value=None,
                label=tr("common.none", default="None"),
                description=tr("cleanmkv.wizard.no_default_track", default="no default track"),
                preselected=False,
                group=tr("common.default", default="Default"),
            ),
            *[
                SelectionItem(
                    value=option.value,
                    label=option.label,
                    description=option.description,
                    preselected=False,
                    group=tr("common.default", default="Default"),
                )
                for option in _track_entries(scans, kind="audio")
                if option.value in keep_audio_refs
            ],
        ],
        page_size=12,
    )

    keep_subtitle_refs = _select_many_values(
        title=tr("cleanmkv.selector.subtitle_tracks", default="Subtitle Tracks Found"),
        items=[
            SelectionItem(
                value=entry.value,
                label=entry.label,
                description=entry.description,
                preselected=entry.preselected,
                group=tr("cleanmkv.selector.current_subtitles", default="Current subtitle tracks"),
            )
            for entry in _track_entries(
                scans, kind="subtitle", enabled_values=subtitle_defaults, select_all=True
            )
        ],
        page_size=12,
        allow_empty=True,
    )

    if keep_subtitle_refs:
        default_subtitle_ref = _select_one_value(
            title=tr("cleanmkv.selector.default_subtitle", default="Default Subtitle Track"),
            items=[
                SelectionItem(
                    value=None,
                    label=tr("common.none", default="None"),
                    description=tr(
                        "cleanmkv.wizard.no_default_subtitle", default="no default subtitle"
                    ),
                    preselected=False,
                    group=tr("common.default", default="Default"),
                ),
                *[
                    SelectionItem(
                        value=option.value,
                        label=option.label,
                        description=option.description,
                        preselected=False,
                        group=tr("common.default", default="Default"),
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
        keep_audio_track_refs=_expand_grouped_refs(keep_audio_refs),
        default_audio_track_ref=default_audio_ref,
        keep_subtitle_track_refs=_expand_grouped_refs(keep_subtitle_refs),
        default_subtitle_track_ref=default_subtitle_ref,
        # The track selector always exposes a "None" choice for both audio
        # and subtitle defaults, so a missing reference here is always an
        # explicit user decision — never an "I don't care".
        audio_default_explicit=True,
        subtitle_default_explicit=True,
    )
