from __future__ import annotations

import sys
from pathlib import Path

from rich import box
from rich.table import Table

from ouro.core.cli_helpers import join_path_parts
from ouro.core.i18n import tr
from ouro.core.paths import PathResolver
from ouro.core.settings import SettingsStore
from ouro.modules.renamer.profiles import (
    LanguageTagProfile,
    RenamerProfile,
    list_renamer_profiles,
    load_renamer_profile,
    resolve_language_tag_profile,
)
from ouro.modules.renamer.service import RenamerService
from ouro.modules.renamer.term_selector import (
    TermInventory,
    collect_terms,
    derive_remove_terms,
)
from ouro.ui.branding import print_module_banner

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from ouro.ui.click_helper import click
from ouro.ui.console import console, print_error, print_info, print_success, print_warning
from ouro.ui.unified_selector import (
    SelectorDivider,
    SelectorEntry,
    SelectorOption,
    confirm_choice,
)
from ouro.ui.unified_selector import (
    select_many as _select_many,
)


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
    changed = _first_rename_example(report, changed_only=True)
    if changed:
        return changed
    any_example = _first_rename_example(report, changed_only=False)
    return any_example or "-"


def _first_rename_example(report, *, changed_only: bool) -> str | None:
    for detail in report.details:
        source_name = str(detail.before.get("name", "") or "")
        target_name = str(detail.after.get("name", "") or "")
        if not source_name or not target_name:
            continue
        if changed_only and source_name == target_name:
            continue
        return f"{source_name} → {target_name}"
    return None


def _rename_counts(report) -> tuple[int, int, int]:
    changed = sum(
        1
        for detail in report.details
        if detail.status in {"renamed", "planned", "case-only", "planned-case-only"}
    )
    unchanged = sum(1 for detail in report.details if detail.status == "unchanged")
    collisions = sum(1 for detail in report.details if detail.status == "collision")
    return changed, unchanged, collisions


def _preview_summary_table(report, *, applied: bool) -> Table:
    summary = Table(
        title=tr("renamer.preview_summary", default="Renamer Preview Summary"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    summary.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
    summary.add_column(tr("common.value", default="Value"), ratio=1)
    changed, unchanged, collisions = _rename_counts(report)
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
    return summary


def _print_rename_detail_table(detail, *, index: int) -> None:
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


def _print_rename_preview(report, *, details: bool = False, applied: bool = False) -> None:
    console.print(_preview_summary_table(report, applied=applied))

    if not details:
        return

    console.print()
    for index, detail in enumerate(report.details, start=1):
        _print_rename_detail_table(detail, index=index)


def _resolve_renamer_context(
    path: str | None, lang: str | None, profile_name: str | None
) -> tuple[Path, RenamerService, str, RenamerProfile, LanguageTagProfile] | None:
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    folder = resolver.resolve_start_folder("renamer", path or None)
    if not folder.exists() or not folder.is_dir():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=folder,
            )
        )
        return None
    service = RenamerService()
    resolved_profile_name = profile_name or str(settings["modules"]["renamer"].get("profile", "fr_tracker"))
    profile = load_renamer_profile(resolved_profile_name)
    language_profile = resolve_language_tag_profile(settings, profile_name=resolved_profile_name)
    default_lang = _default_language(settings, lang, profile, language_profile)
    return folder, service, default_lang, profile, language_profile


def _run_renamer_preview_then_confirm(
    *,
    interactive_confirmation: bool,
    service: RenamerService,
    folder: Path,
    default_lang: str,
    force_lang: bool,
    remove_terms: tuple[str, ...],
    insert_after_pairs: tuple[tuple[str, str], ...],
    show_details: bool,
    apply_changes: bool,
    profile: RenamerProfile,
    language_profile: LanguageTagProfile,
    interactive_conflict_resolution: bool,
) -> int | None:
    first_error, _first_report = _run_renamer_once(
        service=service,
        folder=folder,
        default_lang=default_lang,
        apply_changes=apply_changes,
        force_lang=force_lang,
        remove_terms=remove_terms,
        insert_after_pairs=insert_after_pairs,
        show_details=show_details,
        profile=profile,
        language_profile=language_profile,
        interactive_conflict_resolution=interactive_conflict_resolution,
    )
    if first_error is not None:
        return first_error
    if not interactive_confirmation:
        return None

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
        return 0

    second_error, _report = _run_renamer_once(
        service=service,
        folder=folder,
        default_lang=default_lang,
        apply_changes=True,
        force_lang=force_lang,
        remove_terms=remove_terms,
        insert_after_pairs=insert_after_pairs,
        show_details=show_details,
        profile=profile,
        language_profile=language_profile,
        interactive_conflict_resolution=interactive_conflict_resolution,
    )
    return second_error


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
    """Build the entries for the interactive term selector.

    Locked entries are rendered as ``disabled`` SelectorOption rows so the user
    can see them but cannot toggle them off.
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
    """Open the interactive term picker for ``folder``.

    Returns the resulting ``remove_terms`` tuple, or ``None`` if the user
    cancelled or if there are no selectable terms (no point asking).

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


