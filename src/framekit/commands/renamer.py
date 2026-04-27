from __future__ import annotations

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
try:
    import rich_click as click  # type: ignore[import-not-found]
except Exception:
    import click  # type: ignore[import-not-found]
from rich import box
from rich.table import Table

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.settings import SettingsStore
from framekit.modules.renamer.service import RenamerService
from framekit.ui.branding import print_module_banner
from framekit.ui.console import console, print_error, print_info, print_success, print_warning
from framekit.ui.selector import confirm_choice


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


def run_renamer_command(
    *,
    path: str | None,
    lang: str | None,
    apply_changes: bool,
    dry_run: bool,
    force_lang: bool,
    show_details: bool = False,
    remove_terms: tuple[str, ...] = (),
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

    interactive_confirmation = not apply_changes and not dry_run
    report = service.run(
        folder,
        default_lang=default_lang,
        apply_changes=apply_changes,
        force_lang=force_lang,
        remove_terms=tuple(remove_terms),
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
            remove_terms=tuple(remove_terms),
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
def renamer_command(
    path_parts: tuple[str, ...],
    lang: str | None,
    apply_changes: bool,
    dry_run: bool,
    force_lang: bool,
    show_details: bool,
    remove_terms: tuple[str, ...],
) -> int:
    return run_renamer_command(
        path=_join_path_parts(path_parts) or None,
        lang=lang,
        apply_changes=apply_changes,
        dry_run=dry_run,
        force_lang=force_lang,
        show_details=show_details,
        remove_terms=remove_terms,
    )
