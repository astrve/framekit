from __future__ import annotations

# ruff: noqa: I001
from pathlib import Path

from loguru import logger

from framekit.core.i18n import tr
from framekit.core.languages import match_language_filter
from framekit.core.models.cleanmkv import CleanPreset, MkvFileScan, RemuxPlan, TrackInfo
from framekit.modules.cleanmkv.tracks import ad_codec_score, track_reference_key

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
    """Return the builtin preset."""
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
    if not preset.keep_audio_filters:
        return list(scan.audio_tracks)

    return [
        track
        for track in scan.audio_tracks
        if _track_matches_any_filter(track, preset.keep_audio_filters)
    ]


def _filter_subtitle_tracks(scan: MkvFileScan, preset: CleanPreset) -> list[TrackInfo]:
    if preset.keep_subtitle_track_refs:
        wanted = set(preset.keep_subtitle_track_refs)
        filtered = [track for track in scan.subtitle_tracks if track_reference_key(track) in wanted]
    elif preset.keep_subtitle_filters:
        filtered = [
            track
            for track in scan.subtitle_tracks
            if _track_matches_any_filter(track, preset.keep_subtitle_filters)
        ]
    else:
        filtered = list(scan.subtitle_tracks)

    if not preset.keep_subtitle_variants:
        return filtered

    return [track for track in filtered if track.subtitle_variant in preset.keep_subtitle_variants]


def _dedupe_ad_audio_tracks(tracks: list[TrackInfo]) -> list[TrackInfo]:
    """Keep the best AD track for each matching language and channel group.

    Non-AD audio tracks pass through unchanged.
    """
    ad_groups: dict[tuple, list[TrackInfo]] = {}
    for track in tracks:
        if track.subtitle_variant == "ad":
            key = (track.language, track.language_variant, track.channels_count)
            ad_groups.setdefault(key, []).append(track)

    if not ad_groups:
        return tracks

    best_ad_ids: set[int] = set()
    for group in ad_groups.values():
        best = max(group, key=lambda t: (ad_codec_score(t.codec), t.bitrate or 0))
        best_ad_ids.add(best.track_id)

    return [t for t in tracks if t.subtitle_variant != "ad" or t.track_id in best_ad_ids]


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

    track_id = _default_track_id_by_ref(tracks, preset.default_audio_track_ref)
    if track_id is not None:
        return track_id

    track_id = _default_audio_track_id_by_filter(tracks, preset.default_audio_filter)
    if track_id is not None:
        return track_id

    # When the user has gone through an interactive flow (wizard or track
    # selector) and explicitly picked no default, do not fall back to the
    # source file's is_default flag. This avoids "ghost" defaults appearing
    # silently in the remuxed output.
    if preset.audio_default_explicit:
        return None

    for track in tracks:
        if track.is_default:
            return track.track_id

    return tracks[0].track_id


def _pick_default_subtitle_track(
    tracks: list[TrackInfo],
    preset: CleanPreset,
    audio_tracks: list[TrackInfo],
) -> int | None:
    if not tracks:
        return None

    track_id = _default_track_id_by_ref(tracks, preset.default_subtitle_track_ref)
    if track_id is not None:
        return track_id

    special_policy_applied, track_id = _pick_same_language_subtitle_default(
        subtitle_tracks=tracks,
        audio_tracks=audio_tracks,
        preset=preset,
    )
    if special_policy_applied:
        return track_id

    track_id = _default_subtitle_track_id_by_filter(
        tracks,
        preset.default_subtitle_filter,
        preset.default_subtitle_variant,
    )
    if track_id is not None:
        return track_id

    # When the user has explicitly picked "no default subtitle" through the
    # wizard or the interactive track selector, respect that choice instead
    # of silently re-using the source file's is_default flag — which used to
    # cause a random subtitle track to be marked default on some files.
    if preset.subtitle_default_explicit:
        return None

    for track in tracks:
        if track.is_default:
            return track.track_id

    return None


def _pick_same_language_subtitle_default(
    *,
    subtitle_tracks: list[TrackInfo],
    audio_tracks: list[TrackInfo],
    preset: CleanPreset,
) -> tuple[bool, int | None]:
    target_filter = preset.default_subtitle_filter
    if not _uses_same_language_subtitle_policy(preset) or target_filter is None:
        return False, None

    forced_track_id = _default_subtitle_track_id_by_filter(
        subtitle_tracks,
        target_filter,
        "forced",
    )
    if forced_track_id is not None:
        return True, forced_track_id

    if _has_audio_track_for_filter(audio_tracks, target_filter):
        return True, None

    vost_track_id, vost_variant = _pick_vost_subtitle_fallback(subtitle_tracks, target_filter)
    if vost_track_id is None:
        logger.warning(
            tr(
                "cleanmkv.warn.same_language_audio_and_sub_missing",
                default=(
                    "Preset {preset} did not find any audio or subtitle track matching "
                    "{language}; no default subtitle will be selected"
                ),
                preset=preset.name,
                language=target_filter,
            )
        )
        return True, None

    logger.warning(
        tr(
            "cleanmkv.warn.same_language_audio_missing_using_vost",
            default=(
                "Preset {preset} did not find {language} audio; using {variant} "
                "{language} subtitle as default (VOST)"
            ),
            preset=preset.name,
            language=target_filter,
            variant=vost_variant or "matching",
        )
    )
    return True, vost_track_id