def _validate_renamer_flags(*, apply_changes: bool, dry_run: bool) -> int | None:
    if not (apply_changes and dry_run):
        return None
    print_error(
        tr(
            "common.error.apply_and_dry_run",
            default="--apply and --dry-run cannot be used together.",
        )
    )
    return 1


def _resolve_renamer_folder(path: str | None) -> tuple[PathResolver, Path] | tuple[None, None]:
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)
    folder = resolver.resolve_start_folder("renamer", path or None)
    if folder.exists() and folder.is_dir():
        return resolver, folder
    print_error(
        tr(
            "cleanmkv.error.folder_not_found",
            default="Folder not found: {folder}",
            folder=folder,
        )
    )
    return None, None


def _default_language(
    settings: dict,
    lang: str | None,
    profile: RenamerProfile,
    language_profile: LanguageTagProfile,
) -> str:
    configured = str(settings["modules"]["renamer"].get("default_language_tag", "") or "")
    inferred_default = language_profile.tags.only_default or profile.default_language_tag
    return str(lang or inferred_default or configured or "")


def _should_run_picker(
    *,
    select_terms: bool | None,
    remove_terms: tuple[str, ...],
    apply_changes: bool,
    dry_run: bool,
) -> bool:
    if select_terms is True:
        return True
    if select_terms is False:
        return False
    return bool(sys.stdin.isatty()) and not remove_terms and not apply_changes and not dry_run


def _merge_remove_terms(
    *, cli_terms: tuple[str, ...], picker_terms: tuple[str, ...]
) -> tuple[str, ...]:
    seen: set[str] = set()
    merged: list[str] = []
    for term in (*cli_terms, *picker_terms):
        key = term.upper()
        if key in seen:
            continue
        seen.add(key)
        merged.append(term)
    return tuple(merged)


def _resolve_effective_remove_terms(
    *,
    folder: Path,
    remove_terms: tuple[str, ...],
    select_terms: bool | None,
    apply_changes: bool,
    dry_run: bool,
) -> tuple[int | None, tuple[str, ...]]:
    run_picker = _should_run_picker(
        select_terms=select_terms,
        remove_terms=remove_terms,
        apply_changes=apply_changes,
        dry_run=dry_run,
    )
    if not run_picker:
        return None, tuple(remove_terms)

    picker_result = _run_term_selector(folder)
    if picker_result is None:
        print_warning(
            tr(
                "renamer.term_selector.cancelled",
                default="Term selection cancelled.",
            )
        )
        return 1, ()

    effective_remove_terms = _merge_remove_terms(cli_terms=remove_terms, picker_terms=picker_result)
    if effective_remove_terms:
        print_info(
            tr(
                "renamer.term_selector.removing",
                default="Removing terms: {terms}",
                terms=", ".join(effective_remove_terms),
            )
        )
    return None, effective_remove_terms


def _print_renamer_run_summary(report, *, folder: Path, apply_changes: bool) -> None:
    print_info(tr("common.folder", default="Folder") + f": {folder}")
    print_info(tr("nfo.info.scanned", default="Scanned: {count}", count=report.scanned))
    print_info(tr("nfo.info.processed", default="Processed: {count}", count=report.processed))
    if apply_changes:
        print_info(tr("common.modified", default="Modified") + f": {report.modified}")
    else:
        print_info(tr("common.planned_changes", default="Planned changes") + f": {report.modified}")
    print_info(tr("common.skipped", default="Skipped") + f": {report.skipped}")
    if apply_changes:
        for output in report.outputs:
            if output.startswith("run_id="):
                operation_id = output[len("run_id=") :]
                print_info(
                    tr("common.operation_id", default="Operation ID")
                    + f": [bold]{operation_id}[/bold]"
                    + "  [dim](use [cyan]ouro rollback "
                    + operation_id
                    + "[/cyan] to undo)[/dim]"
                )


