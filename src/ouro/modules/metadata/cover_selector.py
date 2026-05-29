from __future__ import annotations

import webbrowser

from ouro.core.i18n import tr
from ouro.ui.console import print_success
from ouro.ui.unified_selector import SelectorOption
from ouro.ui.unified_selector import select_one as _select_one


def _open_poster_url(poster: dict[str, str]) -> None:
    """Open the poster URL in the default browser."""
    url = poster.get("url_original") or poster.get("url")
    if url:
        webbrowser.open(url)
        print_success(
            tr("metadata.cover.opened_url", default="Opened poster in browser: {url}", url=url)
        )


def choose_cover(posters: list[dict[str, str]]) -> dict[str, str] | None:
    """Present a UI for selecting a cover image from available posters.

    Args:
        posters: List of poster dictionaries with 'url', 'url_original', 'size', 'language' keys

    Returns:
        Selected poster dictionary or None if cancelled
    """
    if not posters:
        return None

    entries: list[SelectorOption[dict[str, str]]] = []

    for idx, poster in enumerate(posters, start=1):
        language = poster.get("language", "en")
        size = poster.get("size", "unknown")

        # Mark the first poster as selected by default
        is_first = idx == 1

        # Use intelligent name if available, otherwise fallback to numbered label
        label = poster.get("name") or tr(
            "metadata.cover.poster_label", default="Poster #{num}", num=idx
        )

        hint = f"{language.upper()} · {size}"

        entries.append(
            SelectorOption(
                value=poster,
                label=label,
                hint=hint,
                selected=is_first,
            )
        )

    try:
        return select_one(
            title=tr("metadata.cover.selector_title", default="Cover Selection"),
            entries=entries,
            page_size=8,
            on_open_current=_open_poster_url,
        )
    except KeyboardInterrupt:
        return None


select_one = _select_one  # backwards-compatible patch target for tests