def _uses_same_language_subtitle_policy(preset: CleanPreset) -> bool:
    if (
        not preset.default_audio_filter
        or not preset.default_subtitle_filter
        or preset.default_subtitle_variant is not None
    ):
        return False
    return (
        preset.default_audio_filter.strip().lower()
        == preset.default_subtitle_filter.strip().lower()
    )


def _has_audio_track_for_filter(tracks: list[TrackInfo], language_filter: str) -> bool:
    return any(
        match_language_filter(track.language, track.language_variant, language_filter)
        for track in tracks
    )


def _pick_vost_subtitle_fallback(
    tracks: list[TrackInfo],
    language_filter: str,
) -> tuple[int | None, str | None]:
    for variant in ("full", "sdh", "forced"):
        track_id = _default_subtitle_track_id_by_filter(tracks, language_filter, variant)
        if track_id is not None:
            return track_id, variant

    track_id = _default_subtitle_track_id_by_filter(tracks, language_filter, None)
    if track_id is None:
        return None, None

    matched_track = next((track for track in tracks if track.track_id == track_id), None)
    return track_id, matched_track.subtitle_variant if matched_track is not None else None


def _default_track_id_by_ref(tracks: list[TrackInfo], track_ref: str | None) -> int | None:
    if not track_ref:
        return None
    for track in tracks:
        if track_reference_key(track) == track_ref:
            return track.track_id
    return None


def _default_audio_track_id_by_filter(
    tracks: list[TrackInfo],
    language_filter: str | None,
) -> int | None:
    if not language_filter:
        return None
    for track in tracks:
        if match_language_filter(track.language, track.language_variant, language_filter):
            return track.track_id
    return None


def _default_subtitle_track_id_by_filter(
    tracks: list[TrackInfo],
    language_filter: str | None,
    subtitle_variant: str | None,
) -> int | None:
    if not language_filter:
        return None
    for track in tracks:
        if not match_language_filter(track.language, track.language_variant, language_filter):
            continue
        if subtitle_variant and track.subtitle_variant != subtitle_variant:
            continue
        return track.track_id
    return None


def build_remux_plan(
    scan: MkvFileScan,
    *,
    preset: CleanPreset,
    output_dir_name: str,
    release_name: str | None = None,
) -> RemuxPlan:
    """Build remux plan."""
    _validate_non_empty_preset(preset)

    kept_audio = _dedupe_tracks(_dedupe_ad_audio_tracks(_filter_audio_tracks(scan, preset)))
    kept_subs = _dedupe_tracks(_filter_subtitle_tracks(scan, preset))

    has_audio_filters = bool(preset.keep_audio_filters or preset.keep_audio_track_refs)
    if has_audio_filters and not kept_audio:
        reason = tr(
            "cleanmkv.warn.no_matching_audio",
            default="No audio tracks match preset filters — skipping {file}",
            file=scan.path.name,
        )
        logger.warning(reason)
        target = _resolve_remux_target(
            scan, output_dir_name=output_dir_name, release_name=release_name
        )
        return RemuxPlan(
            source=scan.path,
            target=target,
            keep_audio_track_ids=[],
            keep_subtitle_track_ids=[],
            default_audio_track_id=None,
            default_subtitle_track_id=None,
            copy_only=True,
            skipped=True,
            skip_reason=reason,
        )

    keep_audio_ids = [track.track_id for track in kept_audio]
    keep_sub_ids = [track.track_id for track in kept_subs]

    default_audio_id = _pick_default_audio_track(kept_audio, preset)
    default_sub_id = _pick_default_subtitle_track(kept_subs, preset, kept_audio)

    target = _resolve_remux_target(scan, output_dir_name=output_dir_name, release_name=release_name)
    copy_only = _is_copy_only_plan(
        scan=scan,
        keep_audio_ids=keep_audio_ids,
        keep_sub_ids=keep_sub_ids,
        default_audio_id=default_audio_id,
        default_sub_id=default_sub_id,
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


def _validate_non_empty_preset(preset: CleanPreset) -> None:
    # External/project presets use empty filters to mean "keep all tracks".
    # Validation stays as a compatibility hook, but must not reject that shape.
    return None


def _resolve_remux_target(
    scan: MkvFileScan,
    *,
    output_dir_name: str,
    release_name: str | None,
) -> Path:
    resolved_output_dir_name = sanitized_release_dir(
        output_dir_name, release_name or scan.path.stem
    )
    return scan.path.parent / resolved_output_dir_name / scan.path.name


def _is_copy_only_plan(
    *,
    scan: MkvFileScan,
    keep_audio_ids: list[int],
    keep_sub_ids: list[int],
    default_audio_id: int | None,
    default_sub_id: int | None,
) -> bool:
    original_audio_ids = [track.track_id for track in scan.audio_tracks]
    original_sub_ids = [track.track_id for track in scan.subtitle_tracks]
    original_default_audio_ids = {track.track_id for track in scan.audio_tracks if track.is_default}
    original_default_sub_ids = {
        track.track_id for track in scan.subtitle_tracks if track.is_default
    }
    desired_default_audio_ids = {default_audio_id} if default_audio_id is not None else set()
    desired_default_sub_ids = {default_sub_id} if default_sub_id is not None else set()
    checks = [
        keep_audio_ids == original_audio_ids,
        keep_sub_ids == original_sub_ids,
        desired_default_audio_ids == original_default_audio_ids,
        desired_default_sub_ids == original_default_sub_ids,
    ]
    return all(checks)