def _report_errors_if_any(report) -> int | None:
    if not report.errors:
        return None
    for error in report.errors:
        print_error(error.message)
    return 1


def _resolve_multi_language_tags_interactive(
    plan: list,
    *,
    _service: RenamerService,
) -> list:
    """Prompt for ambiguous single-language tags in interactive mode.

    Returns a possibly mutated plan when multiple audio tracks are detected.
    """
    if not sys.stdin.isatty():
        return plan

    from ouro.modules.renamer.rules import replace_language_tag

    for i, item in enumerate(plan):
        if not item.changed:
            continue
        if not (item.multi_language_detected or item.language_tag_conflict):
            continue

        existing = (item.existing_language_tag or "").upper()
        suggested = (item.calculated_language_tag or item.resulting_language_tag or existing).upper()
        if not suggested:
            suggested = f"MULTI.{existing}" if existing else "MULTI"
        keep = existing or suggested

        console.print(
            f"\n[yellow]WARNING[/yellow]  [bold]{item.source.name}[/bold]: "
            "detected language-tag mismatch between filename and audio tracks."
        )
        choice = (
            click.prompt(
                f"  Language tag [{suggested} / {keep} / Custom]",
                default=suggested,
            )
            .strip()
            .upper()
        )

        if choice == keep:
            chosen_tag = keep
        elif choice == suggested:
            chosen_tag = suggested
        else:
            chosen_tag = choice.upper()  # custom input

        if chosen_tag == keep and keep == existing:
            # Keep current value: no change for this item.
            plan[i].changed = False
            continue

        # Rebuild the target stem with the chosen tag.
        stem_parts = item.target.stem.split(".")
        new_parts = replace_language_tag(stem_parts, chosen_tag)
        new_stem = ".".join(new_parts)
        plan[i].target = item.target.with_name(f"{new_stem}{item.target.suffix}")
        plan[i].resulting_language_tag = chosen_tag
        plan[i].calculated_language_tag = suggested

    return plan


def _run_renamer_once(
    *,
    service: RenamerService,
    folder: Path,
    default_lang: str,
    apply_changes: bool,
    force_lang: bool,
    remove_terms: tuple[str, ...],
    insert_after_pairs: tuple[tuple[str, str], ...],
    show_details: bool,
    profile: RenamerProfile,
    language_profile: LanguageTagProfile,
    interactive_conflict_resolution: bool,
) -> tuple[int | None, object]:
    # When applying in interactive mode, build the plan first so we can prompt
    # the user to resolve ambiguous single-language tags before committing.
    if apply_changes and sys.stdin.isatty() and interactive_conflict_resolution:
        plan = service.build_plan(
            folder,
            default_lang=default_lang,
            force_lang=force_lang,
            remove_terms=remove_terms,
            insert_after_pairs=insert_after_pairs,
            profile=profile,
            language_profile=language_profile,
        )
        plan = _resolve_multi_language_tags_interactive(plan, _service=service)
        report = service.run_plan(plan, apply_changes=apply_changes)
    else:
        report = service.run(
            folder,
            default_lang=default_lang,
            apply_changes=apply_changes,
            force_lang=force_lang,
            remove_terms=remove_terms,
            insert_after_pairs=insert_after_pairs,
            profile=profile,
            language_profile=language_profile,
            strict_conflict_abort=apply_changes and not interactive_conflict_resolution,
        )
    _print_rename_preview(report, details=show_details, applied=apply_changes)
    _print_renamer_run_summary(report, folder=folder, apply_changes=apply_changes)
    error_code = _report_errors_if_any(report)
    return error_code, report


def _derive_parent_name_from_report(report) -> str | None:
    """Derive a new parent folder name from the first renamed file (strip extension)."""
    for detail in report.details:
        if detail.status in ("renamed", "planned", "case-only", "planned-case-only"):
            target_name = detail.after.get("name", "")
            if target_name:
                return Path(target_name).stem
    return None


