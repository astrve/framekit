"""Upload command for managing torrent uploads to trackers."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import click
from rich import box
from rich.panel import Panel
from rich.table import Table

from framekit.core.cli_helpers import print_fatal
from framekit.modules.upload import DiscoveryService, TorrentMetadata, UploadService
from framekit.ui.console import console
from framekit.ui.timeline import reset_timeline, show_step
from framekit.ui.unified_selector import (
    SelectionItem,
    UnifiedSelector,
    confirm_choice,
    text_input,
)

# ── Known tracker profiles ───────────────────────────────────────────────────

KNOWN_TRACKERS: dict[str, dict] = {
    "C411": {"url": "https://c411.org", "type": "c411"},
    "BeyondHD (BHD)": {"url": "https://beyond-hd.me", "type": "unit3d"},
    "Blutopia (BLU)": {"url": "https://blutopia.cc", "type": "unit3d"},
    "Aither (ATH)": {"url": "https://aither.cc", "type": "unit3d"},
    "ReelFliX (RFX)": {"url": "https://reelflix.xyz", "type": "unit3d"},
    "SkipTheTrailers (STT)": {"url": "https://skipthetrailers.xyz", "type": "unit3d"},
    "Hawke-One (HWK)": {"url": "https://hawke.uno", "type": "unit3d"},
    "OldToons World (OTW)": {"url": "https://oldtoons.world", "type": "unit3d"},
    "Orpheus Network (OPS)": {"url": "https://orpheus.network", "type": "gazelle"},
    "Redacted (RED)": {"url": "https://redacted.ch", "type": "gazelle"},
    "Custom / Other": {"url": "", "type": "unit3d"},
}

C411_CATEGORIES: dict[int, str] = {
    1: "Films & Videos",
    2: "Ebook",
    3: "Audio",
    4: "Applications",
    5: "Jeux Video",
    6: "Emulation",
    7: "GPS",
    8: "XXX",
    9: "Nulled",
    10: "Imprimante 3D",
}

C411_SUBCATEGORIES: dict[int, dict[int, str]] = {
    1: {
        1: "Animation",
        2: "Animation Serie",
        3: "Concert",
        4: "Documentaire",
        5: "Emission TV",
        6: "Film",
        7: "Serie TV",
        8: "Spectacle",
        9: "Sport",
        10: "Video-clips",
    },
    2: {11: "Audio", 12: "BDs", 13: "Comics", 14: "Livres", 15: "Manga", 16: "Presse"},
    3: {17: "Karaoke", 18: "Musique", 19: "Podcast Radio", 20: "Samples"},
    4: {
        21: "Autre",
        22: "Formation",
        23: "Linux",
        24: "MacOS",
        25: "Smartphone",
        26: "Tablette",
        27: "Windows",
    },
    5: {
        28: "Autre",
        29: "Linux",
        30: "MacOS",
        31: "Microsoft",
        32: "Nintendo",
        33: "Smartphone",
        34: "Sony",
        35: "Tablette",
        36: "Windows",
    },
    6: {37: "Emulateur", 38: "ROM/ISO"},
    7: {39: "Applications", 40: "Cartes", 41: "Divers"},
    8: {42: "Ebooks", 43: "Films", 44: "Hentai", 45: "Images", 46: "Jeux"},
    9: {47: "Divers", 48: "Mobile", 49: "Scripts PHP", 50: "Wordpress"},
    10: {51: "Objets", 52: "Personnages", 53: "Pack"},
}

C411_LANGUAGE_VALUES: dict[int, str] = {
    1: "Anglais",
    2: "Francais (VFF)",
    3: "Muet",
    4: "Multi (FR inclus)",
    5: "Multi (QC inclus)",
    6: "Quebecois (VFQ)",
    7: "VFSTFR",
    8: "VOSTFR",
    422: "Multi VF2 (FR+QC)",
}

C411_QUALITY_VALUES: dict[int, str] = {
    10: "BluRay 4K",
    11: "BluRay Full",
    12: "BluRay Remux",
    16: "HDRip 1080",
    24: "WEB-DL",
    25: "WEB-DL 1080",
    26: "WEB-DL 4K",
    413: "Bluray.HDLight 1080",
}

C411_SEASON_VALUES: dict[int, str] = {
    118: "Serie integrale",
    119: "Hors saison",
    120: "Non communique",
    **{index: f"Saison {index - 120:02d}" for index in range(121, 151)},
}

C411_EPISODE_VALUES: dict[int, str] = {
    96: "Saison complete",
    117: "Non communique",
    97: "Episode 01",
    98: "Episode 02",
    **{index: f"Episode {index - 96:02d}" for index in range(99, 117)},
}

# ── Timeline helpers (shared from framekit.ui.timeline) ──────────────────────

_reset_timeline = reset_timeline
_show_step = show_step


# ── CLI group ────────────────────────────────────────────────────────────────


@click.group(name="upload")
def upload_group():
    """Beta commands for tracker uploads."""


def _select_label(
    *,
    title: str,
    items: list[SelectionItem[str]],
    page_size: int = 8,
) -> str | None:
    """Select a value with UnifiedSelector."""
    result = UnifiedSelector[str](title=title, items=items, page_size=page_size).select()
    if result.cancelled:
        return None
    return result.value


def _resolve_tracker_selection(
    trackers: list[dict[str, Any]], tracker: str | None, *, is_tty: bool
) -> str | None:
    """Resolve tracker from CLI arg or interactive selector."""
    if tracker:
        wanted = tracker.strip()
        if not wanted:
            print_fatal("--tracker cannot be empty")
            return None
        # Exact name
        for row in trackers:
            if str(row.get("name", "")) == wanted:
                return str(row.get("name", ""))
        # Case-insensitive name
        wanted_lower = wanted.lower()
        for row in trackers:
            name = str(row.get("name", "")).strip()
            if name and name.lower() == wanted_lower:
                return name
        # Type shortcut (only if unique)
        by_type = [
            str(row.get("name", ""))
            for row in trackers
            if str(row.get("type", "")).lower() == wanted_lower
        ]
        if len(by_type) == 1:
            return by_type[0]
        # Domain shortcut
        wanted_host = wanted_lower.replace("https://", "").replace("http://", "").strip("/")
        for row in trackers:
            raw_url = str(row.get("url", "")).strip()
            host = urlparse(raw_url).netloc.lower() if raw_url else ""
            if host and (wanted_host in host or host in wanted_host):
                return str(row.get("name", ""))
        print_fatal(
            f"Unknown tracker: {tracker}",
            "Run: framekit upload list-trackers",
        )
        return None
    if not is_tty:
        print_fatal("--tracker is required in non-interactive mode")
        return None
    selected = _select_label(
        title="Select tracker",
        items=[
            SelectionItem(value=t["name"], label=t["name"], description=t["url"]) for t in trackers
        ],
    )
    return selected or None


def _infer_release_display_name(torrent_file: Path) -> str:
    """Infer a human-friendly display name from torrent file stem."""
    stem = torrent_file.stem
    try:
        from framekit.modules.upload.metadata_extractor import ReleaseParser

        parsed = ReleaseParser.parse(stem)
        if parsed.title:
            return " ".join(word.capitalize() for word in parsed.title.split())
    except Exception:
        return stem.replace(".", " ").replace("_", " ")
    return stem.replace(".", " ").replace("_", " ")


def _resolve_torrent_input_path(path: Path, *, is_tty: bool) -> Path | None:
    """Resolve a .torrent file from either a direct file path or a release folder."""
    if path.is_file():
        if path.suffix.lower() == ".torrent":
            return path
        print_fatal(f"Expected a .torrent file, got: {path}")
        return None

    if not path.is_dir():
        print_fatal(f"Input path is not a file or directory: {path}")
        return None

    direct_candidates = sorted(p for p in path.glob("*.torrent") if p.is_file())
    candidates = direct_candidates
    if not candidates:
        candidates = sorted(p for p in path.rglob("*.torrent") if p.is_file())
    if not candidates:
        print_fatal(f"No .torrent file found in folder: {path}")
        return None
    if len(candidates) == 1:
        return candidates[0]

    if not is_tty:
        print_fatal(
            "Multiple .torrent files found in folder. "
            "Provide the exact .torrent path in non-interactive mode."
        )
        return None

    selected = _select_label(
        title="Select torrent file",
        items=[
            SelectionItem(
                value=str(candidate), label=candidate.name, description=str(candidate.parent)
            )
            for candidate in candidates
        ],
        page_size=10,
    )
    return Path(selected) if selected else None


def _description_candidates(torrent_file: Path) -> list[Path]:
    folder = torrent_file.parent
    stem = torrent_file.stem
    patterns = [
        f"{stem}.bbcode.txt",
        f"{stem}.bbcode",
        f"{stem}.bb",
        f"{stem}_prez_bbcode.txt",
        "description.bbcode.txt",
        "description.bbcode",
        "release.bbcode.txt",
        "release.bbcode",
        "*.bbcode.txt",
        "*_prez_bbcode.txt",
        "*.bbcode",
        "*.bb",
    ]
    ordered: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for candidate in sorted(folder.glob(pattern)):
            resolved = candidate.resolve()
            if candidate.is_file() and resolved not in seen:
                seen.add(resolved)
                ordered.append(candidate)
    return ordered


def _infer_description_from_release(torrent_file: Path, *, is_tty: bool) -> str | None:
    candidates = _description_candidates(torrent_file)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0].read_text(encoding="utf-8").strip() or None
    if not is_tty:
        return None

    selected = _select_label(
        title="Select BBCode description file",
        items=[
            SelectionItem(
                value=str(candidate), label=candidate.name, description=str(candidate.parent)
            )
            for candidate in candidates
        ],
        page_size=10,
    )
    if not selected:
        return None
    return Path(selected).read_text(encoding="utf-8").strip() or None


def _resolve_upload_text_fields(
    torrent_file: Path,
    *,
    name: str | None,
    description: str | None,
    description_file: Path | None,
    preset_description: str | None,
    is_tty: bool,
) -> tuple[str, str] | None:
    """Resolve name/description with strict non-interactive validation."""
    inferred_name = _infer_release_display_name(torrent_file)
    if name:
        resolved_name = name
    elif is_tty:
        resolved_name = text_input(title="Torrent name", default=inferred_name, mandatory=True)
    else:
        resolved_name = inferred_name
    if description and description_file is not None:
        print_fatal("Use either --description or --description-file, not both")
        return None
    if description_file is not None:
        resolved = description_file.read_text(encoding="utf-8").strip()
        if resolved:
            return resolved_name, resolved
        print_fatal("--description-file is empty")
        return None
    if description:
        return resolved_name, description
    if preset_description:
        return resolved_name, preset_description
    inferred = _infer_description_from_release(torrent_file, is_tty=is_tty)
    if inferred:
        return resolved_name, inferred
    if is_tty:
        return resolved_name, text_input(title="Description (BBCode)", mandatory=True)
    print_fatal("--description is required in non-interactive mode")
    return None


def _resolve_choice_field(
    *,
    field_label: str,
    current: str | None,
    values: list[str],
    is_tty: bool,
    fallback: str,
) -> str:
    """Resolve category/type/resolution from CLI arg, selector, or fallback."""
    if current:
        return current
    if values:
        if is_tty:
            selected = _select_label(
                title=f"Select {field_label}",
                items=[SelectionItem(value=value, label=value) for value in values],
            )
            if selected:
                return selected
        return values[0]
    return fallback


def _parse_options_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("options JSON must be an object")
    return parsed


def _looks_like_c411_tracker(tracker_info: dict[str, Any] | None) -> bool:
    if not tracker_info:
        return False
    tracker_type = str(tracker_info.get("type", "") or "").lower()
    if tracker_type == "c411":
        return True
    tracker_url = str(tracker_info.get("url", "") or "").lower()
    return "c411.org" in tracker_url


def _select_int_value(title: str, values: dict[int, str]) -> int | None:
    selected = _select_label(
        title=title,
        items=[
            SelectionItem(value=str(key), label=f"{key} - {label}")
            for key, label in sorted(values.items())
        ],
        page_size=12,
    )
    return int(selected) if selected and selected.isdigit() else None


def _resolve_c411_category_id(
    *,
    tracker_info: dict[str, Any] | None,
    provided_category_id: int | None,
    is_tty: bool,
) -> int | None:
    if provided_category_id is not None:
        return provided_category_id
    defaults = tracker_info.get("defaults", {}) if tracker_info else {}
    default_category = defaults.get("c411_category_id")
    if isinstance(default_category, int):
        return default_category
    if not is_tty:
        return None
    return _select_int_value("Select c411 category", C411_CATEGORIES)


def _resolve_c411_subcategory_id(
    *,
    category_id: int | None,
    tracker_info: dict[str, Any] | None,
    provided_subcategory_id: int | None,
    is_tty: bool,
) -> int | None:
    if provided_subcategory_id is not None:
        return provided_subcategory_id
    defaults = tracker_info.get("defaults", {}) if tracker_info else {}
    default_subcategory = defaults.get("c411_subcategory_id")
    if isinstance(default_subcategory, int):
        return default_subcategory
    if not is_tty or category_id is None:
        return None
    choices = C411_SUBCATEGORIES.get(category_id, {})
    if not choices:
        return None
    return _select_int_value("Select c411 subcategory", choices)


def _resolve_c411_options(
    *,
    subcategory_id: int | None,
    tracker_info: dict[str, Any] | None,
    options_json: str | None,
    is_tty: bool,
) -> dict[str, Any]:
    parsed = _parse_options_json(options_json)
    if parsed:
        return parsed
    defaults = tracker_info.get("defaults", {}) if tracker_info else {}
    default_options = defaults.get("c411_options")
    if isinstance(default_options, dict):
        return default_options
    if not is_tty:
        return {}
    if subcategory_id not in {6, 7}:
        raw = text_input(
            title="c411 options JSON (optional, empty for none)",
            mandatory=False,
        ).strip()
        return _parse_options_json(raw) if raw else {}

    options: dict[str, Any] = {}
    language_id = _select_int_value("Select c411 language option", C411_LANGUAGE_VALUES)
    if language_id is not None:
        options["1"] = [language_id]

    quality_id = _select_int_value("Select c411 quality option", C411_QUALITY_VALUES)
    if quality_id is not None:
        options["2"] = quality_id

    if subcategory_id == 7:
        season_id = _select_int_value("Select c411 season option", C411_SEASON_VALUES)
        if season_id is not None:
            options["7"] = season_id
        episode_id = _select_int_value("Select c411 episode option", C411_EPISODE_VALUES)
        if episode_id is not None:
            options["6"] = episode_id

    return options


def _resolve_c411_nfo_path(
    *,
    torrent_file: Path,
    provided_nfo: Path | None,
    is_tty: bool,
) -> Path | None:
    if provided_nfo is not None:
        return provided_nfo
    inferred = torrent_file.with_suffix(".nfo")
    if inferred.exists():
        return inferred
    sibling_nfo = sorted(
        candidate for candidate in torrent_file.parent.glob("*.nfo") if candidate.is_file()
    )
    if len(sibling_nfo) == 1:
        return sibling_nfo[0]
    if len(sibling_nfo) > 1 and is_tty:
        selected = _select_label(
            title="Select NFO file for c411",
            items=[
                SelectionItem(
                    value=str(candidate),
                    label=candidate.name,
                    description=str(candidate.parent),
                )
                for candidate in sibling_nfo
            ],
            page_size=10,
        )
        if selected:
            return Path(selected)
    if not is_tty:
        return None
    raw = text_input(
        title="NFO file path for c411 (required if not next to .torrent)",
        mandatory=False,
    ).strip()
    if not raw:
        return None
    candidate = Path(raw)
    return candidate if candidate.exists() else None


def _apply_upload_preset(
    metadata: TorrentMetadata,
    preset: str | None,
    *,
    preset_obj: Any | None = None,
) -> TorrentMetadata:
    """Apply optional preset to metadata."""
    if not preset:
        return metadata
    from framekit.modules.upload.presets import PresetManager

    manager = PresetManager()
    preset_obj = preset_obj or manager.get_preset(preset)
    if not preset_obj:
        console.print(f"[yellow]Warning: Preset '{preset}' not found[/yellow]")
        return metadata
    console.print(f"[dim]Applied preset: {preset}[/dim]")
    return manager.apply_to_metadata(preset_obj, metadata)


def _load_upload_preset(preset: str | None):
    """Load optional upload preset object."""
    if not preset:
        return None
    from framekit.modules.upload.presets import PresetManager

    manager = PresetManager()
    preset_obj = manager.get_preset(preset)
    if not preset_obj:
        console.print(f"[yellow]Warning: Preset '{preset}' not found[/yellow]")
        return None
    return preset_obj


def _resolve_tracker_ids(
    tracker_config: dict[str, Any] | None,
    metadata: TorrentMetadata,
) -> tuple[str, str, str, str]:
    """Resolve human labels to tracker ids for preview output."""
    if not tracker_config:
        return "?", "?", "?", "?"
    category_id = tracker_config.get("categories", {}).get(metadata.category, "?")
    type_id = tracker_config.get("types", {}).get(metadata.type, "?")
    resolution_id = tracker_config.get("resolutions", {}).get(metadata.resolution, "?")
    return (
        str(category_id),
        str(type_id),
        str(resolution_id),
        str(tracker_config.get("url", "?")),
    )


def _render_upload_preview(
    *,
    tracker: str,
    tracker_url: str,
    metadata: TorrentMetadata,
    category_id: str,
    type_id: str,
    resolution_id: str,
) -> None:
    """Render dry-run preview table."""
    from rich.table import Table

    table = Table(title="Upload Preview", show_header=True)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Tracker", tracker)
    table.add_row("Tracker URL", tracker_url)
    table.add_row("Name", metadata.name)
    is_c411 = metadata.c411_category_id is not None or metadata.c411_subcategory_id is not None
    if is_c411:
        table.add_row("Category", metadata.category)
        table.add_row("Type", metadata.type)
        table.add_row("Resolution", metadata.resolution)
    else:
        table.add_row("Category", f"{metadata.category} (ID: {category_id})")
        table.add_row("Type", f"{metadata.type} (ID: {type_id})")
        table.add_row("Resolution", f"{metadata.resolution} (ID: {resolution_id})")
    if metadata.c411_category_id is not None:
        table.add_row("c411 categoryId", str(metadata.c411_category_id))
    if metadata.c411_subcategory_id is not None:
        table.add_row("c411 subcategoryId", str(metadata.c411_subcategory_id))
    if metadata.c411_options:
        table.add_row("c411 options", json.dumps(metadata.c411_options, ensure_ascii=False))
    if metadata.nfo_path:
        table.add_row("NFO file", metadata.nfo_path)
    if metadata.c411_draft:
        table.add_row("Mode", "[yellow]DRAFT[/yellow] — will POST to /api/user/drafts")

    if metadata.tmdb_id:
        table.add_row("TMDB ID", str(metadata.tmdb_id))
    if metadata.imdb_id:
        table.add_row("IMDB ID", metadata.imdb_id)
    if metadata.tvdb_id:
        table.add_row("TVDB ID", str(metadata.tvdb_id))
    if metadata.source:
        table.add_row("Source", metadata.source)
    if metadata.codec:
        table.add_row("Codec", metadata.codec)
    if metadata.audio:
        table.add_row("Audio", metadata.audio)
    if metadata.hdr:
        table.add_row("HDR", metadata.hdr)
    if metadata.tags:
        table.add_row("Tags", ", ".join(metadata.tags))

    desc_preview = (
        metadata.description[:200] + "..."
        if len(metadata.description) > 200
        else metadata.description
    )
    table.add_row("Description", desc_preview)
    console.print(table)
    console.print("\n[dim]This is a dry-run. No upload was performed.[/dim]")


@dataclass(slots=True)
class _SetupTrackerSelection:
    chosen_label: str
    tracker_url: str
    tracker_type: str
    is_custom: bool


@dataclass(slots=True)
class _SetupCredentials:
    tracker_name: str
    api_key: str


@dataclass(slots=True)
class _UploadModuleSettings:
    enable_upload: bool
    auto_upload: bool


@dataclass(slots=True)
class _ImageHostSettings:
    configured: bool
    image_host: str
    image_host_api_key: str


def _ensure_interactive(command_name: str) -> bool:
    if sys.stdin.isatty():
        return True
    console.print(f"[yellow]{command_name} requires an interactive terminal[/yellow]")
    return False


def _setup_select_tracker(steps: list[str]) -> _SetupTrackerSelection | None:
    _show_step(
        "Step 1 - Tracker",
        "Select your tracker from the list or choose Custom for any other tracker.",
        "Tracker",
        steps,
    )
    tracker_names = list(KNOWN_TRACKERS.keys())
    chosen_label = _select_label(
        title="Select tracker",
        items=[
            SelectionItem(
                value=label,
                label=label,
                description=KNOWN_TRACKERS[label]["url"] or "enter URL manually",
            )
            for label in tracker_names
        ],
    )
    if not chosen_label:
        return None
    profile = KNOWN_TRACKERS[chosen_label]
    tracker_url = profile["url"]
    tracker_type = profile["type"]
    is_custom = chosen_label == "Custom / Other"

    if is_custom:
        tracker_url = text_input(title="Tracker URL (e.g. https://mytracker.com)", mandatory=True)
        tracker_url = tracker_url.rstrip("/")
        type_choice = _select_label(
            title="Tracker engine type",
            items=[
                SelectionItem(
                    value="c411",
                    label="C411 API",
                    description="c411.org dedicated upload API",
                ),
                SelectionItem(
                    value="unit3d",
                    label="UNIT3D",
                    description="Most modern private trackers",
                    preselected=True,
                ),
                SelectionItem(
                    value="gazelle",
                    label="Gazelle",
                    description="Music trackers (RED, OPS)",
                ),
                SelectionItem(value="custom", label="Custom", description="Anything else"),
            ],
        )
        tracker_type = type_choice or "unit3d"

    return _SetupTrackerSelection(
        chosen_label=chosen_label,
        tracker_url=tracker_url,
        tracker_type=tracker_type,
        is_custom=is_custom,
    )


def _default_tracker_name(chosen_label: str) -> str:
    if "(" in chosen_label:
        return chosen_label.split("(")[-1].rstrip(")").strip().lower()
    return chosen_label.split("/")[0].strip().lower()


def _setup_collect_credentials(chosen_label: str, steps: list[str]) -> _SetupCredentials:
    _show_step(
        "Step 2 - Credentials",
        "Enter your API key and a short name for this tracker.",
        "Credentials",
        steps,
    )
    default_name = _default_tracker_name(chosen_label)
    tracker_name = (
        text_input(title=f"Tracker name (default: {default_name})", mandatory=False) or default_name
    )
    api_key = text_input(title="API key", mandatory=True)
    return _SetupCredentials(tracker_name=tracker_name, api_key=api_key)


def _setup_test_connection(
    *,
    selection: _SetupTrackerSelection,
    credentials: _SetupCredentials,
    steps: list[str],
) -> tuple[DiscoveryService, Any, str] | None:
    _show_step(
        "Step 3 - Connection",
        "Testing connection to the tracker...",
        "Connection",
        steps,
    )
    console.print(f"Testing connection to [cyan]{selection.tracker_url}[/cyan]...")
    discovery = DiscoveryService()
    result = discovery.discover_tracker(
        selection.tracker_url,
        credentials.api_key,
        selection.tracker_type if not selection.is_custom else None,
    )
    tracker_type = selection.tracker_type

    if result.success:
        console.print(
            f"[green]Connection OK[/green] - detected type: [cyan]{result.tracker_type}[/cyan]"
        )
        if result.categories:
            console.print(
                f"  Categories: {len(result.categories)}, Types: {len(result.types)}, Resolutions: {len(result.resolutions)}"
            )
        tracker_type = result.tracker_type
        return discovery, result, tracker_type

    console.print("[yellow]Connection test failed or tracker did not respond:[/yellow]")
    for err in result.errors:
        console.print(f"  - {err}")
    save_anyway = confirm_choice(title="Save configuration anyway (manual setup)?", default=False)
    if not save_anyway:
        return None
    return discovery, result, tracker_type


def _setup_upload_settings(steps: list[str]) -> _UploadModuleSettings:
    _show_step(
        "Step 4 - Settings",
        "Configure upload behaviour.",
        "Settings",
        steps,
    )
    enable_upload = bool(
        confirm_choice(
            title="Enable upload module? (required to use uploads)",
            default=True,
        )
    )
    auto_upload = False
    if enable_upload:
        auto_upload = bool(
            confirm_choice(
                title="Enable auto-upload after pipeline runs?",
                default=False,
            )
        )
    return _UploadModuleSettings(enable_upload=enable_upload, auto_upload=auto_upload)


def _setup_image_host(steps: list[str]) -> _ImageHostSettings:
    _show_step(
        "Step 4bis - Image Host (Optional)",
        "Configure image hosting for screenshots.",
        "Image Host",
        steps,
    )
    configure_image_host = confirm_choice(
        title="Configure image host for automatic screenshot uploads?",
        default=False,
    )
    if not configure_image_host:
        return _ImageHostSettings(configured=False, image_host="", image_host_api_key="")

    from framekit.modules.upload.image_host import ImageHostService

    host_options = [
        SelectionItem(value="imgbb", label="ImgBB", description="Requires API key, 32MB max"),
        SelectionItem(value="imgbox", label="Imgbox", description="No API key, 10MB max"),
        SelectionItem(
            value="ptpimg",
            label="PTPImg",
            description="Requires API key, 10MB max",
        ),
        SelectionItem(
            value="freeimage",
            label="FreeImage",
            description="Requires API key, 16MB max",
        ),
    ]

    image_host = _select_label(title="Select image host", items=host_options) or ""
    image_host_api_key = ""
    if image_host and ImageHostService.HOSTS[image_host]["requires_api_key"]:
        image_host_api_key = text_input(
            title=f"Enter {ImageHostService.HOSTS[image_host]['name']} API key",
            default="",
        )
    if image_host:
        console.print(f"[green]Image host configured: {image_host}[/green]")
    return _ImageHostSettings(
        configured=bool(image_host),
        image_host=image_host,
        image_host_api_key=image_host_api_key,
    )


def _setup_save_configuration(
    *,
    discovery: DiscoveryService,
    discovery_result: Any,
    tracker_type: str,
    selection: _SetupTrackerSelection,
    credentials: _SetupCredentials,
) -> bool:
    if discovery_result.success:
        return discovery.save_discovery(
            discovery_result, credentials.tracker_name, credentials.api_key
        )

    from framekit.modules.upload.models import DiscoveryResult

    manual = DiscoveryResult(
        tracker_type=tracker_type, tracker_url=selection.tracker_url, success=True
    )
    return discovery.save_discovery(manual, credentials.tracker_name, credentials.api_key)


def _persist_image_host_settings(image_host: _ImageHostSettings) -> None:
    if not image_host.configured:
        return
    from framekit.core.settings import SettingsStore

    store = SettingsStore()
    settings = store.load()
    upload_cfg = settings.get("upload", {})
    upload_cfg["image_host"] = image_host.image_host
    upload_cfg["image_host_api_key"] = image_host.image_host_api_key
    settings["upload"] = upload_cfg
    store.save(settings)


def _print_setup_summary(
    credentials: _SetupCredentials, upload_settings: _UploadModuleSettings
) -> None:
    console.print(f"\n[green]Tracker '{credentials.tracker_name}' saved.[/green]")
    console.print(
        f"Upload enabled: {'[green]yes[/green]' if upload_settings.enable_upload else '[red]no[/red]'}"
    )
    console.print(
        f"Auto-upload:    {'[green]yes[/green]' if upload_settings.auto_upload else '[red]no[/red]'}"
    )
    console.print(
        "\nTest with: [cyan]framekit upload test --tracker " + credentials.tracker_name + "[/cyan]"
    )


@dataclass(slots=True)
class _RunUploadContext:
    tracker_name: str
    tracker_info: dict[str, Any] | None
    preset_obj: Any | None
    is_tty: bool


@dataclass(slots=True)
class _RunChoiceValues:
    categories: list[str]
    types: list[str]
    resolutions: list[str]


def _resolve_run_context(
    tracker: str | None,
    preset: str | None,
) -> _RunUploadContext | None:
    trackers = UploadService.list_trackers()
    if not trackers:
        print_fatal("No trackers configured", "Run: framekit upload setup")
        return None

    preset_obj = _load_upload_preset(preset)
    is_tty = sys.stdin.isatty()
    tracker_name = _resolve_tracker_selection(trackers, tracker, is_tty=is_tty)
    if not tracker_name:
        return None
    tracker_info = UploadService.get_tracker_info(tracker_name)
    return _RunUploadContext(
        tracker_name=tracker_name,
        tracker_info=tracker_info,
        preset_obj=preset_obj,
        is_tty=is_tty,
    )


def _run_choice_values(tracker_info: dict[str, Any] | None) -> _RunChoiceValues:
    if not tracker_info:
        return _RunChoiceValues(categories=[], types=[], resolutions=[])
    return _RunChoiceValues(
        categories=list(tracker_info.get("categories", {}).keys()),
        types=list(tracker_info.get("types", {}).keys()),
        resolutions=list(tracker_info.get("resolutions", {}).keys()),
    )


def _try_auto_tmdb_id(torrent_file: Path) -> int | None:
    """Best-effort TMDB ID lookup from release title/year using configured TMDB token."""
    try:
        from framekit.core.models.metadata import MetadataLookupRequest
        from framekit.core.settings import SettingsStore
        from framekit.modules.metadata.factory import build_metadata_provider
        from framekit.modules.upload.metadata_extractor import ReleaseParser

        parsed = ReleaseParser.parse(torrent_file.stem)
        if not parsed.title:
            return None
        media_kind = (
            "single_episode" if parsed.season is not None or parsed.episode is not None else "movie"
        )
        request = MetadataLookupRequest(
            media_kind=media_kind,
            title=parsed.title,
            year=str(parsed.year) if parsed.year else None,
            season_number=parsed.season,
            episode_number=parsed.episode,
            release_title=torrent_file.stem,
        )
        settings = SettingsStore().load()
        provider = build_metadata_provider(settings, provider_name="tmdb")
        candidates = provider.search(request)
        if not candidates:
            return None
        candidate = max(candidates, key=lambda item: float(getattr(item, "confidence", 0.0)))
        provider_id = str(getattr(candidate, "provider_id", "")).strip()
        return int(provider_id) if provider_id.isdigit() else None
    except Exception:
        return None


def _resolve_tmdb_id(
    initial_tmdb_id: int | None,
    *,
    is_tty: bool,
    auto_tmdb: bool,
    torrent_file: Path,
) -> int | None:
    if initial_tmdb_id is not None:
        return initial_tmdb_id
    if auto_tmdb:
        auto = _try_auto_tmdb_id(torrent_file)
        if auto is not None:
            return auto
    if not is_tty:
        return None
    raw = text_input(title="TMDB ID (leave blank to skip)", mandatory=False)
    return int(raw) if raw.isdigit() else None


def _resolve_metadata_choices(
    *,
    ctx: _RunUploadContext,
    category: str | None,
    type: str | None,
    resolution: str | None,
) -> tuple[str, str, str]:
    values = _run_choice_values(ctx.tracker_info)
    resolved_category = _resolve_choice_field(
        field_label="category",
        current=category or (ctx.preset_obj.category if ctx.preset_obj else None),
        values=values.categories,
        is_tty=ctx.is_tty,
        fallback="Movie",
    )
    resolved_type = _resolve_choice_field(
        field_label="type",
        current=type or (ctx.preset_obj.type if ctx.preset_obj else None),
        values=values.types,
        is_tty=ctx.is_tty,
        fallback="1080p",
    )
    resolved_resolution = _resolve_choice_field(
        field_label="resolution",
        current=resolution or (ctx.preset_obj.resolution if ctx.preset_obj else None),
        values=values.resolutions,
        is_tty=ctx.is_tty,
        fallback="1920x1080",
    )
    return resolved_category, resolved_type, resolved_resolution


def _resolve_run_metadata(
    torrent_file: Path,
    *,
    ctx: _RunUploadContext,
    name: str | None,
    description: str | None,
    description_file: Path | None,
    category: str | None,
    type: str | None,
    resolution: str | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    tvdb_id: int | None,
    nfo: Path | None,
    category_id: int | None,
    subcategory_id: int | None,
    options_json: str | None,
    description_format: str | None,
    uploader_note: str | None,
    auto_tmdb: bool,
    anonymous: bool,
    stream: bool,
    draft: bool,
    preset: str | None,
) -> TorrentMetadata | None:
    text_fields = _resolve_upload_text_fields(
        torrent_file,
        name=name,
        description=description,
        description_file=description_file,
        preset_description=(
            getattr(ctx.preset_obj, "description", None) if ctx.preset_obj else None
        ),
        is_tty=ctx.is_tty,
    )
    if text_fields is None:
        return None
    resolved_name, resolved_description = text_fields

    is_c411 = _looks_like_c411_tracker(ctx.tracker_info)
    if is_c411:
        resolved_category_id = _resolve_c411_category_id(
            tracker_info=ctx.tracker_info,
            provided_category_id=category_id,
            is_tty=ctx.is_tty,
        )
        if resolved_category_id is None:
            print_fatal("c411 categoryId is required (flag or interactive selection)")
            return None
        resolved_subcategory_id = _resolve_c411_subcategory_id(
            category_id=resolved_category_id,
            tracker_info=ctx.tracker_info,
            provided_subcategory_id=subcategory_id,
            is_tty=ctx.is_tty,
        )
        if resolved_subcategory_id is None:
            print_fatal("c411 subcategoryId is required (flag or interactive selection)")
            return None
        resolved_options = _resolve_c411_options(
            subcategory_id=resolved_subcategory_id,
            tracker_info=ctx.tracker_info,
            options_json=options_json,
            is_tty=ctx.is_tty,
        )
        resolved_nfo = _resolve_c411_nfo_path(
            torrent_file=torrent_file,
            provided_nfo=nfo,
            is_tty=ctx.is_tty,
        )
        if resolved_nfo is None:
            print_fatal("c411 requires an NFO file (--nfo or <torrent>.nfo)")
            return None
        resolved_category = C411_CATEGORIES.get(
            resolved_category_id, f"Category {resolved_category_id}"
        )
        resolved_type = "c411"
        resolved_resolution = "c411"
    else:
        resolved_category, resolved_type, resolved_resolution = _resolve_metadata_choices(
            ctx=ctx,
            category=category,
            type=type,
            resolution=resolution,
        )
        resolved_category_id = None
        resolved_subcategory_id = None
        resolved_options = {}
        resolved_nfo = nfo

    resolved_tmdb_id = _resolve_tmdb_id(
        tmdb_id,
        is_tty=ctx.is_tty,
        auto_tmdb=auto_tmdb,
        torrent_file=torrent_file,
    )

    metadata = TorrentMetadata(
        name=resolved_name,
        description=resolved_description,
        category=resolved_category,
        type=resolved_type,
        resolution=resolved_resolution,
        tmdb_id=resolved_tmdb_id,
        imdb_id=imdb_id,
        tvdb_id=tvdb_id,
        anonymous=anonymous,
        stream=stream,
        nfo_path=str(resolved_nfo) if resolved_nfo else None,
        c411_category_id=resolved_category_id,
        c411_subcategory_id=resolved_subcategory_id,
        c411_options=resolved_options,
        c411_description_format=description_format,
        c411_uploader_note=uploader_note,
        c411_draft=draft,
    )
    return _apply_upload_preset(metadata, preset, preset_obj=ctx.preset_obj)


def _execute_upload_run(
    *,
    torrent_file: Path,
    tracker_name: str,
    metadata: TorrentMetadata,
) -> None:
    console.print(f"\nUploading [cyan]{torrent_file.name}[/cyan] to [cyan]{tracker_name}[/cyan]...")
    result = UploadService().upload(torrent_file, metadata, tracker_name)
    if result.success:
        console.print("[green]Upload successful[/green]")
        console.print(f"Torrent ID: [cyan]{result.torrent_id}[/cyan]")
        if result.url:
            console.print(f"URL: [cyan]{result.url}[/cyan]")
        console.print(f"Time: [yellow]{result.upload_time:.2f}s[/yellow]")
        return

    console.print("[red]Upload failed[/red]")
    for err in result.errors:
        console.print(f"  - {err}")


# ── setup wizard ─────────────────────────────────────────────────────────────


@upload_group.command(name="setup")
def setup_command():
    """Interactive wizard to configure a new tracker.

    Guides you through selecting a tracker, entering credentials,
    testing the connection, and saving to framekit.yaml.
    """
    if not _ensure_interactive("setup"):
        return

    _reset_timeline()
    steps = ["Tracker", "Credentials", "Connection", "Settings", "Image Host", "Save"]

    try:
        selection = _setup_select_tracker(steps)
        if not selection:
            console.print("[yellow]Cancelled[/yellow]")
            return

        credentials = _setup_collect_credentials(selection.chosen_label, steps)
        connection_payload = _setup_test_connection(
            selection=selection,
            credentials=credentials,
            steps=steps,
        )
        if connection_payload is None:
            console.print("[yellow]Aborted[/yellow]")
            return
        discovery, result, tracker_type = connection_payload
        upload_settings = _setup_upload_settings(steps)
        image_host_settings = _setup_image_host(steps)

        _show_step("Step 5 - Save", "Saving configuration to framekit.yaml.", "Save", steps)
        saved = _setup_save_configuration(
            discovery=discovery,
            discovery_result=result,
            tracker_type=tracker_type,
            selection=selection,
            credentials=credentials,
        )
        if not saved:
            print_fatal("Failed to save tracker configuration")
            return

        UploadService.set_upload_enabled(
            bool(upload_settings.enable_upload),
            bool(upload_settings.auto_upload),
        )
        _persist_image_host_settings(image_host_settings)
        _print_setup_summary(credentials, upload_settings)

    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled[/yellow]")
    except Exception as e:
        print_fatal(str(e), "Check tracker URL and API key")


# ── remove ───────────────────────────────────────────────────────────────────


@upload_group.command(name="remove")
def remove_command():
    """Remove a configured tracker."""
    if not sys.stdin.isatty():
        console.print("[yellow]remove requires an interactive terminal[/yellow]")
        return
    try:
        trackers = UploadService.list_trackers()
        if not trackers:
            console.print("[yellow]No trackers configured[/yellow]")
            console.print("Add one with: [cyan]framekit upload setup[/cyan]")
            return

        chosen = _select_label(
            title="Select tracker to remove",
            items=[
                SelectionItem(
                    value=t["name"],
                    label=t["name"],
                    description=f"{t['type']} - {t['url']}",
                )
                for t in trackers
            ],
        )
        if not chosen:
            return

        confirmed = confirm_choice(title=f"Remove tracker '{chosen}'?", default=False)
        if not confirmed:
            console.print("[yellow]Cancelled[/yellow]")
            return

        if UploadService.remove_tracker(chosen):
            console.print(f"[green]Removed:[/green] {chosen}")
        else:
            print_fatal(f"Tracker not found: {chosen}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
    except Exception as e:
        print_fatal(str(e))


# ── list-trackers ─────────────────────────────────────────────────────────────


@upload_group.command(name="list-trackers")
def list_trackers_command():
    """List all configured trackers."""
    try:
        from framekit.core.settings import SettingsStore

        store = SettingsStore()
        settings = store.load()
        upload_cfg = settings.get("upload", {})

        enabled = upload_cfg.get("enabled", False)
        auto_upload = upload_cfg.get("auto_upload", False)
        trackers = UploadService.list_trackers()

        console.print(
            f"\nUpload: {'[green]enabled[/green]' if enabled else '[red]disabled[/red]'}"
            f"  |  Auto-upload: {'[green]yes[/green]' if auto_upload else '[red]no[/red]'}\n"
        )

        if not trackers:
            console.print("[yellow]No trackers configured[/yellow]")
            console.print("Run: [cyan]framekit upload setup[/cyan]")
            return

        table = Table(box=box.SIMPLE)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("URL", style="blue")
        table.add_column("Categories")
        table.add_column("Types")
        table.add_column("Resolutions")

        for t in trackers:
            table.add_row(
                t["name"],
                t["type"],
                t["url"],
                str(t["categories"]),
                str(t["types"]),
                str(t["resolutions"]),
            )

        console.print(table)

    except Exception as e:
        print_fatal(str(e), "Check framekit.yaml for tracker configuration")


# ── show-tracker ──────────────────────────────────────────────────────────────


@upload_group.command(name="show-tracker")
@click.argument("tracker_name")
def show_tracker_command(tracker_name: str):
    """Show detailed info about a tracker (categories, types, resolutions)."""
    try:
        info = UploadService.get_tracker_info(tracker_name)
        if not info:
            print_fatal(f"Tracker not found: {tracker_name}")
            return

        console.print(f"\n[bold cyan]{info['name']}[/bold cyan]")
        console.print(f"Type: [yellow]{info['type']}[/yellow]  |  URL: [blue]{info['url']}[/blue]")
        console.print(f"API Key: [dim]{info['api_key']}[/dim]\n")

        for section in ("categories", "types", "resolutions"):
            data = info.get(section)
            if data:
                console.print(f"[bold]{section.capitalize()}:[/bold]")
                table = Table(box=box.SIMPLE)
                table.add_column("Name", style="cyan")
                table.add_column("ID", style="yellow")
                for k, v in sorted(data.items()):
                    table.add_row(k, str(v))
                console.print(table)

        if info.get("defaults"):
            console.print("[bold]Defaults:[/bold]")
            for k, v in info["defaults"].items():
                console.print(f"  {k}: [cyan]{v}[/cyan]")

    except Exception as e:
        print_fatal(str(e), "Verify tracker name is correct")


# ── test ─────────────────────────────────────────────────────────────────────


@upload_group.command(name="test")
@click.option(
    "--tracker", default=None, help="Tracker name to test (auto-selected if only one configured)"
)
def test_command(tracker: str | None):
    """Test connection to a configured tracker."""
    try:
        if not tracker:
            trackers = UploadService.list_trackers()
            if not trackers:
                print_fatal("No trackers configured", "Run: framekit upload setup")
                return
            if len(trackers) == 1:
                tracker = trackers[0]["name"]
                console.print(f"Auto-selected tracker: [cyan]{tracker}[/cyan]")
            elif sys.stdin.isatty():
                tracker = _select_label(
                    title="Select tracker to test",
                    items=[
                        SelectionItem(value=t["name"], label=t["name"], description=t["url"])
                        for t in trackers
                    ],
                )
                if not tracker:
                    return
            else:
                print_fatal("--tracker required when multiple trackers configured")
                return

        console.print(f"\nTesting connection to [cyan]{tracker}[/cyan]...")
        service = UploadService()
        success, message = service.test_connection(tracker)
        if success:
            console.print(f"[green]{message}[/green]")
        else:
            print_fatal(message)
    except Exception as e:
        print_fatal(str(e), "Verify tracker exists in configuration")


# ── discover ──────────────────────────────────────────────────────────────────


@upload_group.command(name="discover")
@click.option("--url", required=True, help="Tracker URL (e.g. https://tracker.com)")
@click.option("--api-key", required=True, help="API key")
@click.option("--name", required=True, help="Tracker name (e.g. mytracker)")
@click.option(
    "--type",
    "tracker_type",
    type=click.Choice(["c411", "unit3d", "gazelle", "custom"]),
    help="Tracker type (auto-detected if not specified)",
)
@click.option("--save/--no-save", default=True, help="Save to framekit.yaml")
def discover_command(url: str, api_key: str, name: str, tracker_type: str | None, save: bool):
    r"""Auto-discover tracker API capabilities and save configuration.

    \b
    Examples:
      framekit upload discover --url https://tracker.com --api-key KEY --name mytracker
      framekit upload discover --url https://tracker.com --api-key KEY --name t --type unit3d
    """
    console.print(f"\nDiscovering tracker: [cyan]{url}[/cyan]")
    try:
        discovery = DiscoveryService()
        result = discovery.discover_tracker(url, api_key, tracker_type)

        if not result.success:
            console.print("\n[red]Discovery failed[/red]")
            for err in result.errors:
                console.print(f"  - {err}")
            print_fatal("Discovery failed", "Verify the tracker URL and API key are correct")
            return

        console.print(f"[green]Success[/green] - type: [cyan]{result.tracker_type}[/cyan]")
        if result.api_version:
            console.print(f"API version: [cyan]{result.api_version}[/cyan]")

        for section, label in [
            ("categories", "Categories"),
            ("types", "Types"),
            ("resolutions", "Resolutions"),
        ]:
            data = getattr(result, section)
            if data:
                console.print(f"\n[bold]{label}:[/bold]")
                table = Table(box=box.SIMPLE)
                table.add_column("Name", style="cyan")
                table.add_column("ID", style="yellow")
                for k, v in sorted(data.items()):
                    table.add_row(k, str(v))
                console.print(table)

        if save:
            if discovery.save_discovery(result, name, api_key):
                console.print("\n[green]Configuration saved to framekit.yaml[/green]")
            else:
                print_fatal("Failed to save configuration")

    except Exception as e:
        print_fatal(str(e), "Verify tracker URL is accessible and API key is valid")


# ── run ───────────────────────────────────────────────────────────────────────


@upload_group.command(name="run")
@click.argument("torrent_file", type=click.Path(exists=True, path_type=Path))
@click.option("--tracker", default=None, help="Tracker name")
@click.option("--name", default=None, help="Torrent name")
@click.option("--description", default=None, help="Description (BBCode)")
@click.option(
    "--description-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Read description from a text/BBCode file (UTF-8)",
)
@click.option(
    "--nfo",
    "nfo_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="NFO file path (required for c411)",
)
@click.option("--category", default=None, help="Category name")
@click.option("--type", default=None, help="Type (e.g. 1080p, 2160p)")
@click.option("--resolution", default=None, help="Resolution (e.g. 1920x1080)")
@click.option("--category-id", type=int, default=None, help="c411 categoryId")
@click.option("--subcategory-id", type=int, default=None, help="c411 subcategoryId")
@click.option("--options-json", default=None, help='c411 options JSON (e.g. \'{"1":[4],"2":10}\')')
@click.option(
    "--description-format",
    type=click.Choice(["standard", "html"]),
    default=None,
    help="c411 description format",
)
@click.option("--uploader-note", default=None, help="c411 uploader note")
@click.option("--tmdb-id", type=int, default=None, help="TMDB ID")
@click.option(
    "--auto-tmdb/--no-auto-tmdb", default=False, help="Auto-resolve TMDB ID from release name"
)
@click.option("--imdb-id", default=None, help="IMDB ID")
@click.option("--tvdb-id", type=int, default=None, help="TVDB ID")
@click.option("--anonymous/--no-anonymous", default=False, help="Upload anonymously")
@click.option("--stream/--no-stream", default=True, help="Mark as streamable")
@click.option(
    "--draft",
    is_flag=True,
    help="Save as draft (c411 only) — uses /api/user/drafts, no live publish",
)
@click.option("--dry-run", is_flag=True, help="Preview upload without sending")
@click.option("--preset", default=None, help="Apply a saved preset")
def run_command(
    torrent_file: Path,
    tracker: str | None = None,
    name: str | None = None,
    description: str | None = None,
    description_file: Path | None = None,
    nfo_path: Path | None = None,
    category: str | None = None,
    type: str | None = None,
    resolution: str | None = None,
    category_id: int | None = None,
    subcategory_id: int | None = None,
    options_json: str | None = None,
    description_format: str | None = None,
    uploader_note: str | None = None,
    tmdb_id: int | None = None,
    auto_tmdb: bool = False,
    imdb_id: str | None = None,
    tvdb_id: int | None = None,
    anonymous: bool = False,
    stream: bool = True,
    draft: bool = False,
    dry_run: bool = False,
    preset: str | None = None,
):
    r"""Upload a torrent file to a tracker.

    All options are interactive when not provided as flags.

    \b
    Examples:
      framekit upload run movie.torrent --tracker bhd --name "Film 2024" \\
          --description "..." --category Films --type 1080p --resolution 1920x1080 --tmdb-id 12345

      framekit upload run movie.torrent   # fully interactive
      framekit upload run "E:\\Release\\MyFolder" --tracker C411 --dry-run
    """
    try:
        ctx = _resolve_run_context(tracker, preset)
        if ctx is None:
            return
        resolved_torrent_file = _resolve_torrent_input_path(torrent_file, is_tty=ctx.is_tty)
        if resolved_torrent_file is None:
            return
        metadata = _resolve_run_metadata(
            resolved_torrent_file,
            ctx=ctx,
            name=name,
            description=description,
            description_file=description_file,
            category=category,
            type=type,
            resolution=resolution,
            nfo=nfo_path,
            category_id=category_id,
            subcategory_id=subcategory_id,
            options_json=options_json,
            description_format=description_format,
            uploader_note=uploader_note,
            auto_tmdb=auto_tmdb,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            tvdb_id=tvdb_id,
            anonymous=anonymous,
            stream=stream,
            draft=draft,
            preset=preset,
        )
        if metadata is None:
            return
        preview_category_id, preview_type_id, preview_resolution_id, tracker_url = (
            _resolve_tracker_ids(ctx.tracker_info, metadata)
        )
        if dry_run:
            _render_upload_preview(
                tracker=ctx.tracker_name,
                tracker_url=tracker_url,
                metadata=metadata,
                category_id=preview_category_id,
                type_id=preview_type_id,
                resolution_id=preview_resolution_id,
            )
            return

        _execute_upload_run(
            torrent_file=resolved_torrent_file,
            tracker_name=ctx.tracker_name,
            metadata=metadata,
        )

    except Exception as e:
        print_fatal(str(e), "Check torrent file and metadata")


# ── history ───────────────────────────────────────────────────────────────────


@upload_group.command(name="history")
@click.option("--limit", default=20, help="Number of entries to show (default: 20)")
@click.option("--tracker", default=None, help="Filter by tracker name")
@click.option("--failed", is_flag=True, help="Show only failed uploads")
def history_command(limit: int, tracker: str | None, failed: bool):
    """Show recent upload history."""
    try:
        entries = _history_entries(limit=limit, tracker=tracker, failed=failed)

        if not entries:
            console.print("[yellow]No upload history found[/yellow]")
            return

        table = Table(box=box.SIMPLE, title=f"Upload History (last {len(entries)})")
        table.add_column("Date", style="dim")
        table.add_column("Tracker", style="cyan")
        table.add_column("Torrent", style="white")
        table.add_column("Status")
        table.add_column("ID / Error", style="dim")

        for e in entries:
            ts, tracker_name, torrent_name, status, detail = _history_row_values(e)
            table.add_row(ts, tracker_name, torrent_name, status, detail)

        console.print(table)

    except Exception as e:
        print_fatal(str(e))


def _history_entries(*, limit: int, tracker: str | None, failed: bool) -> list[dict[str, Any]]:
    entries = UploadService.get_upload_history(limit=max(limit, 200))
    if tracker:
        entries = [entry for entry in entries if entry.get("tracker") == tracker]
    if failed:
        entries = [entry for entry in entries if not entry.get("success")]
    return entries[:limit]


def _history_row_values(entry: dict[str, Any]) -> tuple[str, str, str, str, str]:
    ts = entry.get("timestamp", "")[:16].replace("T", " ")
    tracker_name = entry.get("tracker", "?")
    torrent = entry.get("torrent", entry.get("name", "?"))
    if len(torrent) > 40:
        torrent = torrent[:37] + "..."
    success = bool(entry.get("success", False))
    status = "[green]OK[/green]" if success else "[red]FAIL[/red]"
    detail = str(entry.get("torrent_id", "")) if success else (entry.get("errors") or [""])[0][:40]
    return ts, tracker_name, torrent, status, detail


# ── enable / disable ──────────────────────────────────────────────────────────


@upload_group.command(name="enable")
@click.option("--auto/--no-auto", default=None, help="Also set auto-upload after pipeline")
def enable_command(auto: bool | None):
    """Enable the upload module."""
    try:
        UploadService.set_upload_enabled(True, auto)
        console.print("[green]Upload enabled[/green]")
        if auto is True:
            console.print("Auto-upload: [green]on[/green]")
        elif auto is False:
            console.print("Auto-upload: [red]off[/red]")
    except Exception as e:
        print_fatal(str(e))


@upload_group.command(name="disable")
def disable_command():
    """Disable the upload module."""
    try:
        UploadService.set_upload_enabled(False, False)
        console.print("[red]Upload disabled[/red]")
    except Exception as e:
        print_fatal(str(e))


# ── stats ─────────────────────────────────────────────────────────────────────


@upload_group.command("stats")
@click.option("--days", default=30, help="Number of days to analyze")
def stats_command(days: int):
    """Display upload statistics dashboard."""
    from rich.table import Table

    from framekit.modules.upload.stats import UploadStats

    stats_service = UploadStats()
    stats = stats_service.get_stats(days)

    if stats["total_uploads"] == 0:
        console.print(f"[yellow]No uploads found in the last {days} days.[/yellow]")
        return

    # Summary panel
    summary = f"""[bold]Upload Statistics (Last {days} Days)[/bold]

