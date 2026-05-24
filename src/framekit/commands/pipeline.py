from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from loguru import logger

from framekit.core.verbose import configure_verbosity, is_verbose

# Prefer rich_click if available; fall back to click when the rich integration is not installed.
from framekit.ui.click_helper import click

try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename fallback when pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(filename: str, replacement_text: str = "_") -> str:
        """Sanitize a filename by replacing characters illegal on most filesystems.

        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


from rich.panel import Panel

# Import from extracted modules. The step helpers and preset utilities are
# imported here even when not consumed directly in this module: ``pipeline``
# is the documented public facade for the pipeline subsystem (see ADR-0002 and
# ``tests/test_pipeline_smoke.py::test_module_exports_public_surface``). Listing
# them in ``__all__`` below preserves the re-export against future ruff
# ``--fix`` passes that would otherwise prune "unused" imports.
from framekit.commands.pipeline_batch import run_batch_pipeline
from framekit.commands.pipeline_orchestrator import execute_pipeline_modules
from framekit.commands.pipeline_presets import (
    list_pipeline_presets as _list_pipeline_presets,
)
from framekit.commands.pipeline_presets import (
    load_pipeline_preset as _load_pipeline_preset,
)
from framekit.commands.pipeline_presets import (
    select_pipeline_preset as _select_pipeline_preset,
)
from framekit.commands.pipeline_preview import (
    _gather_preview_data,
    _print_pipeline_preview,
    _print_pipeline_preview_comparison,
)
from framekit.commands.pipeline_steps import (
    _cleanmkv_step,
    _encoder_step,
    _ensure_release_context,
    _nfo_step,
    _prez_step,
    _renamer_step,
    _resolve_pipeline_locale,
    _torrent_step,
    _upload_step,
)
from framekit.core.i18n import tr
from framekit.core.models.nfo import ReleaseNfoData
from framekit.core.naming import release_name_from_mkv_paths
from framekit.core.paths import PathResolver
from framekit.core.settings import Settings, SettingsStore
from framekit.modules.metadata.config import (
    looks_like_tmdb_read_access_token,
    normalize_secret_input,
)
from framekit.ui.branding import print_module_banner
from framekit.ui.console import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from framekit.ui.unified_selector import (
    SelectorDivider,
    SelectorEntry,
    SelectorOption,
    confirm_choice,
    text_input,
)
from framekit.ui.unified_selector import (
    select_many as _select_many,
)
from framekit.ui.unified_selector import (
    select_one as _select_one,
)

PIPELINE_MODULES = (
    "renamer",
    "cleanmkv",
    "metadata",
    "nfo",
    "torrent",
    "prez",
    "encode",
    "screenshot",
    "seedbox",
    "upload",
    "rename-parent",
)
# Display order for module selection.
# Execution order for heavy/dependent phases is handled in pipeline_orchestrator.
PIPELINE_MODULES_DEFAULT = ("renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez")
PIPELINE_METADATA_MODULES = frozenset({"metadata", "nfo", "prez", "upload"})
PIPELINE_MODULE_ALIASES = {
    "encoder": "encode",
    "enc": "encode",
    "rename_parent": "rename-parent",
    "renameparent": "rename-parent",
}
PipelineStep = tuple[str, str, Callable[[], int]]
_PIPELINE_NFO_OUTPUT_MODES = frozenset({"global", "per_file", "both"})
_PIPELINE_NFO_TEMPLATE_ALIASES = {
    "default": "default",
    "classic": "default",
    "detailed": "detailed",
    "movie_default": "default",
    "series_default": "default",
    "single_episode_default": "default",
    "movie_detailed": "detailed",
    "series_detailed": "detailed",
    "single_episode_detailed": "detailed",
}


# Documented public facade for the pipeline subsystem (ADR-0002). Tests assert
# every name below is importable from ``framekit.commands.pipeline``; do not
# remove an entry without coordinating with ``tests/test_pipeline_smoke.py``.
__all__ = [
    "PIPELINE_MODULES",
    "PIPELINE_MODULES_DEFAULT",
    "PipelineContext",
    "PipelineStep",
    "execute_pipeline_modules",
    "pipeline_command",
    "run_batch_pipeline",
    "run_pipeline_command",
    # Preset discovery (re-exported from pipeline_presets).
    "_list_pipeline_presets",
    "_load_pipeline_preset",
    "_select_pipeline_preset",
    # Preview helpers (re-exported from pipeline_preview).
    "_gather_preview_data",
    "_print_pipeline_preview",
    "_print_pipeline_preview_comparison",
    # Step helpers (re-exported from pipeline_steps).
    "_cleanmkv_step",
    "_encoder_step",
    "_ensure_release_context",
    "_nfo_step",
    "_prez_step",
    "_renamer_step",
    "_resolve_pipeline_locale",
    "_torrent_step",
    "_upload_step",
]


@dataclass(slots=True)
class PipelineContext:
    """Pipeline context."""

    release: ReleaseNfoData | None = None
    metadata_context: dict | None = None
    nfo_path: Path | None = None
    nfo_outputs: tuple[Path, ...] = field(default_factory=tuple)
    torrent_path: Path | None = None
    prez_outputs: tuple[Path, ...] = field(default_factory=tuple)
    screenshot_outputs: tuple[Path, ...] = field(default_factory=tuple)
    dry_run: bool = False


# BatchQueueItem moved to framekit.modules.batch.models


def _pipeline_explain_text() -> str:
    """Return explanation text for the pipeline command."""
    return tr(
        "pipeline.explain.text",
        default=(
            "The pipeline command orchestrates multiple modules in sequence:\n\n"
            "1. Renamer: Standardize filenames\n"
            "2. CleanMKV: Remove unwanted tracks\n"
            "3. Metadata: Resolve metadata context\n"
            "4. NFO: Generate release information\n"
            "5. Torrent: Create torrent file\n"
            "6. Prez: Generate presentation files\n"
            "7. Encode: Encode video files (opt-in)\n"
            "8. Screenshot / Seedbox / Upload / Rename parent (opt-in)\n\n"
            "Use --preset to load a saved configuration.\n"
            "Use --preview to see what will happen before execution."
        ),
    )


def _module_label(name: str) -> str:
    return {
        "renamer": tr("pipeline.step.renamer", default="Renamer"),
        "cleanmkv": tr("pipeline.step.cleanmkv", default="CleanMKV"),
        "metadata": tr("pipeline.step.metadata", default="Metadata (NFO + Prez)"),
        "nfo": tr("pipeline.step.nfo", default="NFO"),
        "torrent": tr("pipeline.step.torrent", default="Torrent"),
        "prez": tr("pipeline.step.prez", default="Prez"),
        "encode": tr("pipeline.step.encoder", default="Encode"),
        "screenshot": tr("pipeline.step.screenshot", default="Screenshot"),
        "seedbox": tr("pipeline.step.seedbox", default="Seedbox"),
        "upload": tr("pipeline.step.upload", default="Upload"),
        "rename-parent": tr("pipeline.step.rename_parent", default="Rename parent"),
    }.get(name, name)


def _normalize_module_name(value: str) -> str:
    normalized = str(value).strip().lower()
    if not normalized:
        return ""
    return PIPELINE_MODULE_ALIASES.get(normalized, normalized)


def _resolve_enabled_modules(settings: dict, requested: tuple[str, ...] | None = None) -> set[str]:
    allowed = set(PIPELINE_MODULES)
    if requested is not None:
        return {
            module
            for item in requested
            if (module := _normalize_module_name(item)) in allowed
        }
    configured = (
        settings.get("modules", {})
        .get("pipeline", {})
        .get("enabled_modules", PIPELINE_MODULES_DEFAULT)
    )
    if isinstance(configured, list):
        selected = {
            module
            for item in configured
            if (module := _normalize_module_name(item)) in allowed
        }
        return selected or set(PIPELINE_MODULES_DEFAULT)
    return set(PIPELINE_MODULES_DEFAULT)


def _maybe_select_modules(
    settings: dict, selected: set[str], select_modules: bool | None, metadata_enabled: bool = True
) -> tuple[set[str], bool, bool, bool]:
    should_select = sys.stdin.isatty() if select_modules is None else select_modules
    if not should_select:
        return selected, False, False, metadata_enabled
    entries: list[SelectorEntry] = [SelectorDivider("Modules")]
    entries.extend(
        SelectorOption(
            value=name,
            label=_module_label(name),
            hint=tr("pipeline.selector.module_hint", default="Enable this module for this run"),
            selected=name in selected,
        )
        for name in PIPELINE_MODULES
    )
    entries.append(SelectorDivider("Options"))
    entries.append(
        SelectorOption(
            value="__preview__",
            label=tr("pipeline.selector.show_preview", default="Show preview before execution"),
            hint=tr(
                "pipeline.selector.preview_hint",
                default="Display comparison table with planned changes",
            ),
            selected=True,
        )
    )
    entries.append(
        SelectorOption(
            value="__auto_mode__",
            label=tr("pipeline.selector.auto_mode", default="Auto Mode (No user interaction)"),
            hint=tr(
                "pipeline.selector.auto_mode_hint",
                default="Run fully autonomous with preset configurations",
            ),
            selected=False,
        )
    )
    try:
        values = select_many(
            title=tr("pipeline.selector.title", default="Choose pipeline modules"),
            entries=entries,
            page_size=14,
            minimal_count=1,
        )
    except KeyboardInterrupt:
        raise

    show_preview = "__preview__" in values
    auto_mode = "__auto_mode__" in values
    # Metadata and encoder are now controlled via module selection only
    use_metadata = metadata_enabled  # Keep the default/configured value
    modules = {str(value) for value in values if str(value) in PIPELINE_MODULES} or selected

    return modules, show_preview, auto_mode, use_metadata


def _pipeline_has_tmdb_token(settings: dict, store: SettingsStore) -> bool:
    if os.environ.get("FRAMEKIT_TMDB_READ_ACCESS_TOKEN", "").strip():
        return True

    token = str(settings.get("metadata", {}).get("tmdb_read_access_token", "") or "").strip()
    if token and token != Settings.ENCRYPTED_PLACEHOLDER:
        return True
    if token == Settings.ENCRYPTED_PLACEHOLDER:
        return bool(Settings(store).get_tmdb_token())
    return False


def _should_prompt_missing_tmdb_token(
    *,
    settings: dict,
    selected_modules: set[str],
    metadata_enabled: bool,
    auto_mode: bool,
    store: SettingsStore,
) -> bool:
    if not metadata_enabled or auto_mode or not sys.stdin.isatty():
        return False
    if not (selected_modules & PIPELINE_METADATA_MODULES):
        return False
    if not bool(settings.get("metadata", {}).get("prompt_missing_token_in_pipeline", True)):
        return False
    return not _pipeline_has_tmdb_token(settings, store)


def _select_missing_tmdb_token_action() -> str | None:
    try:
        selected = select_one(
            title=tr(
                "pipeline.prompt.tmdb_missing",
                default="Aucun token TMDb configuré. Voulez-vous en ajouter un maintenant ?",
            ),
            entries=[
                SelectorOption(
                    value="add",
                    label=tr("pipeline.prompt.tmdb_missing.add", default="Oui"),
                    hint=tr(
                        "pipeline.prompt.tmdb_missing.add_hint",
                        default="Ajouter un token TMDb dans le vault puis continuer avec les metadata.",
                    ),
                    selected=True,
                ),
                SelectorOption(
                    value="skip",
                    label=tr("pipeline.prompt.tmdb_missing.skip", default="Non"),
                    hint=tr(
                        "pipeline.prompt.tmdb_missing.skip_hint",
                        default="Continuer cette pipeline sans metadata TMDb.",
                    ),
                ),
                SelectorOption(
                    value="never",
                    label=tr(
                        "pipeline.prompt.tmdb_missing.never",
                        default="Non, ne plus me le rappeler",
                    ),
                    hint=tr(
                        "pipeline.prompt.tmdb_missing.never_hint",
                        default="Désactiver ce rappel dans framekit.yaml.",
                    ),
                ),
            ],
            page_size=6,
            default="skip" if not sys.stdin.isatty() else None,
        )
    except (KeyboardInterrupt, EOFError):
        return None
    return str(selected) if selected else None


def _prompt_pipeline_tmdb_token() -> str | None:
    while True:
        raw = click.prompt(
            tr(
                "pipeline.prompt.tmdb_token",
                default="TMDb Read Access Token (vide pour annuler)",
            ),
            default="",
            show_default=False,
            hide_input=True,
        )
        token = normalize_secret_input(str(raw or ""))
        if not token:
            return None
        if looks_like_tmdb_read_access_token(token):
            return token
        print_error(
            tr(
                "metadata.error.invalid_token",
                default="That does not look like a valid TMDb read access token.",
            )
        )


def _store_pipeline_tmdb_token(store: SettingsStore, token: str) -> dict:
    settings_obj = Settings(store)
    settings_obj.set_tmdb_token(token)
    return store.load()


def _disable_pipeline_tmdb_reminder(settings: dict, store: SettingsStore) -> dict:
    settings.setdefault("metadata", {})["prompt_missing_token_in_pipeline"] = False
    store.save(settings)
    return store.load()


def _maybe_prompt_missing_tmdb_token(
    *,
    settings: dict,
    store: SettingsStore,
    selected_modules: set[str],
    metadata_enabled: bool,
    auto_mode: bool,
) -> tuple[dict, bool]:
    if not _should_prompt_missing_tmdb_token(
        settings=settings,
        selected_modules=selected_modules,
        metadata_enabled=metadata_enabled,
        auto_mode=auto_mode,
        store=store,
    ):
        return settings, metadata_enabled

    action = _select_missing_tmdb_token_action()
    if action == "add":
        token = _prompt_pipeline_tmdb_token()
        if not token:
            print_warning(
                tr(
                    "pipeline.warning.tmdb_token_skipped",
                    default="Pipeline sans metadata TMDb pour cette exécution.",
                )
            )
            return settings, False
        try:
            refreshed = _store_pipeline_tmdb_token(store, token)
        except Exception as exc:
            print_error(
                tr(
                    "pipeline.error.tmdb_token_save_failed",
                    default="Impossible d'enregistrer le token TMDb: {error}",
                    error=str(exc),
                )
            )
            return settings, False
        print_success(
            tr(
                "pipeline.success.tmdb_token_saved",
                default="Token TMDb enregistré. Les metadata restent activées.",
            )
        )
        return refreshed, metadata_enabled

    if action == "never":
        try:
            settings = _disable_pipeline_tmdb_reminder(settings, store)
        except Exception as exc:
            print_error(
                tr(
                    "pipeline.error.tmdb_reminder_save_failed",
                    default="Impossible d'enregistrer la préférence TMDb: {error}",
                    error=str(exc),
                )
            )
        print_warning(
            tr(
                "pipeline.warning.tmdb_reminder_disabled",
                default="Rappel TMDb désactivé. Pipeline sans metadata TMDb.",
            )
        )
        return settings, False

    print_warning(
        tr(
            "pipeline.warning.tmdb_token_skipped",
            default="Pipeline sans metadata TMDb pour cette exécution.",
        )
    )
    return settings, False


def release_artifacts_folder(root: Path) -> Path:
    """Get the Release artifacts folder for a given root directory.

    Args:
        root: Root directory

    Returns:
        Path to Release folder
    """
    return root / "Release"


def safe_release_folder_name(root: Path) -> str:
    """Generate a safe release folder name from MKV files or directory name.

    Args:
        root: Root directory

    Returns:
        Sanitized release folder name
    """
    mkv_files = sorted(root.glob("*.mkv"), key=lambda path: path.name.lower())
    if mkv_files:
        return release_name_from_mkv_paths(mkv_files)
    return sanitize_filename(root.name, replacement_text="_").strip(" .") or "release"


def release_payload_folder(root: Path) -> Path:
    """Get the release payload folder (Release/{release_name}).

    Args:
        root: Root directory

    Returns:
        Path to release payload folder
    """
    return release_artifacts_folder(root) / safe_release_folder_name(root)


# Deprecated aliases for backward compatibility
_release_artifacts_folder = release_artifacts_folder
_safe_release_folder_name = safe_release_folder_name
_release_payload_folder = release_payload_folder


def _pipeline_output_folder(work_folder: Path, root: Path | None = None) -> Path:
    if work_folder.parent.name == "Release":
        return work_folder.parent
    if root is not None:
        return _release_artifacts_folder(root)
    return work_folder


def _try_cleanmkv_output(root: Path, settings: dict) -> Path | None:
    clean_settings = settings.get("modules", {}).get("cleanmkv", {})
    configured = str(
        clean_settings.get("output_dir_name", "Release/{release}") or "Release/{release}"
    )
    clean_dir = root / configured.format(release=_safe_release_folder_name(root))
    if clean_dir.exists() and clean_dir.is_dir():
        return clean_dir
    return None


def _try_release_artifacts_child(root: Path) -> Path | None:
    release_dir = _release_artifacts_folder(root)
    if not release_dir.exists() or not release_dir.is_dir():
        return None
    candidates = [
        item
        for item in release_dir.iterdir()
        if item.is_dir() and any(child.suffix.lower() == ".mkv" for child in item.iterdir())
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _next_work_folder(root: Path, settings: dict) -> Path:
    release_payload = _release_payload_folder(root)
    if release_payload.exists() and release_payload.is_dir():
        return release_payload

    cleanmkv_out = _try_cleanmkv_output(root, settings)
    if cleanmkv_out is not None:
        return cleanmkv_out

    artifacts_child = _try_release_artifacts_child(root)
    if artifacts_child is not None:
        return artifacts_child

    legacy_clean_dir = root / "clean"
    return legacy_clean_dir if legacy_clean_dir.exists() and legacy_clean_dir.is_dir() else root


_WIZARD_MODULE_DEFAULTS: dict[str, dict] = {
    "renamer": {"auto_detect": True},
    "cleanmkv": {"preset": "keep_all", "apply_changes": True, "output_dir_name": "Clean"},
    "nfo": {"template": "detailed", "locale": "en", "auto_metadata": True},
    "torrent": {"private": True},
    "prez": {
        "format": "both",
        "html_template": "magazine_dark",
        "bbcode_template": "detailed",
        "banner_design": "textual",
    },
}


def _build_wizard_module_config(selected_modules: list[str] | set[str]) -> dict:
    return {
        module: defaults
        for module, defaults in _WIZARD_MODULE_DEFAULTS.items()
        if module in selected_modules
    }


def _save_wizard_preset(preset_name: str, preset_config: dict) -> int:
    preset_dir = Path("Presets/Pipeline")
    preset_dir.mkdir(parents=True, exist_ok=True)
    preset_file = preset_dir / f"{preset_name}.yaml"

    if preset_file.exists():
        confirmed = confirm_choice(
            title=tr(
                "pipeline.wizard.overwrite",
                default="Preset '{name}' already exists. Overwrite?",
                name=preset_name,
            ),
            default=False,
        )
        if not confirmed:
            print_info(tr("pipeline.wizard.cancelled", default="Preset creation cancelled"))
            return 0

    try:
        with open(preset_file, "w", encoding="utf-8") as f:
            yaml.dump({preset_name: preset_config}, f, default_flow_style=False, sort_keys=False)

        print_success(
            tr(
                "pipeline.wizard.saved",
                default="Preset saved: {path}",
                path=str(preset_file),
            )
        )
        return 0
    except Exception as exc:
        from framekit.ui.console import print_exception_error

        print_exception_error(
            exc,
            message=tr("pipeline.wizard.save_failed", default="Failed to save preset"),
        )
        return 1


def _create_pipeline_preset_wizard() -> int:
    """Interactive wizard to create a pipeline preset.

    Guides user through all configuration options and saves the preset.
    """
    print_module_banner("Pipeline Preset Wizard")

    console.print()
    console.print(
        tr(
            "pipeline.wizard.intro",
            default="This wizard will guide you through creating a custom pipeline preset.",
        )
    )
    console.print()

    preset_name = text_input(
        title=tr("pipeline.wizard.preset_name", default="Preset name (filename without .yaml)"),
        mandatory=True,
    )

    if not preset_name:
        print_error(tr("pipeline.wizard.name_required", default="Preset name is required"))
        return 1

    display_name = text_input(
        title=tr("pipeline.wizard.display_name", default="Display name"),
        default=preset_name.replace("_", " ").title(),
        mandatory=True,
    )

    description = text_input(
        title=tr("pipeline.wizard.description", default="Description (optional)"),
        mandatory=False,
    )

    module_entries: list[SelectorEntry] = [
        SelectorDivider(tr("pipeline.wizard.modules", default="Select Modules")),
        *[
            SelectorOption(
                value=module,
                label=_module_label(module),
                hint=tr(f"pipeline.wizard.module_{module}_hint", default=f"Enable {module}"),
                selected=True,
            )
            for module in PIPELINE_MODULES
        ],
    ]

    try:
        selected_modules = select_many(
            title=tr("pipeline.wizard.select_modules", default="Choose pipeline modules"),
            entries=module_entries,
            page_size=10,
            minimal_count=1,
        )
    except KeyboardInterrupt:
        print_info(tr("pipeline.wizard.cancelled", default="Preset creation cancelled"))
        return 0

    preset_config: dict = {
        "name": display_name,
        "modules": list(selected_modules),
    }

    if description:
        preset_config["description"] = description

    preset_config.update(_build_wizard_module_config(selected_modules))

    return _save_wizard_preset(preset_name, preset_config)


def _initialize_pipeline(
    path: str | None,
    explain: bool,
    resolver: PathResolver,
) -> tuple[int, Path | None]:
    """Initialize pipeline and validate inputs.

    Args:
        path: Path to release folder
        explain: Whether to show explanation and exit
        resolver: Path resolver instance

    Returns:
        Tuple of (exit_code, root_path). If exit_code is 0 and root_path is None,
        explanation was shown. If exit_code is non-zero, an error occurred.
    """
    print_module_banner("Pipeline")

    if explain:
        console.print(
            Panel(
                _pipeline_explain_text(),
                title=tr("pipeline.explain", default="Pipeline explain"),
                border_style="white",
                expand=True,
            )
        )
        return 0, None

    if not path:
        print_error(
            tr("pipeline.error.no_path", default="Please specify a valid path to a release folder")
        )
        return 1, None

    root = resolver.resolve_start_folder("pipeline", path)
    if not root.exists() or not root.is_dir():
        print_error(
            tr("cleanmkv.error.folder_not_found", default="Folder not found: {folder}", folder=root)
        )
        return 1, None

    return 0, root


def _normalize_pipeline_nfo_template(
    template_value: object | None,
    mode_value: object | None,
) -> str | None:
    if isinstance(mode_value, str):
        legacy_template = _PIPELINE_NFO_TEMPLATE_ALIASES.get(mode_value.strip().lower())
        if legacy_template is not None:
            return legacy_template

    if not isinstance(template_value, str):
        return None

    candidate = template_value.strip()
    if not candidate:
        return None
    return _PIPELINE_NFO_TEMPLATE_ALIASES.get(candidate.lower(), candidate)


def _normalize_pipeline_nfo_mode(mode_value: object | None) -> str | None:
    if not isinstance(mode_value, str):
        return None

    candidate = mode_value.strip().lower()
    if not candidate:
        return None
    if candidate in _PIPELINE_NFO_OUTPUT_MODES:
        return candidate
    if candidate in _PIPELINE_NFO_TEMPLATE_ALIASES:
        return "global"
    return None


def _normalize_pipeline_html_template(template_value: object | None) -> str | None:
    if not isinstance(template_value, str):
        return None

    candidate = template_value.strip()
    if not candidate:
        return None
    if candidate.lower() == "magazine":
        return "magazine_dark"
    return candidate


def _apply_nfo_preset(nfo_preset: dict, mods: dict) -> None:
    if not nfo_preset:
        return
    nfo_cfg = mods.setdefault("nfo", {})
    if "locale" in nfo_preset:
        nfo_cfg["locale"] = nfo_preset["locale"]

    template_name = _normalize_pipeline_nfo_template(
        nfo_preset.get("template"),
        nfo_preset.get("mode"),
    )
    if template_name is not None:
        nfo_cfg["active_template"] = template_name

    output_mode = _normalize_pipeline_nfo_mode(nfo_preset.get("mode"))
    if output_mode is not None:
        nfo_cfg["mode"] = output_mode

    if "auto_metadata" in nfo_preset:
        mods.setdefault("pipeline", {})["with_metadata"] = bool(nfo_preset["auto_metadata"])


def _apply_torrent_preset(torrent_preset: dict, mods: dict) -> None:
    if not torrent_preset:
        return
    torrent_cfg = mods.setdefault("torrent", {})
    for key in ("private", "announce", "comment"):
        if key in torrent_preset:
            torrent_cfg[key] = torrent_preset[key]


def _apply_prez_preset(prez_preset: dict, mods: dict) -> None:
    if not prez_preset:
        return
    prez_cfg = mods.setdefault("prez", {})
    for yaml_key, settings_key in (
        ("format", "format"),
        ("bbcode_template", "bbcode_template"),
        ("mediainfo_mode", "mediainfo_mode"),
        ("preset", "preset"),
        ("banner_design", "banner_design"),
    ):
        if yaml_key in prez_preset:
            prez_cfg[settings_key] = prez_preset[yaml_key]

    normalized_html_template = _normalize_pipeline_html_template(
        prez_preset.get("html_template", "magazine_dark")
    )
    if normalized_html_template is not None:
        prez_cfg["html_template"] = normalized_html_template

    prez_cfg["banner_design"] = str(prez_preset.get("banner_design") or "textual")


def _apply_preset_modules(preset_config: dict, settings: dict) -> None:
    mods = settings.setdefault("modules", {})
    _apply_nfo_preset(preset_config.get("nfo", {}), mods)
    _apply_torrent_preset(preset_config.get("torrent", {}), mods)
    _apply_prez_preset(preset_config.get("prez", {}), mods)


def _load_and_apply_preset(
    pipeline_preset: str | None,
    auto_mode: bool,
    settings: dict,
    enabled_modules: tuple[str, ...] | None,
) -> tuple[dict | None, tuple[str, ...] | None]:
    """Load pipeline preset and apply configuration.

    Args:
        pipeline_preset: Name of preset to load
        auto_mode: Whether in auto mode
        settings: Settings dictionary (modified in place)
        enabled_modules: Currently enabled modules

    Returns:
        Tuple of (preset_config, updated_enabled_modules)
    """
    preset_config = None
    updated_modules = enabled_modules

    if not pipeline_preset:
        return preset_config, updated_modules

    preset_config = _load_pipeline_preset(pipeline_preset)
    if not preset_config:
        print_error(
            tr(
                "pipeline.error.preset_not_found",
                default="Pipeline preset not found: {name}",
                name=pipeline_preset,
            )
        )
        return None, updated_modules

    print_info(
        tr(
            "pipeline.info.using_preset",
            default="Using pipeline preset: {name}",
            name=preset_config.get("name", pipeline_preset),
        )
    )

    if enabled_modules is None and "modules" in preset_config:
        updated_modules = tuple(preset_config["modules"])

    _apply_preset_modules(preset_config, settings)

    return preset_config, updated_modules


def _try_interactive_preset_selection(
    selected_modules: set[str],
    pipeline_preset: str | None,
    preset_config: dict | None,
) -> set[str]:
    if not sys.stdin.isatty() or pipeline_preset or preset_config is not None:
        return selected_modules
    preset_choice = _select_pipeline_preset()
    if not preset_choice or not isinstance(preset_choice, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # Defensive guard against interactive selectors returning non-str
        return selected_modules
    loaded_preset = _load_pipeline_preset(preset_choice)
    if not loaded_preset:
        return selected_modules
    print_info(
        tr(
            "pipeline.info.using_preset",
            default="Using pipeline preset: {name}",
            name=loaded_preset.get("name", preset_choice),
        )
    )
    if "modules" in loaded_preset:
        return set(loaded_preset["modules"])
    return selected_modules


def _resolve_module_selection(
    settings: dict,
    enabled_modules: tuple[str, ...] | None,
    select_modules: bool | None,
    auto_mode: bool,
    pipeline_preset: str | None,
    preset_config: dict | None,
    metadata_enabled: bool = True,
) -> tuple[set[str], bool, bool, bool]:
    """Resolve which modules should be enabled.

    Args:
        settings: Settings dictionary
        enabled_modules: Explicitly enabled modules
        select_modules: Whether to show module selector
        auto_mode: Whether in auto mode
        pipeline_preset: Pipeline preset name
        preset_config: Loaded preset configuration
        metadata_enabled: Whether metadata fetching is enabled

    Returns:
        Tuple of (selected_modules, show_preview, auto_mode_updated, metadata_enabled)
    """
    selected_modules = _resolve_enabled_modules(settings, enabled_modules)
    show_preview = False
    auto_mode_updated = auto_mode

    if not auto_mode:
        selected_modules, show_preview, auto_from_selector, metadata_enabled = (
            _maybe_select_modules(settings, selected_modules, select_modules, metadata_enabled)
        )
        if auto_from_selector:
            auto_mode_updated = True

    if auto_mode_updated:
        selected_modules = _try_interactive_preset_selection(
            selected_modules, pipeline_preset, preset_config
        )

    return selected_modules, show_preview, auto_mode_updated, metadata_enabled


def _show_interactive_preview(
    root: Path,
    release: ReleaseNfoData,
    work_folder: Path,
    output_folder: Path,
    store: SettingsStore,
    settings: dict,
    selected_modules: set[str],
    remove_terms: tuple[str, ...],
    resolved_locale: str,
    resolved_announce: str | None,
    resolved_preset: str,
    metadata_enabled: bool,
) -> tuple[int, Path, Path]:
    module_tuple = tuple(name for name in PIPELINE_MODULES if name in selected_modules)
    preview_data = _gather_preview_data(
        root,
        work_folder,
        store,
        settings,
        module_tuple,
        remove_terms,
        resolved_locale,
    )

    _print_pipeline_preview_comparison(
        root,
        release,
        module_tuple,
        preview_data,
        root=root,
        work_folder=work_folder,
        output_folder=output_folder,
        nfo_locale=resolved_locale,
        announce=resolved_announce,
        preset=resolved_preset,
        metadata_enabled=metadata_enabled,
    )

    from framekit.ui.unified_selector import confirm_choice

    confirmed = confirm_choice(
        title=tr("pipeline.preview.confirm", default="Launch pipeline with these settings?"),
        default=True,
        yes_label=tr("pipeline.preview.launch", default="Launch Pipeline"),
        no_label=tr("pipeline.preview.cancel", default="Cancel"),
    )

    if not confirmed:
        print_info(tr("pipeline.preview.cancelled", default="Pipeline cancelled by user."))
        return 1, work_folder, output_folder

    console.print()
    return 0, work_folder, output_folder


def _show_headless_preview(
    root: Path,
    release: ReleaseNfoData,
    work_folder: Path,
    output_folder: Path,
    settings: dict,
    selected_modules: set[str],
    resolved_locale: str,
    resolved_announce: str | None,
    resolved_preset: str,
    metadata_enabled: bool,
) -> tuple[int, Path, Path]:
    prez_settings = settings.get("modules", {}).get("prez", {})
    module_tuple = tuple(name for name in PIPELINE_MODULES if name in selected_modules)
    _print_pipeline_preview(
        root,
        release,
        module_tuple,
        root=root,
        work_folder=work_folder,
        output_folder=output_folder,
        nfo_locale=resolved_locale,
        announce=resolved_announce,
        preset=resolved_preset,
        metadata_enabled=metadata_enabled,
        html_template=str(prez_settings.get("html_template", "-") or "-"),
        bbcode_template=str(prez_settings.get("bbcode_template", "-") or "-"),
    )
    return 1, work_folder, output_folder


def _handle_preview_and_confirmation(
    should_show_preview: bool,
    preview_only: bool,
    root: Path,
    work_folder: Path,
    output_folder: Path,
    store: SettingsStore,
    settings: dict,
    selected_modules: set[str],
    remove_terms: tuple[str, ...],
    nfo_locale: str | None,
    announce: str | None,
    preset: str | None,
    metadata_enabled: bool,
    dry_run: bool = False,
) -> tuple[int, Path, Path]:
    """Handle preview display and user confirmation.

    Args:
        should_show_preview: Whether to show preview
        preview_only: Whether to exit after preview
        root: Root release folder
        work_folder: Working folder
        output_folder: Output folder
        store: Settings store
        settings: Settings dictionary
        selected_modules: Selected modules
        remove_terms: Terms to remove
        nfo_locale: NFO locale
        announce: Announce URL
        preset: Prez preset
        metadata_enabled: Whether metadata is enabled

    Returns:
        Tuple of (exit_code, updated_work_folder, updated_output_folder).
        Exit code 0 means continue, 1 means user cancelled.
    """
    if not should_show_preview:
        return 0, work_folder, output_folder

    context = PipelineContext(dry_run=dry_run)
    if dry_run:
        print_info(tr("pipeline.dry_run.active", default="Dry-run mode: no files will be written."))
    try:
        release = _ensure_release_context(work_folder, context)
    except Exception:
        release = _ensure_release_context(root, context)
        work_folder = root
        output_folder = _pipeline_output_folder(work_folder, root)

    prez_settings = settings.get("modules", {}).get("prez", {})
    resolved_locale = _resolve_pipeline_locale(settings, nfo_locale)
    resolved_announce = (
        announce
        or settings.get("modules", {}).get("torrent", {}).get("selected_announce")
        or settings.get("modules", {}).get("torrent", {}).get("announce")
    )
    resolved_preset = preset or str(prez_settings.get("preset", "default") or "default")

    if sys.stdin.isatty():
        return _show_interactive_preview(
            root,
            release,
            work_folder,
            output_folder,
            store,
            settings,
            selected_modules,
            remove_terms,
            resolved_locale,
            resolved_announce,
            resolved_preset,
            metadata_enabled,
        )

    if preview_only:
        return _show_headless_preview(
            root,
            release,
            work_folder,
            output_folder,
            settings,
            selected_modules,
            resolved_locale,
            resolved_announce,
            resolved_preset,
            metadata_enabled,
        )

    return 0, work_folder, output_folder


def _should_open_term_picker(
    select_terms: bool | None,
    remove_terms: tuple[str, ...],
) -> bool:
    if select_terms is True:
        return True
    return select_terms is None and bool(sys.stdin.isatty()) and not remove_terms


def _resolve_remove_terms(
    selected_modules: set[str],
    select_terms: bool | None,
    auto_mode: bool,
    root: Path,
    remove_terms: tuple[str, ...],
) -> tuple[int, tuple[str, ...]]:
    """Resolve terms to remove via interactive selector or CLI args.

    Args:
        selected_modules: Selected modules
        select_terms: Whether to show term selector
        auto_mode: Whether in auto mode
        root: Root release folder
        remove_terms: Terms provided via CLI

    Returns:
        Tuple of (exit_code, effective_remove_terms). Exit code 1 means cancelled.
    """
    if "renamer" not in selected_modules or select_terms is False:
        return 0, remove_terms

    from framekit.commands.renamer import (
        _run_term_selector,  # pyright: ignore[reportPrivateUsage]  # Internal helper shared between command modules
    )

    if auto_mode:
        return 0, remove_terms

    should_open_picker = _should_open_term_picker(select_terms, remove_terms)

    if not should_open_picker:
        return 0, remove_terms

    try:
        picker_result = _run_term_selector(root)
    except Exception as exc:
        print_warning(
            tr(
                "renamer.term_selector.failed",
                default="Term picker failed: {message}",
                message=str(exc),
            )
        )
        return 0, remove_terms

    if picker_result is None:
        print_error(
            tr(
                "renamer.term_selector.cancelled",
                default="Term selection cancelled.",
            )
        )
        return 1, remove_terms

    # Merge with existing remove_terms
    seen: set[str] = set()
    merged: list[str] = []
    for term in (*remove_terms, *picker_result):
        key = term.upper()
        if key in seen:
            continue
        seen.add(key)
        merged.append(term)

    return 0, tuple(merged)


# Alias for backward compatibility - now delegates to orchestrator
_execute_pipeline_modules = execute_pipeline_modules


def run_pipeline_command(
    *,
    path: str | None,
    nfo_locale: str | None,
    announce: str | None,
    preset: str | None = None,
    preview: bool = False,
    explain: bool = False,
    dry_run: bool = False,
    with_metadata: bool | None = None,
    remove_terms: tuple[str, ...] = (),
    select_modules: bool | None = None,
    select_templates: bool | None = None,
    select_terms: bool | None = None,
    nfo_mode: str | None = None,
    enabled_modules: tuple[str, ...] | None = None,
    pipeline_preset: str | None = None,
    auto_mode: bool = False,
    skip_renamer: bool = False,
    skip_cleanmkv: bool = False,
    skip_metadata: bool = False,
    skip_nfo: bool = False,
    skip_torrent: bool = False,
    skip_prez: bool = False,
    skip_encode: bool = False,
    skip_screenshot: bool = False,
    skip_seedbox: bool = False,
    skip_upload: bool = False,
    skip_rename_parent: bool = False,
    step_callback: Callable[[str, str], None] | None = None,
    result_callback: Callable[[dict[str, dict]], None] | None = None,
) -> int:
    """Execute the pipeline command with all modules.

    This is the main entry point for the pipeline command. It orchestrates
    the execution of multiple modules (renamer, cleanmkv, nfo, torrent, prez, upload)
    in sequence, with support for presets, previews, and interactive configuration.
    """
    store = SettingsStore()
    settings = store.load()
    resolver = PathResolver(settings)

    # Initialize and validate
    exit_code, root = _initialize_pipeline(path, explain, resolver)
    if exit_code != 0 or root is None:
        return exit_code

    enabled_modules = _apply_skip_flags(
        enabled_modules,
        skip_renamer=skip_renamer,
        skip_cleanmkv=skip_cleanmkv,
        skip_metadata=skip_metadata,
        skip_nfo=skip_nfo,
        skip_torrent=skip_torrent,
        skip_prez=skip_prez,
        skip_encode=skip_encode,
        skip_screenshot=skip_screenshot,
        skip_seedbox=skip_seedbox,
        skip_upload=skip_upload,
        skip_rename_parent=skip_rename_parent,
    )

    # Load and apply preset configuration
    preset_config, enabled_modules = _load_and_apply_preset(
        pipeline_preset, auto_mode, settings, enabled_modules
    )
    if preset_config is None and pipeline_preset:
        return 1  # Preset loading failed

    # Determine metadata settings
    stop_on_error = bool(settings.get("modules", {}).get("pipeline", {}).get("stop_on_error", True))
    metadata_default = bool(
        settings.get("modules", {})
        .get("pipeline", {})
        .get(
            "with_metadata",
            settings.get("metadata", {}).get("enabled_by_default", True),
        )
    )
    metadata_enabled = metadata_default if with_metadata is None else with_metadata

    # Resolve module selection
    selected_modules, show_preview, auto_mode, metadata_enabled = _resolve_module_selection(
        settings,
        enabled_modules,
        select_modules,
        auto_mode,
        pipeline_preset,
        preset_config,
        metadata_enabled,
    )

    settings, metadata_enabled = _maybe_prompt_missing_tmdb_token(
        settings=settings,
        store=store,
        selected_modules=selected_modules,
        metadata_enabled=metadata_enabled,
        auto_mode=auto_mode,
    )

    # Handle preview and confirmation
    work_folder = _next_work_folder(root, settings)
    output_folder = _pipeline_output_folder(work_folder, root)
    should_show_preview = preview or show_preview

    exit_code, work_folder, output_folder = _handle_preview_and_confirmation(
        should_show_preview,
        preview,
        root,
        work_folder,
        output_folder,
        store,
        settings,
        selected_modules,
        remove_terms,
        nfo_locale,
        announce,
        preset,
        metadata_enabled,
        dry_run=dry_run,
    )
    if exit_code != 0:
        return exit_code

    # Resolve terms to remove
    exit_code, effective_remove_terms = _resolve_remove_terms(
        selected_modules, select_terms, auto_mode, root, remove_terms
    )
    if exit_code != 0:
        return exit_code

    # Execute pipeline with all modules
    return execute_pipeline_modules(
        work_folder=work_folder,
        output_folder=output_folder,
        source_root=root,
        selected_modules=selected_modules,
        effective_remove_terms=effective_remove_terms,
        settings=settings,
        nfo_locale=nfo_locale,
        nfo_mode=nfo_mode,
        select_templates=select_templates,
        metadata_enabled=metadata_enabled,
        announce=announce,
        preset=preset,
        stop_on_error=stop_on_error,
        step_callback=step_callback,
        result_callback=result_callback,
        preset_config=preset_config,
        auto_mode=auto_mode,
        dry_run=dry_run,
    )


def _coerce_optional_flags(
    select_modules: bool,
    select_templates: bool,
    select_terms: bool,
    enabled_modules: tuple[str, ...],
) -> tuple[bool | None, bool | None, bool | None, tuple[str, ...] | None]:
    return (
        select_modules or None,
        select_templates or None,
        select_terms or None,
        enabled_modules or None,
    )


def _apply_skip_flags(
    enabled_modules: tuple[str, ...] | None,
    *,
    skip_renamer: bool = False,
    skip_cleanmkv: bool = False,
    skip_metadata: bool = False,
    skip_nfo: bool = False,
    skip_torrent: bool = False,
    skip_prez: bool = False,
    skip_encode: bool = False,
    skip_screenshot: bool = False,
    skip_seedbox: bool = False,
    skip_upload: bool = False,
    skip_rename_parent: bool = False,
    skip_encoder: bool = False,  # legacy alias
) -> tuple[str, ...] | None:
    skip_map = {
        "renamer": skip_renamer,
        "cleanmkv": skip_cleanmkv,
        "metadata": skip_metadata,
        "nfo": skip_nfo,
        "torrent": skip_torrent,
        "prez": skip_prez,
        "encode": skip_encode or skip_encoder,
        "screenshot": skip_screenshot,
        "seedbox": skip_seedbox,
        "upload": skip_upload,
        "rename-parent": skip_rename_parent,
    }
    if not any(skip_map.values()):
        return enabled_modules
    source = enabled_modules or PIPELINE_MODULES_DEFAULT
    return tuple(name for name in source if not skip_map.get(name, False))


@click.command(name="pipeline")
@click.argument("path", type=click.Path(exists=False), required=False)
@click.option("-l", "--nfo-locale", type=str, help="NFO locale (e.g., 'en', 'fr', 'es')")
@click.option("-a", "--announce", type=str, help="Torrent announce URL")
@click.option("--skip-renamer", is_flag=True, help="Skip renamer module")
@click.option("--skip-cleanmkv", is_flag=True, help="Skip cleanmkv module")
@click.option("--skip-metadata", is_flag=True, help="Skip metadata module")
@click.option("--skip-nfo", is_flag=True, help="Skip NFO module")
@click.option("--skip-torrent", is_flag=True, help="Skip torrent module")
@click.option("--skip-prez", is_flag=True, help="Skip prez module")
@click.option("--skip-encode", "--skip-encoder", is_flag=True, help="Skip encode module")
@click.option("--skip-screenshot", is_flag=True, help="Skip screenshot module")
@click.option("--skip-seedbox", is_flag=True, help="Skip seedbox module")
@click.option("--skip-upload", is_flag=True, help="Skip upload module")
@click.option("--skip-rename-parent", is_flag=True, help="Skip rename-parent module")
@click.option("--ren", "opt_renamer", is_flag=True, help="Enable renamer module")
@click.option("--cmk", "opt_cleanmkv", is_flag=True, help="Enable cleanmkv module")
@click.option("--meta", "opt_metadata", is_flag=True, help="Enable metadata module")
@click.option("--nfo", "opt_nfo", is_flag=True, help="Enable NFO module")
@click.option("--tor", "opt_torrent", is_flag=True, help="Enable torrent module")
@click.option("--prez", "opt_prez", is_flag=True, help="Enable prez module")
@click.option("--enc", "opt_encode", is_flag=True, help="Enable encode module")
@click.option("--shot", "opt_screenshot", is_flag=True, help="Enable screenshot module")
@click.option("--seedbox", "opt_seedbox", is_flag=True, help="Enable seedbox module")
@click.option("--up", "opt_upload", is_flag=True, help="Enable upload module")
@click.option("--rp", "opt_rename_parent", is_flag=True, help="Enable rename-parent module")
@click.option(
    "--all", "all_modules", is_flag=True, help="Run all modules without interactive prompt"
)
@click.option("-P", "--preset", type=str, help="Prez preset name")
@click.option("-p", "--preview", is_flag=True, help="Show preview and exit")
@click.option(
    "-d", "--dry-run", "dry_run", is_flag=True, help="Execute pipeline without writing output files"
)
@click.option("-e", "--explain", is_flag=True, help="Show explanation and exit")
@click.option(
    "--with-metadata/--no-metadata", default=None, help="Enable/disable metadata fetching"
)
@click.option("--remove-term", "remove_terms", multiple=True, help="Terms to remove from filenames")
@click.option("-S", "--select-modules", is_flag=True, help="Interactively select modules")
@click.option("--select-templates", is_flag=True, help="Interactively select templates")
@click.option("--select-terms", is_flag=True, help="Interactively select terms to remove")
@click.option(
    "--nfo-mode", type=click.Choice(["global", "per_file", "both"]), help="NFO generation mode"
)
@click.option("--modules", "enabled_modules", multiple=True, help="Explicitly enable modules")
@click.option("--pipeline-preset", type=str, help="Pipeline preset name")
@click.option("--auto", "auto_mode", is_flag=True, help="Run in fully autonomous mode")
@click.option("--batch", is_flag=True, help="Run in batch mode")
@click.option("--batch-auto", is_flag=True, help="Auto-scan parent folder in batch mode")
@click.option("--create-preset", is_flag=True, help="Create a new pipeline preset")
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (-v, -vv, -vvv)",
)
def pipeline_command(
    path: str | None,
    nfo_locale: str | None,
    announce: str | None,
    skip_renamer: bool,
    skip_cleanmkv: bool,
    skip_metadata: bool,
    skip_nfo: bool,
    skip_torrent: bool,
    skip_prez: bool,
    skip_encode: bool,
    skip_screenshot: bool,
    skip_seedbox: bool,
    skip_upload: bool,
    skip_rename_parent: bool,
    opt_renamer: bool,
    opt_cleanmkv: bool,
    opt_metadata: bool,
    opt_nfo: bool,
    opt_torrent: bool,
    opt_prez: bool,
    opt_encode: bool,
    opt_screenshot: bool,
    opt_seedbox: bool,
    opt_upload: bool,
    opt_rename_parent: bool,
    all_modules: bool,
    preset: str | None,
    preview: bool,
    dry_run: bool,
    explain: bool,
    with_metadata: bool | None,
    remove_terms: tuple[str, ...],
    select_modules: bool,
    select_templates: bool,
    select_terms: bool,
    nfo_mode: str | None,
    enabled_modules: tuple[str, ...],
    pipeline_preset: str | None,
    auto_mode: bool,
    batch: bool,
    batch_auto: bool,
    create_preset: bool,
    verbose: int,
) -> None:
    """Execute the complete pipeline workflow."""
    configure_verbosity(verbose)
    if is_verbose():
        logger.info(f"Pipeline execution with verbosity level {verbose}")

    if create_preset:
        sys.exit(_create_pipeline_preset_wizard())

    # Opt-in module resolution.
    # --ren/--cmk/--nfo/... runs only those modules without prompting.
    # --all runs the default module set without prompting.
    opt_in: list[str] = []
    if opt_renamer:
        opt_in.append("renamer")
    if opt_cleanmkv:
        opt_in.append("cleanmkv")
    if opt_metadata:
        opt_in.append("metadata")
    if opt_nfo:
        opt_in.append("nfo")
    if opt_torrent:
        opt_in.append("torrent")
    if opt_prez:
        opt_in.append("prez")
    if opt_encode:
        opt_in.append("encode")
    if opt_screenshot:
        opt_in.append("screenshot")
    if opt_seedbox:
        opt_in.append("seedbox")
    if opt_upload:
        opt_in.append("upload")
    if opt_rename_parent:
        opt_in.append("rename-parent")

    skip_requested = any(
        (
            skip_renamer,
            skip_cleanmkv,
            skip_metadata,
            skip_nfo,
            skip_torrent,
            skip_prez,
            skip_encode,
            skip_screenshot,
            skip_seedbox,
            skip_upload,
            skip_rename_parent,
        )
    )
    sel_tmpl: bool | None = None
    sel_terms: bool | None = None
    if all_modules:
        final_enabled: tuple[str, ...] | None = _apply_skip_flags(
            tuple(PIPELINE_MODULES),
            skip_renamer=skip_renamer,
            skip_cleanmkv=skip_cleanmkv,
            skip_metadata=skip_metadata,
            skip_nfo=skip_nfo,
            skip_torrent=skip_torrent,
            skip_prez=skip_prez,
            skip_encode=skip_encode,
            skip_screenshot=skip_screenshot,
            skip_seedbox=skip_seedbox,
            skip_upload=skip_upload,
            skip_rename_parent=skip_rename_parent,
        )
        final_select: bool | None = False
    elif opt_in:
        final_enabled = _apply_skip_flags(
            tuple(opt_in),
            skip_renamer=skip_renamer,
            skip_cleanmkv=skip_cleanmkv,
            skip_metadata=skip_metadata,
            skip_nfo=skip_nfo,
            skip_torrent=skip_torrent,
            skip_prez=skip_prez,
            skip_encode=skip_encode,
            skip_screenshot=skip_screenshot,
            skip_seedbox=skip_seedbox,
            skip_upload=skip_upload,
            skip_rename_parent=skip_rename_parent,
        )
        final_select = False
    elif skip_requested:
        final_enabled = _apply_skip_flags(
            PIPELINE_MODULES_DEFAULT,
            skip_renamer=skip_renamer,
            skip_cleanmkv=skip_cleanmkv,
            skip_metadata=skip_metadata,
            skip_nfo=skip_nfo,
            skip_torrent=skip_torrent,
            skip_prez=skip_prez,
            skip_encode=skip_encode,
            skip_screenshot=skip_screenshot,
            skip_seedbox=skip_seedbox,
            skip_upload=skip_upload,
            skip_rename_parent=skip_rename_parent,
        )
        final_select = False
    else:
        sel_mod, sel_tmpl, sel_terms, en_mod = _coerce_optional_flags(
            select_modules,
            select_templates,
            select_terms,
            enabled_modules,
        )
        final_enabled = en_mod
        final_select = sel_mod

    if all_modules or opt_in or skip_requested:
        sel_tmpl = select_templates or None
        sel_terms = select_terms or None

    if batch or batch_auto:
        sys.exit(
            run_batch_pipeline(
                path=path,
                nfo_locale=nfo_locale,
                announce=announce,
                preset=preset,
                with_metadata=with_metadata,
                remove_terms=remove_terms,
                select_modules=final_select,
                select_templates=sel_tmpl,
                select_terms=sel_terms,
                nfo_mode=nfo_mode,
                enabled_modules=final_enabled,
                batch_auto=batch_auto,
                pipeline_preset=pipeline_preset,
                auto_mode=auto_mode,
            )
        )

    sys.exit(
        run_pipeline_command(
            path=path,
            nfo_locale=nfo_locale,
            announce=announce,
            preset=preset,
            preview=preview,
            explain=explain,
            dry_run=dry_run,
            with_metadata=with_metadata,
            remove_terms=remove_terms,
            select_modules=final_select,
            select_templates=sel_tmpl,
            select_terms=sel_terms,
            nfo_mode=nfo_mode,
            enabled_modules=final_enabled,
            pipeline_preset=pipeline_preset,
            auto_mode=auto_mode,
            skip_renamer=skip_renamer,
            skip_cleanmkv=skip_cleanmkv,
            skip_metadata=skip_metadata,
            skip_nfo=skip_nfo,
            skip_torrent=skip_torrent,
            skip_prez=skip_prez,
            skip_encode=skip_encode,
            skip_screenshot=skip_screenshot,
            skip_seedbox=skip_seedbox,
            skip_upload=skip_upload,
            skip_rename_parent=skip_rename_parent,
        )
    )


select_many = _select_many  # backwards-compatible patch target for tests
select_one = _select_one  # backwards-compatible patch target for tests