def _rename_parent_folder(folder: Path, new_name: str, *, apply: bool) -> Path | None:
    """Rename the release folder. Returns new path on success, None on skip."""
    if folder.name == new_name:
        print_info(
            tr(
                "renamer.parent.already_correct",
                default="Parent folder already named correctly: {name}",
                name=new_name,
            )
        )
        return None

    new_path = folder.parent / new_name
    if new_path.exists():
        print_warning(
            tr(
                "renamer.parent.target_exists",
                default="Cannot rename parent: target already exists: {path}",
                path=new_path,
            )
        )
        return None

    if apply:
        folder.rename(new_path)
        print_success(
            tr(
                "renamer.parent.renamed",
                default="Parent folder renamed: {old} → {new}",
                old=folder.name,
                new=new_name,
            )
        )
        return new_path
    else:
        print_info(
            tr(
                "renamer.parent.would_rename",
                default="Parent folder would be renamed: {old} → {new}",
                old=folder.name,
                new=new_name,
            )
        )
        return None


def run_renamer_command(
    *,
    path: str | None,
    lang: str | None,
    apply_changes: bool,
    dry_run: bool,
    force_lang: bool,
    show_details: bool = False,
    remove_terms: tuple[str, ...] = (),
    insert_after_pairs: tuple[tuple[str, str], ...] = (),
    select_terms: bool | None = None,
    rename_parent: bool = False,
    profile_name: str | None = None,
    interactive_conflict_resolution: bool = True,
) -> int:
    """Run renamer command."""
    flags_error = _validate_renamer_flags(apply_changes=apply_changes, dry_run=dry_run)
    if flags_error is not None:
        return flags_error

    print_module_banner("Renamer")
    context = _resolve_renamer_context(path, lang, profile_name)
    if context is None:
        return 1
    folder, service, default_lang, profile, language_profile = context

    if lang and not force_lang:
        print_warning(
            tr(
                "renamer.warning.lang_not_forced",
                default="Language tag will only be injected if missing. Use --force-lang to replace existing tags.",
            )
        )
    picker_error, effective_remove_terms = _resolve_effective_remove_terms(
        folder=folder,
        remove_terms=remove_terms,
        select_terms=select_terms,
        apply_changes=apply_changes,
        dry_run=dry_run,
    )
    if picker_error is not None:
        return picker_error

    interactive_confirmation = bool(sys.stdin.isatty()) and not apply_changes and not dry_run
    run_error = _run_renamer_preview_then_confirm(
        interactive_confirmation=interactive_confirmation,
        service=service,
        folder=folder,
        default_lang=default_lang,
        apply_changes=apply_changes,
        force_lang=force_lang,
        remove_terms=effective_remove_terms,
        insert_after_pairs=insert_after_pairs,
        show_details=show_details,
        profile=profile,
        language_profile=language_profile,
        interactive_conflict_resolution=interactive_conflict_resolution,
    )
    if run_error is not None:
        return run_error

    # Rename parent folder if requested
    if rename_parent:
        preview_report = service.run(
            folder,
            default_lang=default_lang,
            apply_changes=False,
            force_lang=force_lang,
            remove_terms=effective_remove_terms,
            insert_after_pairs=insert_after_pairs,
            profile=profile,
            language_profile=language_profile,
        )
        parent_name = _derive_parent_name_from_report(preview_report)
        if parent_name:
            will_apply = apply_changes or interactive_confirmation
            _rename_parent_folder(folder, parent_name, apply=will_apply and not dry_run)

    if apply_changes or interactive_confirmation:
        print_success(tr("renamer.success.completed", default="Rename operation completed."))
    else:
        print_success(tr("common.dry_run_completed", default="Dry-run completed."))

    return 0


def _print_renamer_profiles() -> None:
    table = Table(title="Renamer profiles", box=box.HEAVY, expand=True)
    table.add_column("Profile", width=18, no_wrap=True)
    table.add_column("Default language", width=18)
    table.add_column("Junk terms", ratio=1)
    for profile in list_renamer_profiles():
        table.add_row(
            profile.name,
            profile.default_language_tag or "-",
            ", ".join(profile.junk_terms) or "-",
        )
    console.print(table)


