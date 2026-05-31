from __future__ import annotations

import webbrowser

from rich import box
from rich.table import Table

from swirrl.core.i18n import tr
from swirrl.ui.console import console, print_info, print_success, print_warning


def print_lookup_summary(request) -> None:
    """Handle print lookup summary."""
    table = Table(
        title=tr("metadata.lookup_title", default="Metadata Lookup"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=18, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)

    table.add_row(tr("common.media_kind", default="Media Kind"), request.media_kind or "-")
    table.add_row(tr("common.title", default="Title"), request.title or "-")
    table.add_row(tr("common.year", default="Year"), request.year or "-")
    table.add_row(tr("metadata.season", default="Season"), str(request.season_number or "-"))
    table.add_row(tr("metadata.episode", default="Episode"), str(request.episode_number or "-"))
    table.add_row(tr("common.release_title", default="Release Title"), request.release_title or "-")

    console.print(table)


def print_candidates(candidates) -> None:
    """Handle print candidates."""
    table = Table(
        title=tr("metadata.candidates_title", default="Metadata Candidates"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column("#", width=4, no_wrap=True)
    table.add_column(tr("common.title", default="Title"), ratio=2)
    table.add_column(tr("common.year", default="Year"), width=8, no_wrap=True)
    table.add_column(tr("metadata.kind", default="Kind"), width=16, no_wrap=True)
    table.add_column(tr("metadata.confidence", default="Confidence"), width=12, no_wrap=True)
    table.add_column(tr("metadata.reasons", default="Reasons"), ratio=2)

    for index, candidate in enumerate(candidates, start=1):
        reasons = ", ".join(candidate.reasons) if candidate.reasons else "-"
        table.add_row(
            str(index),
            candidate.title or "-",
            candidate.year or "-",
            candidate.kind or "-",
            f"{candidate.confidence:.2f}",
            reasons,
        )

    console.print(table)


def _parse_candidate_index(raw: str, count: int) -> int | None:
    if not raw.isdigit():
        return None
    index = int(raw)
    if index < 1 or index > count:
        return None
    return index - 1


def _open_candidate_command(raw: str) -> str | None:
    if not raw.lower().startswith("o"):
        return None
    return raw[1:].strip()


def _warn_index_range() -> None:
    print_warning(
        tr(
            "metadata.choose.index_out_of_range",
            default="Candidate index out of range.",
        )
    )


def _handle_open_candidate(raw: str, candidates) -> bool:
    index_raw = _open_candidate_command(raw)
    if index_raw is None:
        return False
    if not index_raw.isdigit():
        print_warning(tr("metadata.choose.open_example", default="Use o<number>, for example: o2"))
        return True

    index = _parse_candidate_index(index_raw, len(candidates))
    if index is None:
        _warn_index_range()
        return True

    candidate = candidates[index]
    if not candidate.external_url:
        print_warning(
            tr(
                "metadata.choose.no_browser_url",
                default="This candidate does not expose a browser URL yet.",
            )
        )
        return True

    webbrowser.open(candidate.external_url)
    print_success(tr("metadata.choose.opened", default="Opened: {url}", url=candidate.external_url))
    return True


def choose_candidate(candidates):
    """Handle choose candidate."""
    if not candidates:
        return None

    print_info(tr("metadata.choose.accept_best", default="Press Enter to accept the best match."))
    print_info(
        tr("metadata.choose.type_number", default="Type a number to select another candidate.")
    )
    print_info(
        tr(
            "metadata.choose.open_candidate",
            default="Type o<number> to open a candidate page in your browser.",
        )
    )
    print_info(tr("metadata.choose.cancel", default="Type q to cancel."))

    while True:
        raw = console.input("[white]> [/white]").strip()

        if raw == "":
            return candidates[0]

        if raw.lower() == "q":
            return None

        if _handle_open_candidate(raw, candidates):
            continue

        index = _parse_candidate_index(raw, len(candidates))
        if index is not None:
            return candidates[index]
        if raw.isdigit():
            _warn_index_range()
            continue

        print_warning(
            tr(
                "metadata.choose.unknown_input",
                default="Unknown input. Press Enter, use a number, o<number>, or q.",
            )
        )


def print_cover_selection_summary(poster_count: int) -> None:
    """Print a summary of available cover images."""
    print_info(
        tr(
            "metadata.cover.available_count",
            default="Found {count} available poster images.",
            count=poster_count,
        )
    )


def prompt_manual_tmdb_id() -> str | None:
    """Prompt the user to manually enter a TMDB ID or URL.

    Returns:
        TMDB ID as string, or None if cancelled
    """
    print_info(
        tr(
            "metadata.manual_id.prompt",
            default="Enter TMDB ID or URL (e.g., '12345' or 'https://www.themoviedb.org/movie/12345'):",
        )
    )

    while True:
        raw = console.input("[white]> [/white]").strip()

        if not raw or raw.lower() == "q":
            return None

        # Try to extract ID from URL
        import re

        # Match movie URL: https://www.themoviedb.org/movie/12345
        movie_match = re.search(r"themoviedb\.org/movie/(\d+)", raw)
        if movie_match:
            return movie_match.group(1)

        # Match TV show URL: https://www.themoviedb.org/tv/12345
        tv_match = re.search(r"themoviedb\.org/tv/(\d+)", raw)
        if tv_match:
            return tv_match.group(1)

        # Check if it's just a numeric ID
        if raw.isdigit():
            return raw

        print_warning(
            tr(
                "metadata.manual_id.invalid",
                default="Invalid input. Please enter a numeric TMDB ID or a valid TMDB URL.",
            )
        )
