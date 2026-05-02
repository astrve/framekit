from __future__ import annotations

import sys

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from pathlib import Path

from rich import box
from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.settings import SettingsStore
from framekit.modules.renamer.service import RenamerService
from framekit.modules.renamer.term_selector import (
    TermInventory,
    collect_terms,
    derive_remove_terms,
)
from framekit.ui.branding import print_module_banner
from framekit.ui.console import console, print_error, print_info, print_success, print_warning
from framekit.ui.selector import (
    SelectorDivider,
    SelectorEntry,
    SelectorOption,
    confirm_choice,
    select_many,
)


def _join_path_parts(parts: tuple[str, ...]) -> str:
    return " ".join(part for part in parts if part).strip()


def _status_style(status: str) -> str:
    mapping = {
        "renamed": "green",
        "planned": "white",
        "unchanged": "yellow",
        "collision": "red",
        "case-only": "cyan",
        "planned-case-only": "cyan",
    }
    return mapping.get(status, "white")


def _status_label(status: str) -> str:
    key = status.replace("-", "_")
    return tr(f"operation.status.{key}", default=status)


def _rename_example(report) -> str:
    for detail in report.details:
        source_name = str(detail.before.get("name", "") or "")
        target_name = str(detail.after.get("name", "") or "")
        if source_name and target_name and source_name != target_name:
            return f"{source_name} → {target_name}"
    for detail in report.details:
        source_name = str(detail.before.get("name", "") or "")
        target_name = str(detail.after.get("name", "") or "")
        if source_name and target_name:
            return f"{source_name} → {target_name}"
    return "-"


