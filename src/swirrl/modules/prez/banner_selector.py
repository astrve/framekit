"""Banner selector for Prez presentations.

Banner designs are discovered dynamically from the upstream
`feature/banners` branch on GitHub. Results are cached locally so we do
not hit the GitHub API on every invocation. A static fallback list keeps
the selector functional when the network is unavailable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from swirrl.core.i18n import tr
from swirrl.core.paths import get_cache_dir
from swirrl.ui.unified_selector import SelectorDivider, SelectorOption
from swirrl.ui.unified_selector import select_one as _select_one

GITHUB_OWNER = "astrve"
GITHUB_REPO = "swirrl"
BANNERS_BRANCH = "feature/banners"

BANNER_BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{BANNERS_BRANCH}"
BANNER_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents"
TREE_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/{BANNERS_BRANCH}"

# Sections rendered in the BBCode presentation.
BANNER_SECTIONS: tuple[str, ...] = (
    "audio",
    "information",
    "metadata",
    "release",
    "subtitles",
    "synopsis",
    "technical",
)

SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "es", "fr")

# Fallback when GitHub is unreachable and no cache exists.
FALLBACK_DESIGNS: tuple[str, ...] = (
    "abstract_red",
    "astro_gradient",
    "cinema_pink",
    "cinema_purple",
    "cyberpunk",
    "dark-fantasy_blue",
    "diagonal_blue",
    "digital_blue",
    "folder_beige_and_blue",
    "gold-frame_black",
    "gold-frame_green",
    "iron-man_red_and_yellow",
    "large-basic_blue",
    "leaf_green",
    "linear_beige",
    "metal-frame_blue",
    "military_green",
    "minimal_blue",
    "mojave_orange",
    "movie-custom_red",
    "old-label_black",
    "ores_blue_and_yellow",
    "oval_pastel_green",
    "palace_green_and_gold",
    "patterns_green",
    "robotic_grey",
    "robotic_purple",
    "spectral_blue_and_purple",
    "wavy_blue",
    "white-steel_blue",
)

# Cache lifetime in seconds (24h).
CACHE_TTL_SECONDS = 24 * 60 * 60
CACHE_FILE_NAME = "prez_banners_index.json"
CACHE_SCHEMA_VERSION = 2
HTTP_TIMEOUT = 6.0
_LAST_CATALOG_STATUS = "unknown"
_LAST_CATALOG_DURATION = 0.0


def _cache_path() -> Path:
    return get_cache_dir() / CACHE_FILE_NAME


def _set_catalog_metrics(status: str, started: float) -> None:
    global _LAST_CATALOG_STATUS, _LAST_CATALOG_DURATION
    _LAST_CATALOG_STATUS = status
    _LAST_CATALOG_DURATION = max(time.perf_counter() - started, 0.0)


def _cache_looks_usable(data: dict[str, Any]) -> bool:
    if data.get("schema_version") != CACHE_SCHEMA_VERSION:
        return False
    if data.get("branch") != BANNERS_BRANCH:
        return False
    designs = data.get("designs")
    if not isinstance(designs, dict):
        return False
    return len(designs) >= len(FALLBACK_DESIGNS)


def _load_cache_payload() -> dict[str, Any] | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _load_cache() -> dict[str, Any] | None:
    data = _load_cache_payload()
    if data is None:
        return None
    if not _cache_looks_usable(data):
        return None
    fetched_at = data.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return None
    if (time.time() - float(fetched_at)) > CACHE_TTL_SECONDS:
        return None
    return data


def _save_cache(designs: dict[str, dict[str, list[str]]]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "branch": BANNERS_BRANCH,
            "fetched_at": time.time(),
            "designs": designs,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def _github_list(path: str) -> list[dict[str, Any]] | None:
    """List a GitHub Contents API path on the banners branch.

    Returns None on any HTTP / network error so callers can degrade.
    """
    import httpx  # local import keeps prez startup fast

    url = f"{BANNER_API_URL}/{path}" if path else BANNER_API_URL
    try:
        response = httpx.get(
            url,
            params={"ref": BANNERS_BRANCH},
            timeout=HTTP_TIMEOUT,
            headers={"Accept": "application/vnd.github+json"},
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    return data


def _fetch_remote_index() -> dict[str, dict[str, list[str]]] | None:
    """Fetch the full design → language → sections index from GitHub.

    Returns None if the root listing cannot be retrieved.
    """
    from_tree = _fetch_remote_index_from_tree()
    if from_tree:
        return from_tree

    root = _github_list("")
    if root is None:
        return None

    designs: dict[str, dict[str, list[str]]] = {}
    for design_name in _iter_design_names(root):
        languages = _fetch_design_languages(design_name)
        if languages:
            designs[design_name] = languages
    return designs or None


def _fetch_remote_index_from_tree() -> dict[str, dict[str, list[str]]] | None:
    import httpx  # local import keeps prez startup fast

    try:
        response = httpx.get(
            TREE_API_URL,
            params={"recursive": 1},
            timeout=HTTP_TIMEOUT,
            headers={"Accept": "application/vnd.github+json"},
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    tree = payload.get("tree")
    if not isinstance(tree, list):
        return None

    designs: dict[str, dict[str, set[str]]] = {}
    for item in tree:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "blob":
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.endswith(".png"):
            continue
        parts = path.split("/")
        if len(parts) != 3:
            continue
        design, language, filename = parts
        if language not in SUPPORTED_LANGUAGES:
            continue
        if design.startswith((".", "_")):
            continue
        section = filename[:-4]
        if section not in BANNER_SECTIONS:
            continue
        by_language = designs.setdefault(design, {})
        by_language.setdefault(language, set()).add(section)

    normalized: dict[str, dict[str, list[str]]] = {}
    for design, by_language in designs.items():
        normalized[design] = {
            language: sorted(sections) for language, sections in by_language.items() if sections
        }
    return normalized or None


def _iter_design_names(entries: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for entry in entries:
        if entry.get("type") != "dir":
            continue
        name = entry.get("name")
        if isinstance(name, str) and not name.startswith((".", "_")):
            names.append(name)
    return names


def _fetch_design_languages(design_name: str) -> dict[str, list[str]]:
    languages: dict[str, list[str]] = {}
    for language in _iter_supported_languages(_github_list(design_name) or []):
        sections = _fetch_design_sections(design_name, language)
        if sections:
            languages[language] = sections
    return languages


def _iter_supported_languages(entries: list[dict[str, Any]]) -> list[str]:
    languages: list[str] = []
    for entry in entries:
        if entry.get("type") != "dir":
            continue
        name = entry.get("name")
        if isinstance(name, str) and name in SUPPORTED_LANGUAGES:
            languages.append(name)
    return languages


def _fetch_design_sections(design_name: str, language: str) -> list[str]:
    section_entries = _github_list(f"{design_name}/{language}") or []
    sections: list[str] = []
    for file_entry in section_entries:
        if file_entry.get("type") != "file":
            continue
        file_name = file_entry.get("name", "")
        if isinstance(file_name, str) and file_name.endswith(".png"):
            sections.append(file_name[:-4])
    return sorted(sections)


def get_banner_index(*, refresh: bool = False) -> dict[str, dict[str, list[str]]]:
    """Return mapping `design -> language -> [sections]`.

    Sources, in order:
      1. Fresh GitHub fetch (if `refresh=True` or cache stale).
      2. Cached payload.
      3. Static fallback (every design assumed to expose all sections in all
         supported languages).
    """
    started = time.perf_counter()
    stale_cache: dict[str, Any] | None = None
    if not refresh:
        cached = _load_cache()
        if cached is not None:
            _set_catalog_metrics("cache_hit", started)
            return cached["designs"]
        payload = _load_cache_payload()
        if payload is not None and _cache_looks_usable(payload):
            stale_cache = payload

    remote = _fetch_remote_index()
    if remote:
        _save_cache(remote)
        _set_catalog_metrics("remote_refresh", started)
        return remote

    if stale_cache is not None:
        _set_catalog_metrics("cache_stale", started)
        return stale_cache["designs"]

    # Last resort: fallback list (no remote and no cache).
    fallback: dict[str, dict[str, list[str]]] = {
        design: {lang: list(BANNER_SECTIONS) for lang in SUPPORTED_LANGUAGES}
        for design in FALLBACK_DESIGNS
    }
    _set_catalog_metrics("fallback", started)
    return fallback


def _parse_design_name(design: str) -> tuple[str, str | None]:
    """Split `{suite}_{color}` → (suite, color). Legacy single-name → (name, None)."""
    parts = design.rsplit("_", 1)
    if len(parts) == 2 and parts[1]:
        return parts[0], parts[1]
    return design, None


def _format_design_label(design: str) -> str:
    """Return display label: 'Suite Name - (Color)' or 'Suite Name'."""
    suite, color = _parse_design_name(design)
    suite_label = suite.replace("-", " ").title()
    if color:
        color_label = color.replace("-", " ").title()
        return f"{suite_label} - ({color_label})"
    return suite_label


def get_available_designs(language: str) -> list[str]:
    """Return the design names that have at least one banner for `language`."""
    index = get_banner_index()
    return sorted(design for design, langs in index.items() if langs.get(language))


def normalize_banner_language(locale: str | None) -> str:
    """Map a locale code (e.g. `fr-FR`) to a supported banner language."""
    if not locale:
        return "en"
    lang = locale.split("-")[0].lower()
    return lang if lang in SUPPORTED_LANGUAGES else "en"


def get_banner_url(design: str, language: str, section: str) -> str:
    """Build the raw GitHub URL for a given banner.

    Returns an empty string for the "textual" (no-banner) design or when the
    section is missing on the remote.
    """
    if not design or design == "textual":
        return ""
    index = get_banner_index()
    available_sections = index.get(design, {}).get(language, [])
    if available_sections and section not in available_sections:
        return ""
    return f"{BANNER_BASE_URL}/{design}/{language}/{section}.png"


def build_banner_urls(design: str | None, language: str) -> dict[str, str]:
    """Return `{section: url}` for the standard prez sections.

    Missing sections (or "textual"/empty design) yield empty strings, which
    `PrezBuildOptions` already treats as "no banner for this section".
    """
    return {
        section: get_banner_url(design or "textual", language, section)
        for section in BANNER_SECTIONS
    }


def select_banner_design(
    language: str,
    current_design: str | None = None,
    banners_path: Path | None = None,  # legacy, unused — kept for compat
    default_textual: bool = False,
) -> str | None:
    """Interactive banner design selector.

    `language` must be one of `SUPPORTED_LANGUAGES`. Returns the selected
    design name, `"textual"` for the no-banner option, or `current_design`
    if the user cancels.
    """
    from rich.live import Live
    from rich.spinner import Spinner

    from swirrl.ui.console import console, print_info
    from swirrl.ui.unified_selector import confirm_choice

    _ = banners_path  # legacy parameter kept for backward compatibility

    # Ask user if they want to fetch banner images
    fetch_banners = confirm_choice(
        title=tr(
            "prez.banner.fetch_prompt",
            default="Do you want to fetch banner images from the online catalog?",
        ),
        default=not default_textual,
        yes_label=tr("common.yes", default="Yes"),
        no_label=tr("prez.banner.no_use_textual", default="No (Use text-only)"),
    )

    if fetch_banners is None:
        return current_design

    if not fetch_banners:
        # User chose not to fetch banners, return textual
        return "textual"

    # Show loading animation while fetching banners
    spinner = Spinner(
        "dots",
        text=tr(
            "prez.banner.fetching",
            default="Fetching banner catalog from GitHub...",
        ),
    )

    with Live(spinner, console=console, transient=True):
        index = get_banner_index()
        available = sorted(design for design, langs in index.items() if langs.get(language))

    if available:
        print_info(
            tr(
                "prez.banner.fetch_success",
                default="✓ Banner catalog loaded successfully ({count} designs available)",
                count=len(available),
            )
        )
        status_map = {
            "cache_hit": "cache hit",
            "cache_stale": "cache stale (offline fallback)",
            "remote_refresh": "cache miss/stale -> refreshed online",
            "fallback": "offline fallback list",
        }
        print_info(
            tr(
                "prez.banner.fetch_source",
                default="Source: {source} ({duration:.2f}s)",
                source=status_map.get(_LAST_CATALOG_STATUS, _LAST_CATALOG_STATUS),
                duration=_LAST_CATALOG_DURATION,
            )
        )
    else:
        print_info(
            tr(
                "prez.banner.fetch_fallback",
                default="Using fallback banner list (network unavailable)",
            )
        )

    entries: list[SelectorOption | SelectorDivider] = []

    entries.append(SelectorDivider(tr("prez.banner.no_banner_section", default="No Banner")))
    entries.append(
        SelectorOption(
            value="textual",
            label=tr("prez.banner.textual", default="Textual (No Banner)"),
            hint=tr(
                "prez.banner.textual_hint",
                default="Use text-only section headers",
            ),
            selected=(current_design == "textual" or current_design is None),
        )
    )

    if available:
        current_suite: str | None = None
        for design in available:
            suite, _color = _parse_design_name(design)
            if suite != current_suite:
                current_suite = suite
                entries.append(SelectorDivider(suite.replace("-", " ").title()))
            entries.append(
                SelectorOption(
                    value=design,
                    label=_format_design_label(design),
                    hint=tr(
                        f"prez.banner.design.{design}",
                        default=f"{design} banner design",
                    ),
                    selected=(current_design == design),
                )
            )

    try:
        result = select_one(
            title=tr(
                "prez.banner.selector_title",
                default="Banner Design Selector",
            ),
            entries=entries,
            page_size=12,
        )
        return str(result) if result else current_design
    except KeyboardInterrupt:
        return current_design


def get_banner_path(
    design: str,
    language: str,
    section: str,
    banners_path: Path | None = None,
) -> Path | None:
    """Legacy helper for local filesystem banner lookup.

    Local filesystem lookup is no longer the source of truth — banners live on
    GitHub. Kept for backward compatibility: returns a path only if the caller
    still ships banners locally.
    """
    if design == "textual" or not design:
        return None
    if banners_path is None:
        banners_path = Path("banners")
    candidate = banners_path / design / language / f"{section}.png"
    return candidate if candidate.exists() else None


# Backward-compat alias: code paths that imported the old constant.
BANNER_DESIGNS = FALLBACK_DESIGNS


select_one = _select_one  # backwards-compatible patch target for tests
