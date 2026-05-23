"""Miscellaneous utility commands (fk tools ...)."""

from __future__ import annotations

from pathlib import Path

from framekit.core.i18n import tr
from framekit.core.paths import PathResolver
from framekit.core.release_payload import (
    VIDEO_EXTENSIONS,
    derive_library_folder_name,
    find_release_payload,
)
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


def _folder_has_direct_release_markers(folder: Path) -> bool:
    try:
        children = list(folder.iterdir())
    except OSError:
        return False
    if any(child.is_file() and child.suffix.lower() in VIDEO_EXTENSIONS for child in children):
        return True
    return any(child.is_dir() and child.name.lower() == "release" for child in children)


def _find_rename_parent_targets(folder: Path) -> list[Path]:
    if _folder_has_direct_release_markers(folder):
        return [folder]

    targets: list[Path] = []
    try:
        children = sorted(folder.iterdir(), key=lambda path: path.name.lower())
    except OSError:
        return []

    for child in children:
        if child.is_dir() and find_release_payload(child) is not None:
            targets.append(child)

    if targets:
        return targets
    return [folder] if find_release_payload(folder) is not None else []


def _derive_name_from_payload(folder: Path) -> str | None:
    payload = find_release_payload(folder)
    if payload is None:
        return None
    return derive_library_folder_name(payload)


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
    "--dry-run",
    is_flag=True,
    help=tr("cli.tools.rename_parent.dry_run", default="Preview without applying changes"),
)
def rename_parent_command(
    folder: Path | None,
    name: str | None,
    dry_run: bool,
) -> None:
    """Rename a release folder to match its contents.

    When NAME is not given, the new name is derived automatically from the
    release files inside FOLDER (same logic as the renamer --rename-parent flag).

    Examples:
        fk tools rename-parent /path/to/Release.2024
        fk tools rename-parent --name "Movie.2024.2160p.BluRay.REMUX"
        fk tools rename-parent /path/to/Release --dry-run
    """
    print_module_banner("Rename Parent")

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

    do_apply = not dry_run
    targets = _find_rename_parent_targets(target_folder)
    if not targets:
        print_warning(
            tr(
                "tools.rename_parent.no_files",
                default="Could not derive a folder name — no recognizable release files found in {folder}",
                folder=target_folder,
            )
        )
        raise SystemExit(1)

    if name and len(targets) > 1:
        print_error("--name can only be used when a single folder is being renamed.")
        raise SystemExit(1)

    default_lang = str(
        (settings.get("modules") or {}).get("renamer", {}).get("default_language_tag") or "MULTI"
    )
    handled_any = False
    for folder_to_rename in targets:
        new_name = name or _derive_name_from_payload(folder_to_rename)
        if not new_name:
            new_name = _derive_name_from_renamer(folder_to_rename, default_lang)
        if not new_name:
            print_warning(
                tr(
                    "tools.rename_parent.no_files",
                    default="Could not derive a folder name — no recognizable release files found in {folder}",
                    folder=folder_to_rename,
                )
            )
            continue
        _rename_folder(folder_to_rename, new_name, apply=do_apply)
        handled_any = True

    if not handled_any:
        raise SystemExit(1)
