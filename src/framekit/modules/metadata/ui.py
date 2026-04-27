from __future__ import annotations

import webbrowser

from rich import box
from rich.table import Table

from framekit.core.i18n import tr
from framekit.ui.console import console, print_info, print_success, print_warning


def print_lookup_summary(request) -> None:
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


def choose_candidate(candidates):
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

        if raw.lower().startswith("o"):
            index_raw = raw[1:].strip()
            if not index_raw.isdigit():
                print_warning(
                    tr("metadata.choose.open_example", default="Use o<number>, for example: o2")
                )
                continue

            index = int(index_raw)
            if index < 1 or index > len(candidates):
                print_warning(
                    tr(
                        "metadata.choose.index_out_of_range",
                        default="Candidate index out of range.",
                    )
                )
                continue

            candidate = candidates[index - 1]
            if not candidate.external_url:
                print_warning(
                    tr(
                        "metadata.choose.no_browser_url",
                        default="This candidate does not expose a browser URL yet.",
                    )
                )
                continue

            webbrowser.open(candidate.external_url)
            print_success(
                tr("metadata.choose.opened", default="Opened: {url}", url=candidate.external_url)
            )
            continue

        if raw.isdigit():
            index = int(raw)
            if index < 1 or index > len(candidates):
                print_warning(
                    tr(
                        "metadata.choose.index_out_of_range",
                        default="Candidate index out of range.",
                    )
                )
                continue
            return candidates[index - 1]

        print_warning(
            tr(
                "metadata.choose.unknown_input",
                default="Unknown input. Press Enter, use a number, o<number>, or q.",
            )
        )
