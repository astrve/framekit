from __future__ import annotations

import webbrowser

from framekit.core.i18n import tr
from framekit.core.models.metadata import MetadataCandidate
from framekit.ui.selector import SelectorOption, select_one


def _open_candidate(candidate: MetadataCandidate) -> None:
    if candidate.external_url:
        webbrowser.open(candidate.external_url)


class MetadataCandidateSelector:
    def __init__(self, candidates: list[MetadataCandidate], page_size: int = 8) -> None:
        self.candidates = candidates
        self.page_size = page_size

    def run(self) -> MetadataCandidate | None:
        if not self.candidates:
            return None

        entries: list[SelectorOption[MetadataCandidate]] = []

        for candidate in self.candidates:
            is_saved = "stored choice" in (candidate.reasons or [])
            state = tr("metadata.candidate.saved", default="saved") if is_saved else ""
            reasons = ", ".join(candidate.reasons) if candidate.reasons else "-"
            hint = f"{candidate.kind} · {candidate.year or '-'} · {candidate.confidence:.2f}"
            if state:
                hint = f"{hint} · {state}"
            if reasons and reasons != "-":
                hint = f"{hint} · {reasons}"

            entries.append(
                SelectorOption(
                    value=candidate,
                    label=candidate.title or "-",
                    hint=hint,
                    selected=is_saved,
                )
            )

        try:
            return select_one(
                title=tr("metadata.selector.title", default="TMDb Match Selector"),
                entries=entries,
                page_size=self.page_size,
                on_open_current=_open_candidate,
            )
        except KeyboardInterrupt:
            return None


def choose_metadata_candidate(
    candidates: list[MetadataCandidate],
    page_size: int = 8,
) -> MetadataCandidate | None:
    selector = MetadataCandidateSelector(candidates, page_size=page_size)
    return selector.run()
