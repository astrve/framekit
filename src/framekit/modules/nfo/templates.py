from __future__ import annotations

import re

# nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2
from importlib import resources
from pathlib import Path

from jinja2 import FileSystemLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from loguru import logger

from framekit.core.i18n import tr
from framekit.core.paths import (
    get_nfo_templates_dir,
    get_project_nfo_templates_dir,
    get_user_nfo_templates_dir,
)
from framekit.core.settings import resolve_nfo_locale
from framekit.modules.nfo.formatting import (
    format_bit_depth_human,
    format_bitrate_human,
    format_bytes_human,
    format_duration_ms_human,
    format_fps_human,
    format_kbps_human,
    format_percent_human,
)
from framekit.modules.nfo.template_registry import NfoTemplateRecord, NfoTemplateRegistry

PACKAGE_TEMPLATE_ROOT = "framekit.templates.nfo"
LOCALIZED_TEMPLATE_SUFFIXES = frozenset({"en", "fr", "es"})


def _logical_builtin_template_name(file_stem: str) -> str:
    prefix, separator, suffix = file_stem.rpartition(".")
    if separator and suffix in LOCALIZED_TEMPLATE_SUFFIXES:
        return prefix
    return file_stem


def list_builtin_templates() -> list[str]:
    """Handle list builtin templates."""
    root = resources.files(PACKAGE_TEMPLATE_ROOT)
    names = {
        _logical_builtin_template_name(Path(item.name).stem)
        for item in root.iterdir()
        if item.is_file() and item.name.endswith(".jinja2") and not item.name.startswith("_")
    }
    return sorted(names)


def list_user_templates() -> list[str]:
    """Handle list user templates."""
    root = get_nfo_templates_dir()
    if not root.exists():
        return []
    return sorted(item.stem for item in root.glob("*.jinja2"))


def list_all_templates() -> dict[str, list[str]]:
    """Handle list all templates."""
    return {
        "builtin": list_builtin_templates(),
        "user": list_user_templates(),
    }


def resolve_template_path(name: str, *, locale: str | None = None) -> Path:
    """Resolve template path."""
    user_root = get_nfo_templates_dir()
    user_candidate = user_root / f"{name}.jinja2"
    if user_candidate.exists():
        return user_candidate

    builtin_root = resources.files(PACKAGE_TEMPLATE_ROOT)
    normalized_locale = resolve_nfo_locale(locale, ui_locale="en")
    candidates = [
        builtin_root / f"{name}.{normalized_locale}.jinja2",
        builtin_root / f"{name}.en.jinja2",
        builtin_root / f"{name}.jinja2",
    ]

    for candidate in candidates:
        if candidate.is_file():
            with resources.as_file(candidate) as temp_path:
                return Path(temp_path)

    raise ValueError(
        tr("nfo.error.unknown_template", default="Unknown NFO template: {name}", name=name)
    )


def _is_subpath(path: Path, parent: Path) -> bool:
    """Check if path is equal to or a child of parent."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_import_source(source: Path) -> Path:
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(
            tr(
                "nfo.error.template_file_not_found",
                default="Template file not found: {path}",
                path=source,
            )
        )

    if source.is_symlink():
        raise ValueError(
            tr(
                "nfo.error.template_symlink",
                default="Template source path is a symbolic link: {path}",
                path=source,
            )
        )

    if source.suffix.lower() not in {".jinja2", ".j2"}:
        raise ValueError(
            tr("nfo.error.template_file_type", default="Only .jinja2 or .j2 files can be imported.")
        )
    return source.resolve()


def _warn_if_source_outside_safe_directories(resolved_source: Path) -> None:
    home_dir = Path.home().resolve()
    safe_dirs = [
        home_dir,
        get_user_nfo_templates_dir().resolve(),
        get_nfo_templates_dir().resolve(),
    ]
    if any(_is_subpath(resolved_source, safe_dir) for safe_dir in safe_dirs):
        return
    logger.warning(
        "Template source is outside user home and known template directories: {}",
        resolved_source,
    )


def _resolve_storage_target_dir(
    storage_location: str,
    *,
    base_dir: Path | None,
) -> Path:
    if storage_location == "appdata":
        return get_user_nfo_templates_dir()
    if storage_location == "project":
        return get_project_nfo_templates_dir(base_dir=base_dir)
    raise ValueError(
        tr(
            "nfo.error.unsupported_storage_location",
            default="Unsupported storage location: {location}",
            location=storage_location,
        )
    )


def _resolve_unique_template_name(target_dir: Path, display_name: str) -> str:
    base_name = _slugify_template_name(display_name)
    template_name = base_name
    counter = 2
    while (target_dir / f"{template_name}.jinja2").exists():
        template_name = f"{base_name}_{counter}"
        counter += 1
    return template_name


def import_template_file(
    source_path: str,
    import_name: str | None = None,
    *,
    scope: str = "universal",
    storage_location: str = "appdata",
    base_dir: Path | None = None,
) -> NfoTemplateRecord:
    """Handle import template file."""
    source = Path(source_path)
    resolved_source = _validate_import_source(source)
    _warn_if_source_outside_safe_directories(resolved_source)

    display_name = (import_name or source.stem).strip()
    if not display_name:
        raise ValueError(
            tr("nfo.error.template_name_empty", default="Template display name cannot be empty.")
        )

    target_dir = _resolve_storage_target_dir(storage_location, base_dir=base_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    template_name = _resolve_unique_template_name(target_dir, display_name)
    target = target_dir / f"{template_name}.jinja2"

    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    record = NfoTemplateRecord(
        display_name=display_name,
        template_name=template_name,
        source="user",
        scope=scope,
        file_path=str(target.resolve()),
    )
    NfoTemplateRegistry().register(record)
    return record


def _slugify_template_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "template"


def render_template(template_name: str, context: dict, *, locale: str | None = None) -> str:
    """Render template with security sandboxing.

    Uses SandboxedEnvironment to prevent template injection attacks while
    maintaining autoescape=False for NFO format compatibility.

    Args:
        template_name: Name of the template to render
        context: Template context dictionary
        locale: Optional locale for template selection

    Returns:
        Rendered template string

    Raises:
        SecurityError: If template attempts unsafe operations
        TemplateNotFound: If template file doesn't exist
    """
    template_path: Path | None = None

    registry = NfoTemplateRegistry()
    record = registry.find(template_name)
    if record and record.source == "user" and record.file_path:
        candidate = Path(record.file_path)
        if candidate.exists() and candidate.is_file():
            template_path = candidate

    if template_path is None:
        template_path = resolve_template_path(template_name, locale=locale)

    # Use SandboxedEnvironment instead of Environment for security
    # autoescape=False is required for NFO format, but sandbox prevents code execution
    environment = SandboxedEnvironment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=False,  # Required for NFO format, but sandboxed
        trim_blocks=False,
        lstrip_blocks=False,
        undefined=StrictUndefined,
    )

    # Register safe custom filters
    environment.filters["filesize"] = format_bytes_human
    environment.filters["duration_ms"] = format_duration_ms_human
    environment.filters["percent"] = format_percent_human
    environment.filters["bitrate"] = format_bitrate_human
    environment.filters["bitrate_kbps"] = format_kbps_human
    environment.filters["fps"] = format_fps_human
    environment.filters["bitdepth"] = format_bit_depth_human

    template = environment.get_template(template_path.name)
    # SandboxedEnvironment + StrictUndefined are intentionally used here.
    # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    return template.render(**context)