Total Uploads: {stats["total_uploads"]}
Successful: [green]{stats["successful_uploads"]}[/green]
Failed: [red]{stats["failed_uploads"]}[/red]
Success Rate: [cyan]{stats["success_rate"]:.1f}%[/cyan]
Average Time: {stats["average_time"]:.1f}s
Last Upload: {stats["last_upload"][:19] if stats["last_upload"] else "N/A"}
"""
    console.print(Panel(summary, border_style="cyan"))

    # By tracker table
    if stats["by_tracker"]:
        table = Table(title="Statistics by Tracker", show_header=True)
        table.add_column("Tracker", style="cyan")
        table.add_column("Total", style="white")
        table.add_column("Success", style="green")
        table.add_column("Failed", style="red")
        table.add_column("Success Rate", style="cyan")

        for tracker, counts in stats["by_tracker"].items():
            rate = (counts["success"] / counts["total"] * 100) if counts["total"] > 0 else 0
            table.add_row(
                tracker,
                str(counts["total"]),
                str(counts["success"]),
                str(counts["failed"]),
                f"{rate:.1f}%",
            )

        console.print("\n")
        console.print(table)

    # ASCII chart
    console.print("\n")
    chart = stats_service.get_ascii_chart(days)
    console.print(Panel(chart, border_style="dim"))


@upload_group.command("search")
@click.argument("query")
def search_command(query: str):
    """Search for torrents across all configured trackers."""
    from rich.table import Table

    from framekit.modules.upload.dupe_checker import DupeChecker
    from framekit.modules.upload.models import TorrentMetadata
    from framekit.modules.upload.service import UploadService

    service = UploadService()
    from framekit.core.settings_singleton import get_settings_data

    settings = get_settings_data()
    trackers = settings.get("upload", {}).get("trackers", [])

    if not trackers:
        console.print("[yellow]No trackers configured.[/yellow]")
        return

    console.print(f"Searching for: [cyan]{query}[/cyan]\n")

    # Create dummy metadata for search
    metadata = TorrentMetadata(name=query, description="", category="", type="", resolution="")

    all_results = []
    for tracker_config in trackers:
        tracker_name = tracker_config["name"]
        try:
            adapter = service._get_adapter(tracker_name)  # pyright: ignore[reportPrivateUsage]  # Internal adapter accessor used by upload CLI dupe-check flow
            checker = DupeChecker(adapter)
            result = checker.check(metadata)

            if result.has_dupes:
                for dupe in result.dupes:
                    all_results.append(
                        {
                            "tracker": tracker_name,
                            "name": dupe.get("name", "Unknown"),
                            "id": dupe.get("id", "N/A"),
                            "url": dupe.get("url", ""),
                        }
                    )
        except Exception as e:
            console.print(f"[red]Error searching {tracker_name}: {e}[/red]")

    if not all_results:
        console.print("[yellow]No results found.[/yellow]")
        return

    # Display results
    table = Table(title=f"Search Results ({len(all_results)} found)", show_header=True)
    table.add_column("Tracker", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("ID", style="dim")

    for result in all_results[:50]:  # Limit to 50 results
        table.add_row(
            result["tracker"],
            result["name"][:60] + "..." if len(result["name"]) > 60 else result["name"],
            str(result["id"]),
        )

    console.print(table)


# ── preset management ─────────────────────────────────────────────────────────


@upload_group.group(name="preset")
def preset_group():
    """Manage upload presets."""


@preset_group.command(name="list")
def preset_list():
    """List all saved presets."""
    from framekit.modules.upload.presets import PresetManager

    manager = PresetManager()
    presets = manager.list_presets()

    if not presets:
        console.print("[yellow]No presets found.[/yellow]")
        return

    table = Table(title="Upload Presets", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Type", style="green")
    table.add_column("Resolution", style="green")
    table.add_column("Tags", style="dim")

    for preset in presets:
        table.add_row(
            preset.name,
            preset.category or "-",
            preset.type or "-",
            preset.resolution or "-",
            ", ".join(preset.tags) if preset.tags else "-",
        )

    console.print(table)


@preset_group.command(name="add")
def preset_add():
    """Create a new preset interactively."""
    from framekit.modules.upload.presets import PresetManager, UploadPreset

    if not sys.stdin.isatty():
        console.print("[yellow]add requires an interactive terminal[/yellow]")
        return

    console.print("[bold]Create Upload Preset[/bold]\n")

    name = text_input(title="Preset name", mandatory=True)
    description = text_input(title="Description (optional)", mandatory=False)
    category = text_input(title="Default category (e.g., Movie, TV)", mandatory=False)
    type_ = text_input(title="Default type (e.g., BluRay, WEB-DL)", mandatory=False)
    resolution = text_input(title="Default resolution (e.g., 1080p, 2160p)", mandatory=False)

    anonymous_choice = confirm_choice(title="Upload anonymously?", default=False)

    stream_choice = confirm_choice(title="Enable streaming?", default=True)

    tags_input = text_input(title="Default tags (comma-separated)", mandatory=False)
    tags = [t.strip() for t in tags_input.split(",")] if tags_input else []

    image_host = text_input(
        title="Default image host (imgbb, imgbox, ptpimg, freeimage)", mandatory=False
    )

    preset = UploadPreset(
        name=name,
        description=description,
        category=category,
        type=type_,
        resolution=resolution,
        anonymous=bool(anonymous_choice),
        stream=bool(stream_choice),
        tags=tags,
        image_host=image_host,
    )

    manager = PresetManager()
    manager.save_preset(preset)

    console.print(f"\n[green]✓[/green] Preset '{name}' saved successfully!")


@preset_group.command(name="remove")
@click.argument("name")
def preset_remove(name: str):
    """Remove a preset by name."""
    from framekit.modules.upload.presets import PresetManager

    manager = PresetManager()
    if manager.delete_preset(name):
        console.print(f"[green]✓[/green] Preset '{name}' removed successfully!")
    else:
        console.print(f"[red]✗[/red] Preset '{name}' not found.")


# ── queue management ──────────────────────────────────────────────────────────


@upload_group.group(name="queue")
def queue_group():
    """Manage upload queue."""


@queue_group.command(name="list")
def queue_list():
    """List all queued uploads."""
    from framekit.modules.upload.queue import UploadQueue

    q = UploadQueue()
    pending = q.list_pending()
    failed = q.list_failed()

    if not pending and not failed:
        console.print("[yellow]Queue is empty.[/yellow]")
        return

    if pending:
        table = Table(title="Pending Uploads", show_header=True)
        table.add_column("Job ID", style="cyan")
        table.add_column("Torrent", style="green")
        table.add_column("Trackers", style="dim")
        table.add_column("Created", style="dim")

        for job in pending:
            table.add_row(
                job.job_id[:8],
                Path(job.torrent_path).name,
                ", ".join(job.tracker_names),
                job.created_at[:19],
            )

        console.print(table)

    if failed:
        table = Table(title="Failed Uploads", show_header=True)
        table.add_column("Job ID", style="cyan")
        table.add_column("Torrent", style="green")
        table.add_column("Attempts", style="yellow")
        table.add_column("Error", style="red")

        for job in failed:
            error_msg = (
                job.error_message[:50] + "..." if len(job.error_message) > 50 else job.error_message
            )
            table.add_row(job.job_id[:8], Path(job.torrent_path).name, str(job.attempts), error_msg)

        console.print(table)


@queue_group.command(name="retry")
def queue_retry():
    """Retry all failed uploads."""
    from framekit.modules.upload.queue import UploadQueue

    q = UploadQueue()
    service = UploadService()

    failed = q.list_failed()
    if not failed:
        console.print("[yellow]No failed uploads to retry.[/yellow]")
        return

    console.print(f"Retrying {len(failed)} failed upload(s)...\n")
    results = q.retry_failed(service)

    success_count = sum(
        1 for job_results in results.values() if all(r.success for r in job_results.values())
    )

    console.print(f"\n[green]✓[/green] {success_count}/{len(results)} job(s) succeeded")


@queue_group.command(name="clear")
def queue_clear():
    """Clear completed uploads from queue."""
    from framekit.modules.upload.queue import UploadQueue

    q = UploadQueue()
    count = q.clear()
    console.print(f"[green]✓[/green] Cleared {count} completed upload(s)")
