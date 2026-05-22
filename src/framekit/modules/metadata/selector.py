from __future__ import annotations

import webbrowser

from framekit.core.i18n import tr
from framekit.core.models.metadata import MetadataCandidate
from framekit.ui.unified_selector import SelectorOption
from framekit.ui.unified_selector import select_one as _select_one


def _open_candidate(candidate: MetadataCandidate) -> None:
    if candidate.external_url:
        webbrowser.open(candidate.external_url)


class MetadataCandidateSelector:
    """Interactive selector for metadata candidate."""

    def __init__(self, candidates: list[MetadataCandidate], page_size: int = 8) -> None:
        self.candidates = candidates
        self.page_size = page_size

    def _build_hint(self, candidate: MetadataCandidate, *, is_saved: bool) -> str:
        reasons = ", ".join(candidate.reasons) if candidate.reasons else "-"
        state = tr("metadata.candidate.saved", default="saved") if is_saved else ""
        hint = f"{candidate.kind} · {candidate.year or '-'} · {candidate.confidence:.2f}"
        if state:
            hint = f"{hint} · {state}"
        if reasons != "-":
            hint = f"{hint} · {reasons}"
        return hint

    def _build_entries(self) -> list[SelectorOption[MetadataCandidate]]:
        entries: list[SelectorOption[MetadataCandidate]] = []
        for candidate in self.candidates:
            is_saved = "stored choice" in (candidate.reasons or [])
            entries.append(
                SelectorOption(
                    value=candidate,
                    label=candidate.title or "-",
                    hint=self._build_hint(candidate, is_saved=is_saved),
                    selected=is_saved,
                )
            )
        return entries

    def run(self) -> MetadataCandidate | None:
        """Handle run."""
        if not self.candidates:
            return None

        entries = self._build_entries()

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
    """Handle choose metadata candidate."""
    selector = MetadataCandidateSelector(candidates, page_size=page_size)
    return selector.run()


select_one = _select_one  # backwards-compatible patch target for tests
