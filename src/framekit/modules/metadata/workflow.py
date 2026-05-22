from __future__ import annotations

from dataclasses import dataclass, field

from framekit.core.i18n import tr
from framekit.core.models.metadata import MetadataCandidate
from framekit.modules.metadata.config import resolve_metadata_config
from framekit.modules.metadata.cover_selector import choose_cover
from framekit.modules.metadata.factory import (
    build_metadata_provider,
    build_provider_chain_for_content,
)
from framekit.modules.metadata.render import build_metadata_context
from framekit.modules.metadata.selector import choose_metadata_candidate
from framekit.modules.metadata.service import MetadataService
from framekit.modules.metadata.ui import (
    print_candidates,
    print_cover_selection_summary,
    print_lookup_summary,
    prompt_manual_tmdb_id,
)
from framekit.ui.console import print_warning
from framekit.ui.unified_selector import confirm_choice


def _episode_code_from_release(release) -> str:
    if not release.episodes:
        return ""
    return (release.episodes[0].episode_code or "").strip().upper()


def _release_title_hint(release) -> str:
    """Build a robust title hint for provider routing.

    Some call sites may pass release-like objects that don't expose the legacy
    ``title`` attribute. This helper keeps the routing path tolerant by
    deriving a best-effort value from newer fields.
    """
    title_attr = getattr(release, "title", None)
    if title_attr:
        return str(title_attr)

    return str(
        getattr(release, "title_display", None)
        or getattr(release, "series_title", None)
        or getattr(release, "release_title", "")
        or ""
    )


def _detect_content_type(release) -> str | None:
    """Detect content type from release for provider chain routing."""
    title = _release_title_hint(release).lower()
    groups_hint = (getattr(release, "release_group", "") or "").lower()

    anime_indicators = {"anime", "sub", "dual audio", "horriblesubs", "erai", "subsplease"}
    if any(ind in title or ind in groups_hint for ind in anime_indicators):
        return "anime"

    if release.media_kind == "movie":
        return "movie"
    if release.media_kind in ("single_episode", "season_pack"):
        return "tv"

    return None


def _is_special_release(release) -> bool:
    if release.media_kind == "single_episode":
        return _episode_code_from_release(release).startswith("S00E")

    if release.media_kind == "season_pack":
        codes = [
            (episode.episode_code or "").strip().upper()
            for episode in release.episodes
            if episode.episode_code
        ]
        return bool(codes) and all(code.startswith("S00E") for code in codes)

    return False


@dataclass(slots=True)
class MetadataWorkflowResult:
    """Result of metadata workflow."""

    status: str
    message: str | None = None

    config: object | None = None
    request: object | None = None
    candidates: list = field(default_factory=list)
    chosen: object | None = None
    resolved: object | None = None
    context: dict = field(default_factory=dict)
    selected_cover: dict[str, str] | None = None


def _workflow_missing_credentials(config: object) -> MetadataWorkflowResult:
    return MetadataWorkflowResult(
        status="missing_credentials",
        message=tr(
            "metadata.workflow.missing_credentials", default="Metadata credentials are missing."
        ),
        config=config,
    )


def _workflow_no_providers(config: object) -> MetadataWorkflowResult:
    return MetadataWorkflowResult(
        status="missing_credentials",
        message=tr("metadata.workflow.no_providers", default="No metadata providers available."),
        config=config,
    )


def _build_service_and_candidates(release, settings: dict, config):
    fallback_providers = settings.get("metadata", {}).get("fallback_providers", [])
    content_type_hints = settings.get("metadata", {}).get("content_type_hints", {})

    if fallback_providers or content_type_hints:
        content_type = _detect_content_type(release)
        chain = build_provider_chain_for_content(settings, content_type=content_type, config=config)
        provider = chain.primary_provider
        if provider is None:
            return None, None, None, []
        service = MetadataService(provider, cache_ttl_hours=config.cache_ttl_hours)
        request = service.build_lookup_request(release)
        candidates = chain.search_candidates(request)
        return provider, service, request, candidates

    provider = build_metadata_provider(settings, config=config)
    service = MetadataService(provider, cache_ttl_hours=config.cache_ttl_hours)
    request, candidates = service.search(release)
    return provider, service, request, candidates


