"""``swirrl sort`` — sort release folders into categorized subdirectories.

Analyses release folder names using regex patterns to detect media type
(movie, series, anime, documentary, etc.) and optionally enriches the
classification with TMDb metadata.  Moves each release into a matching
subdirectory under the target root.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from rich import box
from rich.table import Table

from swirrl.core.cli_helpers import join_path_parts
from swirrl.core.i18n import tr
from swirrl.ui.branding import print_module_banner
from swirrl.ui.click_helper import click
from swirrl.ui.console import console, print_error, print_info, print_success, print_warning
from swirrl.ui.unified_selector import confirm_choice

# ── Classification patterns ─────────────────────────────────────────────────

_SERIES_PATTERN = re.compile(
    r"[.\s]S\d{1,2}(?:E\d{1,3})?[.\s]|[.\s](?:Season|Saison)[.\s]?\d",
    re.IGNORECASE,
)
_ANIME_MARKERS = re.compile(
    r"[.\s](?:VOSTFR|MULTi\.(?:VFF|FRENCH))[.\s].*(?:1080p|720p|2160p)"
    r"|(?:HEVC|x265)[.\s].*(?:WEBRip|WEB-DL)[.\s].*(?:CR|Crunchyroll|Funimation|ADN)",
    re.IGNORECASE,
)
_ANIME_GROUPS = re.compile(
    r"-(?:SubsPlease|Erai-raws|EMBER|VARYG|Tsundere-Raws|YURASUKA|Judas)\b",
    re.IGNORECASE,
)
_DOC_PATTERN = re.compile(
    r"[.\s](?:DOCU|Documentary|Documentaire)[.\s]",
    re.IGNORECASE,
)
_CONCERT_PATTERN = re.compile(
    r"[.\s](?:CONCERT|Live\.At|Live\.From|LIVE\.IN)[.\s]",
    re.IGNORECASE,
)


class MediaCategory:
    """Known category constants."""

    MOVIE = "Movies"
    SERIES = "Series"
    ANIME = "Anime"
    DOCUMENTARY = "Documentaries"
    CONCERT = "Concerts"
    UNKNOWN = "Unsorted"


_ALL_CATEGORIES = frozenset(
    {
        MediaCategory.MOVIE,
        MediaCategory.SERIES,
        MediaCategory.ANIME,
        MediaCategory.DOCUMENTARY,
        MediaCategory.CONCERT,
        MediaCategory.UNKNOWN,
    }
)


@dataclass(slots=True)
class SortPlanItem:
    """One release folder and its classification."""

    source: Path
    category: str
    destination: Path
    confidence: str = "regex"  # "regex" | "tmdb"


@dataclass(slots=True)
class SortPlan:
    """Full sort plan for a root folder."""

    items: list[SortPlanItem] = field(default_factory=list)

    @property
    def by_category(self) -> dict[str, list[SortPlanItem]]:
        result: dict[str, list[SortPlanItem]] = {}
        for item in self.items:
            result.setdefault(item.category, []).append(item)
        return result


# ── Classification engine ────────────────────────────────────────────────────


def classify_release(name: str) -> str:
    """Classify a release folder name into a media category using regex."""
    if _ANIME_GROUPS.search(name) or _ANIME_MARKERS.search(name):
        return MediaCategory.ANIME
    if _DOC_PATTERN.search(name):
        return MediaCategory.DOCUMENTARY
    if _CONCERT_PATTERN.search(name):
        return MediaCategory.CONCERT
    if _SERIES_PATTERN.search(name):
        return MediaCategory.SERIES
    # Default: movie (most common release type)
    return MediaCategory.MOVIE


def build_sort_plan(source_root: Path, target_root: Path | None = None) -> SortPlan:
    """Scan immediate subdirectories and classify each release."""
    dest_root = target_root or source_root
    plan = SortPlan()

    for entry in sorted(source_root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name.startswith("_"):
            continue
        # Skip category folders that already exist
        if entry.name in _ALL_CATEGORIES:
            continue

        category = classify_release(entry.name)
        destination = dest_root / category / entry.name
        plan.items.append(SortPlanItem(source=entry, category=category, destination=destination))

    return plan


# ── Display ──────────────────────────────────────────────────────────────────


def _print_sort_plan(plan: SortPlan) -> None:
    """Render the sort plan as a Rich table."""
    table = Table(
        title=tr("sort.plan.title", default="Sort Plan"),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("sort.column.release", default="Release"), ratio=3, overflow="fold")
    table.add_column(tr("sort.column.category", default="Category"), width=16, no_wrap=True)
    table.add_column(tr("sort.column.confidence", default="Source"), width=8, no_wrap=True)

    category_styles = {
        MediaCategory.MOVIE: "cyan",
        MediaCategory.SERIES: "green",
        MediaCategory.ANIME: "magenta",
        MediaCategory.DOCUMENTARY: "yellow",
        MediaCategory.CONCERT: "blue",
        MediaCategory.UNKNOWN: "dim",
    }

    for item in plan.items:
        style = category_styles.get(item.category, "white")
        table.add_row(
            item.source.name,
            f"[{style}]{item.category}[/{style}]",
            item.confidence,
        )

    console.print(table)

    # Summary counts
    by_cat = plan.by_category
    parts = [f"{cat}: {len(items)}" for cat, items in sorted(by_cat.items())]
    console.print(f"\n[dim]{' │ '.join(parts)} │ Total: {len(plan.items)}[/dim]")


def _apply_sort_plan(plan: SortPlan, *, move: bool = True) -> tuple[int, int]:
    """Execute the sort plan. Returns (moved, errors)."""
    moved = 0
    errors = 0
    for item in plan.items:
        try:
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            if move:
                shutil.move(str(item.source), str(item.destination))
            else:
                shutil.copytree(str(item.source), str(item.destination))
            moved += 1
        except Exception as exc:
            print_error(f"{item.source.name}: {exc}")
            errors += 1
    return moved, errors


# ── CLI command ──────────────────────────────────────────────────────────────


def _rename_release_folder(folder: Path, *, dry_run: bool) -> str | None:
    """Derive a normalized name for a release folder using the renamer engine."""
    if not folder.is_dir():
        return None
    try:
        from swirrl.modules.renamer.service import RenamerService

        service = RenamerService()
        report = service.run(
            folder,
            default_lang="",
            apply_changes=False,
            force_lang=False,
            remove_terms=(),
            insert_after_pairs=(),
        )
        for detail in report.details:
            if detail.status in ("renamed", "planned", "case-only", "planned-case-only"):
                target_name = detail.after.get("name", "")
                if target_name:
                    new_name = Path(target_name).stem
                    if new_name and new_name != folder.name:
                        new_path = folder.parent / new_name
                        if new_path.exists():
                            print_warning(
                                tr(
                                    "sort.rename.target_exists",
                                    default="Cannot rename {name}: target already exists",
                                    name=folder.name,
                                )
                            )
                            return None
                        if not dry_run:
                            folder.rename(new_path)
                            print_success(
                                tr(
                                    "sort.rename.done",
                                    default="Renamed: {old} → {new}",
                                    old=folder.name,
                                    new=new_name,
                                )
                            )
                        else:
                            print_info(
                                tr(
                                    "sort.rename.would",
                                    default="Would rename: {old} → {new}",
                                    old=folder.name,
                                    new=new_name,
                                )
                            )
                        return new_name
    except Exception as exc:
        print_warning(
            tr(
                "sort.rename.error",
                default="Rename failed for {name}: {error}",
                name=folder.name,
                error=str(exc),
            )
        )
    return None


def run_sort_command(
    *,
    path: str | None,
    target: str | None = None,
    dry_run: bool = False,
    copy: bool = False,
    rename_folders: bool = False,
) -> int:
    """Run sort command logic."""
    print_module_banner("Sort")

    if not path:
        print_error(
            tr(
                "sort.error.no_path",
                default="Please specify the folder to sort: swirrl sort <path>",
            )
        )
        return 1

    source_root = Path(path)
    if not source_root.is_dir():
        print_error(
            tr(
                "sort.error.not_directory",
                default="Not a directory: {path}",
                path=source_root,
            )
        )
        return 1

    target_root = Path(target) if target else None

    plan = build_sort_plan(source_root, target_root)
    if not plan.items:
        print_info(tr("sort.info.nothing", default="No release folders found to sort."))
        return 0

    _print_sort_plan(plan)

    if dry_run:
        print_info(tr("common.dry_run_completed", default="Dry-run completed."))
        return 0

    confirmed = confirm_choice(
        title=tr(
            "sort.confirm.apply",
            default="Sort {count} release(s) into category folders?",
            count=len(plan.items),
        ),
        default=True,
    )
    if not confirmed:
        print_info(tr("sort.info.cancelled", default="Sort cancelled."))
        return 0

    action = "copy" if copy else "move"
    moved, errors = _apply_sort_plan(plan, move=not copy)

    print_success(
        tr(
            "sort.success.completed",
            default="Sort completed: {moved} {action}d, {errors} error(s).",
            moved=moved,
            action=action,
            errors=errors,
        )
    )

    # Rename folders after sorting if requested
    if rename_folders and moved > 0:
        rename_count = 0
        for item in plan.items:
            dest = item.destination
            if dest.exists():
                result = _rename_release_folder(dest, dry_run=False)
                if result:
                    rename_count += 1
        if rename_count:
            print_success(
                tr(
                    "sort.rename.summary",
                    default="Renamed {count} folder(s).",
                    count=rename_count,
                )
            )

    return 1 if errors > 0 else 0


@click.command(
    "sort",
    help=tr(
        "cli.sort.help",
        default=(
            "Sort release folders into categorized subdirectories.\n\n"
            "Analyses folder names to detect media type (movie, series, anime, "
            "documentary, concert) and organizes them into matching subfolders.\n\n"
            "Use -s/--source to specify the folder to scan.\n\n"
            "Quick examples:\n"
            "  swirrl sort -s /path/to/downloads               # Preview + confirm\n"
            "  swirrl sort -s /path/to/downloads -d             # Dry-run only\n"
            "  swirrl sort -s /downloads -t /nas/media          # Sort into separate target\n"
            "  swirrl sort -s /path/to/downloads --copy         # Copy instead of move\n"
            "  swirrl sort -s /path/to/downloads -R             # Sort + normalize folder names"
        ),
    ),
)
@click.argument("path_parts", nargs=-1, required=False)
@click.option(
    "-s",
    "--source",
    "source_path",
    default=None,
    help=tr(
        "cli.sort.option.source",
        default="Source folder to scan for release folders (required).",
    ),
)
@click.option(
    "-t",
    "--target",
    default=None,
    help=tr(
        "cli.sort.option.target",
        default="Target root directory. Defaults to source directory.",
    ),
)
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    help=tr("cli.sort.option.dry_run", default="Preview only, do not move anything."),
)
@click.option(
    "--copy",
    is_flag=True,
    help=tr("cli.sort.option.copy", default="Copy instead of move."),
)
@click.option(
    "-R",
    "--rename",
    "rename_folders",
    is_flag=True,
    help=tr(
        "cli.sort.option.rename",
        default="Normalize release folder names after sorting (uses renamer engine).",
    ),
)
def sort_command(
    path_parts: tuple[str, ...],
    source_path: str | None,
    target: str | None,
    dry_run: bool,
    copy: bool,
    rename_folders: bool,
) -> int:
    """Handle sort command."""
    # -s/--source takes priority, positional arg as fallback
    resolved_source = source_path or join_path_parts(path_parts) or None
    return run_sort_command(
        path=resolved_source,
        target=target,
        dry_run=dry_run,
        copy=copy,
        rename_folders=rename_folders,
    )
