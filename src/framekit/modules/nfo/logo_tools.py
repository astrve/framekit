from __future__ import annotations

import re
from pathlib import Path

try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename fallback when pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(filename: str, replacement_text: str = "_") -> str:
        """
        Sanitize a filename by replacing characters illegal on most filesystems.
        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


from framekit.core.i18n import tr
from framekit.core.paths import get_user_nfo_logos_dir
from framekit.modules.nfo.logo_registry import NfoLogoRecord, NfoLogoRegistry

ALLOWED_LOGO_SUFFIXES = {".txt", ".nfo", ".asc"}


def _slugify_logo_name(value: str) -> str:
    value = sanitize_filename(value.strip().lower(), replacement_text="_")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "logo"


def import_logo_file(source_path: str, logo_name: str | None = None) -> NfoLogoRecord:
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(
            tr("nfo.error.logo_file_not_found", default="Logo file not found: {path}", path=source)
        )

    if source.suffix.lower() not in ALLOWED_LOGO_SUFFIXES:
        raise ValueError(
            tr(
                "nfo.error.logo_file_type",
                default="Only .txt, .nfo or .asc logo files can be imported.",
            )
        )

    display_name = (logo_name or source.stem).strip()
    if not display_name:
        raise ValueError(
            tr("nfo.error.logo_name_empty", default="Logo display name cannot be empty.")
        )

    internal_name = _slugify_logo_name(display_name)
    target_dir = get_user_nfo_logos_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / f"{internal_name}.txt"
    counter = 2
    while target.exists():
        internal_name = f"{_slugify_logo_name(display_name)}_{counter}"
        target = target_dir / f"{internal_name}.txt"
        counter += 1

    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    record = NfoLogoRecord(
        display_name=display_name,
        logo_name=internal_name,
        file_path=str(target.resolve()),
    )
    NfoLogoRegistry().register(record)
    return record
