from __future__ import annotations

from dataclasses import dataclass, field

from framekit.core.i18n import tr
from framekit.modules.metadata.config import resolve_metadata_config
from framekit.modules.metadata.factory import build_metadata_provider
from framekit.modules.metadata.render import build_metadata_context
from framekit.modules.metadata.selector import choose_metadata_candidate
from framekit.modules.metadata.service import MetadataService
from framekit.modules.metadata.ui import print_candidates, print_lookup_summary


def _episode_code_from_release(release) -> str:
    if not release.episodes:
        return ""
    return (release.episodes[0].episode_code or "").strip().upper()


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
    status: str
    message: str | None = None

    config: object | None = None
    request: object | None = None
    candidates: list = field(default_factory=list)
    chosen: object | None = None
    resolved: object | None = None
    context: dict = field(default_factory=dict)


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
        return MetadataWorkflowResult(
            status="missing_credentials",
            message=tr(
                "metadata.workflow.missing_credentials", default="Metadata credentials are missing."
            ),
            config=config,
        )

    provider = build_metadata_provider(settings, config=config)
    service = MetadataService(
        provider,
        cache_ttl_hours=config.cache_ttl_hours,
    )

    request, candidates = service.search(release)
    if show_ui:
        print_lookup_summary(request)

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

    chosen = candidates[0]
    if config.interactive_confirmation and not auto_accept:
        chosen = chooser(candidates)
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
    context = build_metadata_context(resolved, release)

    return MetadataWorkflowResult(
        status="resolved",
        config=config,
        request=request,
        candidates=candidates,
        chosen=chosen,
        resolved=resolved,
        context=context,
    )