def _maybe_manual_tmdb_candidate(
    *,
    provider,
    request,
    candidates: list[MetadataCandidate],
    config,
    auto_accept: bool,
    show_ui: bool,
) -> list[MetadataCandidate]:
    if candidates or not config.interactive_confirmation or auto_accept or not show_ui:
        return candidates

    print_warning(
        tr(
            "metadata.workflow.no_candidates_found",
            default="No metadata candidates found automatically.",
        )
    )
    should_provide_id = confirm_choice(
        title=tr(
            "metadata.workflow.provide_manual_id",
            default="Would you like to provide a TMDB ID manually?",
        ),
        default=False,
    )
    if not should_provide_id:
        return candidates

    manual_id = prompt_manual_tmdb_id()
    if not manual_id:
        return candidates

    manual_candidate = provider.search_by_id(manual_id, request.media_kind)
    if manual_candidate is None:
        print_warning(
            tr(
                "metadata.workflow.manual_id_not_found",
                default="Could not fetch metadata for the provided TMDB ID.",
            )
        )
        return candidates

    if request.season_number:
        manual_candidate = MetadataCandidate(
            provider_name=manual_candidate.provider_name,
            provider_id=manual_candidate.provider_id,
            kind=manual_candidate.kind,
            title=manual_candidate.title,
            year=manual_candidate.year,
            season_number=request.season_number,
            episode_number=request.episode_number,
            imdb_id=manual_candidate.imdb_id,
            external_url=manual_candidate.external_url,
            overview=manual_candidate.overview,
            confidence=manual_candidate.confidence,
            reasons=manual_candidate.reasons,
        )
    return [manual_candidate]


def _select_candidate(
    *,
    candidates: list[MetadataCandidate],
    config,
    auto_accept: bool,
    chooser,
):
    if not config.interactive_confirmation or auto_accept:
        return candidates[0]
    return chooser(candidates)


def _cover_from_resolved(resolved) -> dict[str, str] | None:
    if hasattr(resolved, "poster_url") and resolved.poster_url:
        return {
            "url": resolved.poster_url,
            "url_original": resolved.poster_url,
            "size": "default",
            "language": "en",
        }
    return None


def _resolve_cover_selection(
    *,
    provider,
    chosen,
    resolved,
    interactive: bool,
) -> dict[str, str] | None:
    try:
        posters = provider.fetch_posters(chosen)
    except Exception:  # nosec B110
        return _cover_from_resolved(resolved)

    if posters:
        if interactive:
            print_cover_selection_summary(len(posters))
            selected_cover = choose_cover(posters)
            return selected_cover if selected_cover is not None else posters[0]
        return posters[0]
    return _cover_from_resolved(resolved)


def run_metadata_workflow(
    release,
    settings: dict,
    *,
    auto_accept: bool = False,
    show_ui: bool = True,
    chooser=choose_metadata_candidate,
    env: dict[str, str] | None = None,
    language_override: str | None = None,
) -> MetadataWorkflowResult:
    """Run metadata workflow."""
    config = resolve_metadata_config(settings, env=env, language_override=language_override)

    if _is_special_release(release):
        return MetadataWorkflowResult(
            status="unsupported_specials",
            message=tr(
                "metadata.workflow.unsupported_specials",
                default="Special season detected (S00). Episode metadata is not supported yet.",
            ),
            config=config,
        )

    if not config.has_credentials:
        return _workflow_missing_credentials(config)

    provider_service_request = _build_service_and_candidates(release, settings, config)
    if provider_service_request[0] is None:
        return _workflow_no_providers(config)
    provider, service, request, candidates = provider_service_request

    if show_ui:
        print_lookup_summary(request)

    candidates = _maybe_manual_tmdb_candidate(
        provider=provider,
        request=request,
        candidates=candidates,
        config=config,
        auto_accept=auto_accept,
        show_ui=show_ui,
    )
    if not candidates:
        return MetadataWorkflowResult(
            status="no_candidates",
            message=tr("metadata.workflow.no_candidates", default="No metadata candidates found."),
            config=config,
            request=request,
            candidates=[],
        )

    if show_ui:
        print_candidates(candidates)

    chosen = _select_candidate(
        candidates=candidates,
        config=config,
        auto_accept=auto_accept,
        chooser=chooser,
    )
    if chosen is None:
        return MetadataWorkflowResult(
            status="cancelled",
            message=tr("metadata.workflow.cancelled", default="Metadata selection cancelled."),
            config=config,
            request=request,
            candidates=candidates,
        )

    service.store_choice(release, chosen)
    resolved = service.resolve_candidate(chosen)

    selected_cover = _resolve_cover_selection(
        provider=provider,
        chosen=chosen,
        resolved=resolved,
        interactive=bool(config.interactive_confirmation and not auto_accept and show_ui),
    )

    context = build_metadata_context(resolved, release, selected_cover=selected_cover)

    return MetadataWorkflowResult(
        status="resolved",
        config=config,
        request=request,
        candidates=candidates,
        chosen=chosen,
        resolved=resolved,
        context=context,
        selected_cover=selected_cover,
    )
