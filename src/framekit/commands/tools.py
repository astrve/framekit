"""Miscellaneous utility commands (fk tools ...)."""

from __future__ import annotations

from pathlib import Path

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.settings import SettingsStore
from framekit.modules.renamer.service import RenamerService
from framekit.ui.branding import print_module_banner
from framekit.ui.click_helper import click
from framekit.ui.console import print_error, print_info, print_success, print_warning


@click.group("tools", context_settings={"help_option_names": ["-h", "--help"]})
def tools_group() -> None:
    """Miscellaneous release utilities."""


def _rename_folder(folder: Path, new_name: str, *, apply: bool) -> bool:
    if folder.name == new_name:
        print_info(
            tr(
                "renamer.parent.already_correct",
                default="Parent folder already named correctly: {name}",
                name=new_name,
            )
        )
        return False

    new_path = folder.parent / new_name
    if new_path.exists():
        print_warning(
            tr(
                "renamer.parent.target_exists",
                default="Cannot rename parent: target already exists: {path}",
                path=new_path,
            )
        )
        return False

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
    else:
        print_info(
            tr(
                "renamer.parent.would_rename",
                default="Parent folder would be renamed: {old} → {new}",
                old=folder.name,
                new=new_name,
            )
        )
    return True


def _derive_name_from_renamer(folder: Path, default_lang: str) -> str | None:
    service = RenamerService()
    report = service.run(folder, default_lang=default_lang, apply_changes=False, force_lang=False)
    for detail in report.details:
        if detail.status in ("renamed", "planned", "case-only", "planned-case-only"):
            target_name = detail.after.get("name", "")
            if target_name:
                return Path(target_name).stem
    return None


@click.command("rename-parent", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("folder", type=click.Path(path_type=Path), required=False)
@click.option(
    "--name",
    "-n",
    default=None,
    help=tr(
        "cli.tools.rename_parent.name",
        default="New folder name (auto-derived from file names when omitted)",
    ),
)
@click.option(
    "--apply",
    is_flag=True,
    help=tr("cli.tools.rename_parent.apply", default="Apply the rename (default: preview only)"),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help=tr("cli.tools.rename_parent.dry_run", default="Preview without applying changes"),
)
def rename_parent_command(
    folder: Path | None,
    name: str | None,
    apply: bool,
    dry_run: bool,
) -> None:
    """Rename a release folder to match its contents.

    When NAME is not given, the new name is derived automatically from the
    release files inside FOLDER (same logic as the renamer --rename-parent flag).

    Examples:
        fk tools rename-parent /path/to/Release.2024
        fk tools rename-parent --name "Movie.2024.2160p.BluRay.REMUX" --apply
        fk tools rename-parent /path/to/Release --apply
    """
    print_module_banner("Rename Parent")

    if apply and dry_run:
        print_error(
            tr(
                "renamer.error.apply_and_dry_run",
                default="Cannot use --apply and --dry-run together.",
            )
        )
        raise SystemExit(1)

    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    target_folder = resolver.resolve_start_folder("renamer", str(folder) if folder else None)
    if not target_folder.exists() or not target_folder.is_dir():
        print_error(
            tr(
                "cleanmkv.error.folder_not_found",
                default="Folder not found: {folder}",
                folder=target_folder,
            )
        )
        raise SystemExit(1)

    new_name = name
    if not new_name:
        # Auto-derive from renamer rules
        default_lang = str(
            (settings.get("modules") or {}).get("renamer", {}).get("default_language_tag")
            or "MULTI"
        )
        new_name = _derive_name_from_renamer(target_folder, default_lang)
        if not new_name:
            print_warning(
                tr(
                    "tools.rename_parent.no_files",
                    default="Could not derive a folder name — no recognizable release files found in {folder}",
                    folder=target_folder,
                )
            )
            raise SystemExit(1)

    do_apply = apply and not dry_run
    _rename_folder(target_folder, new_name, apply=do_apply)