def _print_rename_preview(report, *, details: bool = False, applied: bool = False) -> None:
    summary = Table(
        title=tr("renamer.preview_summary", default="Renamer Preview Summary"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    summary.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
    summary.add_column(tr("common.value", default="Value"), ratio=1)
    changed = sum(
        1
        for detail in report.details
        if detail.status in {"renamed", "planned", "case-only", "planned-case-only"}
    )
    unchanged = sum(1 for detail in report.details if detail.status == "unchanged")
    collisions = sum(1 for detail in report.details if detail.status == "collision")
    summary.add_row(tr("common.scanned", default="Scanned"), str(report.scanned))
    summary.add_row(tr("common.processed", default="Processed"), str(report.processed))
    summary.add_row(
        tr("common.modified", default="Modified")
        if applied
        else tr("common.planned_changes", default="Planned changes"),
        str(changed),
    )
    summary.add_row(tr("common.unchanged", default="Unchanged"), str(unchanged))
    summary.add_row(tr("common.errors", default="Errors"), str(collisions + len(report.errors)))
    summary.add_row(tr("common.example", default="Example"), _rename_example(report))
    console.print(summary)

    if not details:
        return

    console.print()
    for index, detail in enumerate(report.details, start=1):
        status_color = _status_style(detail.status)
        table = Table(
            title=tr("common.item_number", default="Item {index}", index=index),
            expand=True,
            box=box.HEAVY,
            border_style="white",
        )
        table.add_column(tr("common.field", default="Field"), width=22, no_wrap=True)
        table.add_column(tr("common.value", default="Value"), ratio=1, overflow="fold")
        table.add_row(tr("common.source", default="Source"), str(detail.before.get("name", "-")))
        table.add_row(tr("common.target", default="Target"), str(detail.after.get("name", "-")))
        table.add_row(
            tr("common.status", default="Status"),
            f"[{status_color}]{_status_label(detail.status)}[/{status_color}]",
        )
        table.add_row(tr("common.message", default="Message"), detail.message or "-")
        console.print(table)


def _category_label(category: str) -> str:
    return tr(
        f"renamer.term_selector.category.{category}",
        default={
            "episode_code": "Episode codes",
            "year": "Year",
            "language": "Language",
            "resolution": "Resolution",
            "source": "Source",
            "video_codec": "Video codec",
            "audio_codec": "Audio codec",
            "hdr": "HDR",
            "team": "Team",
            "other": "Other",
        }.get(category, category.replace("_", " ").title()),
    )


def _print_term_inventory_summary(inventory: TermInventory, folder: Path) -> None:
    """Render the read-only summary of the detected terms before the picker."""
    table = Table(
        title=tr("renamer.term_selector.summary_title", default="Detected Terms"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.category", default="Category"), width=18, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=2, overflow="fold")
    table.add_column(tr("common.count", default="Count"), width=8, no_wrap=True)
    table.add_column(tr("common.status", default="Status"), width=10, no_wrap=True)

    if inventory.episode_codes.count:
        table.add_row(
            _category_label("episode_code"),
            inventory.episode_codes.label,
            str(inventory.episode_codes.count),
            f"[cyan]{tr('renamer.term_selector.locked', default='locked')}[/cyan]",
        )

    for entry in inventory.entries:
        status = (
            f"[cyan]{tr('renamer.term_selector.locked', default='locked')}[/cyan]"
            if entry.locked
            else f"[green]{tr('renamer.term_selector.selectable', default='selectable')}[/green]"
        )
        table.add_row(_category_label(entry.category), entry.value, str(entry.count), status)

    console.print(table)
    print_info(
        tr(
            "renamer.term_selector.scanned_files",
            default="Scanned {count} file(s)",
            count=len(inventory.files),
        )
    )


def _build_term_selector_entries(inventory: TermInventory) -> list[SelectorEntry]:
    """
    Build the entries for the interactive term selector. Locked entries are
    rendered as `disabled` SelectorOption rows so the user can see them but
    cannot toggle them off.
    """
    entries: list[SelectorEntry] = []

    locked_label = tr("renamer.term_selector.locked", default="locked")

    # Episode codes — always locked, single grouped row.
    if inventory.episode_codes.count:
        entries.append(SelectorDivider(_category_label("episode_code")))
        entries.append(
            SelectorOption(
                value=f"__locked__:episode_code:{inventory.episode_codes.label}",
                label=f"{inventory.episode_codes.label} (×{inventory.episode_codes.count})",
                hint=locked_label,
                selected=True,
                disabled=True,
                disabled_reason=locked_label,
            )
        )

    # Group remaining entries by category, dividers between categories.
    last_category: str | None = None
    for entry in inventory.entries:
        if entry.category != last_category:
            entries.append(SelectorDivider(_category_label(entry.category)))
            last_category = entry.category

        if entry.locked:
            entries.append(
                SelectorOption(
                    value=f"__locked__:{entry.category}:{entry.value}",
                    label=f"{entry.value} (×{entry.count})",
                    hint=locked_label,
                    selected=True,
                    disabled=True,
                    disabled_reason=locked_label,
                )
            )
        else:
            entries.append(
                SelectorOption(
                    value=entry.value,
                    label=f"{entry.value} (×{entry.count})",
                    hint=tr(
                        "renamer.term_selector.option_hint",
                        default="Untick to remove this term from file names",
                    ),
                    selected=entry.selected_by_default,
                )
            )

    return entries


def _run_term_selector(folder: Path) -> tuple[str, ...] | None:
    """
    Open the interactive term picker for `folder` and return the resulting
    `remove_terms` tuple. Returns `None` if the user cancelled or if there
    are no selectable terms (no point asking).

    `RuntimeError` raised by the underlying selector in headless mode is
    caught and surfaced as a regular warning so the caller can fall back to
    the explicit `--remove-term` flag without crashing.
    """
    inventory = collect_terms(folder)
    if inventory.is_empty() and inventory.episode_codes.count == 0:
        print_warning(
            tr(
                "renamer.term_selector.no_terms",
                default="No terms detected in this folder.",
            )
        )
        return ()

    _print_term_inventory_summary(inventory, folder)

    selectable = inventory.selectable()
    if not selectable:
        print_info(
            tr(
                "renamer.term_selector.nothing_selectable",
                default="Nothing to pick — all detected terms are locked.",
            )
        )
        return ()

    entries = _build_term_selector_entries(inventory)

    try:
        kept_values = select_many(
            title=tr("renamer.term_selector.title", default="Choose terms to keep"),
            entries=entries,
            page_size=12,
            minimal_count=0,
        )
    except KeyboardInterrupt:
        return None
    except RuntimeError as exc:
        print_warning(str(exc))
        return ()

    # Filter out locked sentinel values; only string values from selectable
    # entries should reach `derive_remove_terms`.
    kept = {
        str(value)
        for value in kept_values
        if isinstance(value, str) and not value.startswith("__locked__:")
    }
    return derive_remove_terms(inventory, kept)


def run_renamer_command(
    *,
    path: str | None,
    lang: str | None,
    apply_changes: bool,
    dry_run: bool,
    force_lang: bool,
    show_details: bool = False,
    remove_terms: tuple[str, ...] = (),
    select_terms: bool | None = None,
) -> int:
    if apply_changes and dry_run:
        print_error(
            tr(
                "common.error.apply_and_dry_run",
                default="--apply and --dry-run cannot be used together.",
            )
        )
        return 1

    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    print_module_banner("Renamer")

    folder = resolver.resolve_start_folder("renamer", path or None)
    if not folder.exists() or not folder.is_dir():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return 1

    service = RenamerService()
    default_lang = lang or settings["modules"]["renamer"]["default_language_tag"]

    if lang and not force_lang:
        print_warning(
            tr(
                "renamer.warning.lang_not_forced",
                default="Language tag will only be injected if missing. Use --force-lang to replace existing tags.",
            )
        )

    # Resolve whether to open the interactive term picker. Explicit flag wins;
    # otherwise we offer the picker only when we are *interactive* AND the
    # caller did not already supply explicit `--remove-term` values nor a
    # non-interactive mode (`--apply` / `--dry-run`).
    if select_terms is True:
        run_picker = True
    elif select_terms is False:
        run_picker = False
    else:
        run_picker = (
            bool(sys.stdin.isatty()) and not remove_terms and not apply_changes and not dry_run
        )

    effective_remove_terms = tuple(remove_terms)
    if run_picker:
        picker_result = _run_term_selector(folder)
        if picker_result is None:
            print_warning(
                tr(
                    "renamer.term_selector.cancelled",
                    default="Term selection cancelled.",
                )
            )
            return 1
        # Picker output is *additive* to any explicit `--remove-term` values.
        # Deduplicate while keeping the order: CLI terms first, then picker.
        seen: set[str] = set()
        merged: list[str] = []
        for term in (*remove_terms, *picker_result):
            key = term.upper()
            if key in seen:
                continue
            seen.add(key)
            merged.append(term)
        effective_remove_terms = tuple(merged)
        if effective_remove_terms:
            print_info(
                tr(
                    "renamer.term_selector.removing",
                    default="Removing terms: {terms}",
                    terms=", ".join(effective_remove_terms),
                )
            )

    interactive_confirmation = not apply_changes and not dry_run
    report = service.run(
        folder,
        default_lang=default_lang,
        apply_changes=apply_changes,
        force_lang=force_lang,
        remove_terms=effective_remove_terms,
    )

    _print_rename_preview(report, details=show_details, applied=apply_changes)

    print_info(tr("common.folder", default="Folder") + f": {folder}")
    print_info(tr("nfo.info.scanned", default="Scanned: {count}", count=report.scanned))
    print_info(tr("nfo.info.processed", default="Processed: {count}", count=report.processed))
    if apply_changes:
        print_info(tr("common.modified", default="Modified") + f": {report.modified}")
    else:
        print_info(tr("common.planned_changes", default="Planned changes") + f": {report.modified}")
    print_info(tr("common.skipped", default="Skipped") + f": {report.skipped}")

    if report.errors:
        for error in report.errors:
            print_error(error.message)
        return 1

    if interactive_confirmation:
        should_apply = confirm_choice(
            title=tr("renamer.confirm.apply_changes", default="Apply this rename plan now?"),
            default=True,
            yes_label=tr("common.apply", default="Apply"),
            no_label=tr("common.cancel", default="Cancel"),
        )
        if should_apply is None or not should_apply:
            print_success(
                tr(
                    "renamer.success.preview_no_apply",
                    default="Renamer preview completed without applying changes.",
                )
            )
            settings["modules"]["renamer"]["last_folder"] = str(folder)
            store.save(settings)
            return 0

        report = service.run(
            folder,
            default_lang=default_lang,
            apply_changes=True,
            force_lang=force_lang,
            remove_terms=effective_remove_terms,
        )
        _print_rename_preview(report, details=show_details, applied=True)

        if report.errors:
            for error in report.errors:
                print_error(error.message)
            return 1

        print_success(tr("renamer.success.completed", default="Rename operation completed."))
    elif apply_changes:
        print_success(tr("renamer.success.completed", default="Rename operation completed."))
    else:
        print_success(tr("common.dry_run_completed", default="Dry-run completed."))

    settings["modules"]["renamer"]["last_folder"] = str(folder)
    store.save(settings)

    return 0


@click.command(
    "renamer", help=tr("cli.renamer.help", default="Rename media files using Framekit rules.")
)
@click.argument("path_parts", nargs=-1)
@click.option(
    "-l", "--lang", help=tr("cli.renamer.option.lang", default="Language tag to inject or replace.")
)
@click.option(
    "-a",
    "--apply",
    "apply_changes",
    is_flag=True,
    help=tr("cli.renamer.option.apply", default="Apply changes instead of dry-run."),
)
@click.option(
    "-f",
    "--force-lang",
    is_flag=True,
    help=tr(
        "cli.renamer.option.force_lang",
        default="Replace existing language tag instead of only filling missing ones.",
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help=tr(
        "cli.renamer.option.dry_run",
        default="Preview only. Do not ask to apply changes.",
    ),
)
@click.option(
    "--details",
    "show_details",
    is_flag=True,
    help=tr("cli.renamer.option.details", default="Show per-file rename details."),
)
@click.option(
    "--remove-term",
    "remove_terms",
    multiple=True,
    help=tr(
        "cli.renamer.option.remove_term",
        default="Remove a term from source names before normalization.",
    ),
)
@click.option(
    "--select-terms/--no-select-terms",
    "select_terms",
    default=None,
    help=tr(
        "cli.renamer.option.select_terms",
        default="Open or bypass the interactive 'terms to keep' picker before previewing.",
    ),
)
def renamer_command(
    path_parts: tuple[str, ...],
    lang: str | None,
    apply_changes: bool,
    dry_run: bool,
    force_lang: bool,
    show_details: bool,
    remove_terms: tuple[str, ...],
    select_terms: bool | None,
) -> int:
    return run_renamer_command(
        path=_join_path_parts(path_parts) or None,
        lang=lang,
        apply_changes=apply_changes,
        dry_run=dry_run,
        force_lang=force_lang,
        show_details=show_details,
        remove_terms=remove_terms,
        select_terms=select_terms,
    )
