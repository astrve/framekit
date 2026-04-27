from __future__ import annotations

# ruff: noqa: I001

from framekit.core.i18n import tr
from framekit.core.languages import match_language_filter
from framekit.core.models.cleanmkv import CleanPreset, MkvFileScan, RemuxPlan, TrackInfo
from framekit.modules.cleanmkv.tracks import track_reference_key

from framekit.core.naming import sanitized_release_dir

BUILTIN_PRESETS: dict[str, CleanPreset] = {
    "anime": CleanPreset(
        name="anime",
        keep_audio_filters=("french", "japanese", "english"),
        default_audio_filter="french",
        keep_subtitle_filters=("french", "english"),
        keep_subtitle_variants=("forced", "full", "sdh"),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
    ),
    "vostfr": CleanPreset(
        name="vostfr",
        keep_audio_filters=("japanese",),
        default_audio_filter="japanese",
        keep_subtitle_filters=("french",),
        keep_subtitle_variants=("forced", "full", "sdh"),
        default_subtitle_filter="french",
        default_subtitle_variant="full",
    ),
    "multi": CleanPreset(
        name="multi",
        keep_audio_filters=("french", "english", "japanese", "spanish"),
        default_audio_filter="french",
        keep_subtitle_filters=("french", "english", "spanish"),
        keep_subtitle_variants=("forced", "full", "sdh"),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
    ),
    "vf": CleanPreset(
        name="vf",
        keep_audio_filters=("french",),
        default_audio_filter="french",
        keep_subtitle_filters=("french",),
        keep_subtitle_variants=("forced", "full"),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
    ),
    "vo": CleanPreset(
        name="vo",
        keep_audio_filters=("english", "japanese"),
        default_audio_filter=None,
        keep_subtitle_filters=("english", "french"),
        keep_subtitle_variants=("forced", "full", "sdh"),
        default_subtitle_filter=None,
        default_subtitle_variant=None,
    ),
}


def get_builtin_preset(name: str) -> CleanPreset:
    key = name.strip().lower()
    if key not in BUILTIN_PRESETS:
        available = ", ".join(sorted(BUILTIN_PRESETS))
        raise ValueError(
            tr(
                "cleanmkv.error.unknown_preset",
                default="Unknown preset: {name}. Available presets: {available}",
                name=name,
                available=available,
            )
        )
    return BUILTIN_PRESETS[key]


def _track_matches_any_filter(track: TrackInfo, filters: tuple[str, ...]) -> bool:
    return any(
        match_language_filter(track.language, track.language_variant, filter_value)
        for filter_value in filters
    )


def _filter_audio_tracks(scan: MkvFileScan, preset: CleanPreset) -> list[TrackInfo]:
    if preset.keep_audio_track_refs:
        wanted = set(preset.keep_audio_track_refs)
        return [track for track in scan.audio_tracks if track_reference_key(track) in wanted]

    return [
        track
        for track in scan.audio_tracks
        if _track_matches_any_filter(track, preset.keep_audio_filters)
    ]


def _filter_subtitle_tracks(scan: MkvFileScan, preset: CleanPreset) -> list[TrackInfo]:
    if preset.keep_subtitle_track_refs:
        wanted = set(preset.keep_subtitle_track_refs)
        return [track for track in scan.subtitle_tracks if track_reference_key(track) in wanted]

    return [
        track
        for track in scan.subtitle_tracks
        if _track_matches_any_filter(track, preset.keep_subtitle_filters)
        and track.subtitle_variant in preset.keep_subtitle_variants
    ]


def _dedupe_tracks(tracks: list[TrackInfo]) -> list[TrackInfo]:
    seen: set[str] = set()
    result: list[TrackInfo] = []

    for track in tracks:
        key = track_reference_key(track)
        if key in seen:
            continue
        seen.add(key)
        result.append(track)

    return result


def _pick_default_audio_track(tracks: list[TrackInfo], preset: CleanPreset) -> int | None:
    if not tracks:
        return None

    if preset.default_audio_track_ref:
        for track in tracks:
            if track_reference_key(track) == preset.default_audio_track_ref:
                return track.track_id

    if preset.default_audio_filter:
        for track in tracks:
            if match_language_filter(
                track.language, track.language_variant, preset.default_audio_filter
            ):
                return track.track_id

    for track in tracks:
        if track.is_default:
            return track.track_id

    return tracks[0].track_id


def _pick_default_subtitle_track(tracks: list[TrackInfo], preset: CleanPreset) -> int | None:
    if not tracks:
        return None

    if preset.default_subtitle_track_ref:
        for track in tracks:
            if track_reference_key(track) == preset.default_subtitle_track_ref:
                return track.track_id

    if preset.default_subtitle_filter:
        for track in tracks:
            if not match_language_filter(
                track.language, track.language_variant, preset.default_subtitle_filter
            ):
                continue

            if (
                preset.default_subtitle_variant
                and track.subtitle_variant != preset.default_subtitle_variant
            ):
                continue

            return track.track_id

    for track in tracks:
        if track.is_default:
            return track.track_id

    return None


def build_remux_plan(
    scan: MkvFileScan,
    *,
    preset: CleanPreset,
    output_dir_name: str,
    release_name: str | None = None,
) -> RemuxPlan:
    has_audio_selection = bool(preset.keep_audio_filters or preset.keep_audio_track_refs)
    has_subtitle_selection = bool(preset.keep_subtitle_filters or preset.keep_subtitle_track_refs)

    if not has_audio_selection and not has_subtitle_selection:
        raise ValueError(
            tr(
                "cleanmkv.error.empty_preset",
                default="Preset would keep no audio and no subtitles.",
            )
        )

    kept_audio = _dedupe_tracks(_filter_audio_tracks(scan, preset))
    kept_subs = _dedupe_tracks(_filter_subtitle_tracks(scan, preset))

    keep_audio_ids = [track.track_id for track in kept_audio]
    keep_sub_ids = [track.track_id for track in kept_subs]

    default_audio_id = _pick_default_audio_track(kept_audio, preset)
    default_sub_id = _pick_default_subtitle_track(kept_subs, preset)

    # Resolve the output directory using the central release naming helper to ensure the
    # folder name is sanitized. The template may contain a {release} placeholder which is
    # replaced by the sanitized release name. When release_name is not provided, use the
    # file stem of the scanned MKV.
    resolved_output_dir_name = sanitized_release_dir(
        output_dir_name, release_name or scan.path.stem
    )
    target = scan.path.parent / resolved_output_dir_name / scan.path.name

    original_audio_ids = [track.track_id for track in scan.audio_tracks]
    original_sub_ids = [track.track_id for track in scan.subtitle_tracks]

    original_default_audio_ids = {track.track_id for track in scan.audio_tracks if track.is_default}
    original_default_sub_ids = {
        track.track_id for track in scan.subtitle_tracks if track.is_default
    }

    desired_default_audio_ids = {default_audio_id} if default_audio_id is not None else set()
    desired_default_sub_ids = {default_sub_id} if default_sub_id is not None else set()

    copy_only = (
        keep_audio_ids == original_audio_ids
        and keep_sub_ids == original_sub_ids
        and desired_default_audio_ids == original_default_audio_ids
        and desired_default_sub_ids == original_default_sub_ids
    )

    return RemuxPlan(
        source=scan.path,
        target=target,
        keep_audio_track_ids=keep_audio_ids,
        keep_subtitle_track_ids=keep_sub_ids,
        default_audio_track_id=default_audio_id,
        default_subtitle_track_id=default_sub_id,
        copy_only=copy_only,
    )