def _print_renamer_explain(profile_name: str) -> None:
    profile = load_renamer_profile(profile_name)
    table = Table(title=f"Renamer profile: {profile.name}", box=box.HEAVY, expand=True)
    table.add_column("Field", width=24, no_wrap=True)
    table.add_column("Value", ratio=1, overflow="fold")
    table.add_row("default_language_tag", profile.default_language_tag or "-")
    table.add_row(
        "language_aliases",
        ", ".join(f"{k}->{v}" for k, v in profile.language_aliases.items()) or "-",
    )
    table.add_row("junk_terms", ", ".join(profile.junk_terms) or "-")
    table.add_row(
        "quality_aliases",
        ", ".join(f"{k}->{v}" for k, v in profile.quality_aliases.items()) or "-",
    )
    table.add_row("insert_missing_resolution", str(profile.insert_missing_resolution))
    console.print(table)


@click.command(
    "renamer",
    help=tr(
        "cli.renamer.help",
        default=(
            "Normalize release file names using intelligent parsing and formatting rules.\n\n"
            "The renamer analyzes file names, extracts metadata (resolution, codec, language, etc.), "
            "and reformats them according to tracker standards and best practices.\n\n"
            "Quick examples:\n"
            "  ouro renamer <folder>                     # Interactive preview and confirm\n"
            "  ouro ren <folder> --apply                 # Apply without confirmation\n"
            "  ouro renamer <folder> --lang FRENCH       # Inject language tag\n"
            "  ouro ren <folder> --remove-term REPACK    # Remove specific terms\n"
            "  ouro renamer <folder> --select-terms      # Interactive term picker\n\n"
            "Features:\n"
            "  • Intelligent term detection and categorization\n"
            "  • Interactive term selection\n"
            "  • Language tag injection/replacement\n"
            "  • Custom term removal\n"
            "  • Collision detection\n"
            "  • Case-only rename support\n\n"
            "Best practices:\n"
            "  • Always preview changes before applying\n"
            "  • Use --select-terms for fine-grained control\n"
            "  • Use --force-lang to replace existing language tags\n"
            "  • Check for collisions in the preview\n\n"
            "Related commands: pipeline, batch"
        ),
    ),
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
    "-d",
    "--dry-run",
    is_flag=True,
    help=tr(
        "cli.renamer.option.dry_run",
        default="Preview only. Do not ask to apply changes.",
    ),
)
@click.option(
    "-D",
    "--details",
    "show_details",
    is_flag=True,
    help=tr("cli.renamer.option.details", default="Show per-file rename details."),
)
@click.option(
    "-r",
    "--remove-term",
    "remove_terms",
    multiple=True,
    help=tr(
        "cli.renamer.option.remove_term",
        default="Remove a term from source names before normalization.",
    ),
)
@click.option(
    "--insert-after",
    "insert_after_pairs",
    nargs=2,
    multiple=True,
    metavar="<existing_token> <term_to_add>",
    help=tr(
        "cli.renamer.option.insert_after",
        default="Insert a term after an existing token in the filename.",
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
@click.option(
    "-P",
    "--rename-parent",
    is_flag=True,
    help=tr(
        "cli.renamer.option.rename_parent",
        default="Also rename the parent release folder to match the normalized name.",
    ),
)
@click.option(
    "--profile",
    "profile_name",
    help="Renamer profile: fr_tracker, international, no_language, or custom.",
)
@click.pass_context
def renamer_command(
    ctx: click.Context,
    path_parts: tuple[str, ...],
    lang: str | None,
    apply_changes: bool,
    dry_run: bool,
    force_lang: bool,
    show_details: bool,
    remove_terms: tuple[str, ...],
    insert_after_pairs: tuple[tuple[str, str], ...],
    select_terms: bool | None,
    rename_parent: bool,
    profile_name: str | None,
) -> None:
    """Handle renamer command."""
    if path_parts and path_parts[0] == "profiles":
        _print_renamer_profiles()
        return
    if path_parts and path_parts[0] == "explain":
        _print_renamer_explain(profile_name or "fr_tracker")
        return
    ctx.exit(
        run_renamer_command(
            path=join_path_parts(path_parts) or None,
            lang=lang,
            apply_changes=apply_changes,
            dry_run=dry_run,
            force_lang=force_lang,
            show_details=show_details,
            remove_terms=remove_terms,
            insert_after_pairs=insert_after_pairs,
            select_terms=select_terms,
            rename_parent=rename_parent,
            profile_name=profile_name,
        )
    )


select_many = _select_many  # backwards-compatible patch target for tests
