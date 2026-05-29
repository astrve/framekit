from __future__ import annotations

from typing import Literal

from rich.console import Group
from rich.text import Text
from rich.theme import Theme

from ouro import __version__

# Logo colors (existing)
LOGO_PRIMARY = "#bf945c"
LOGO_ACCENT = "#e2b97d"
LOGO_META = "#cfd5ff"
LOGO_META_ACCENT = "#dfe79e"
LOGO_MODULE = "white"

PROJECT_REPO_LABEL = "github.com/astrve/ouro"
COPYRIGHT_YEARS = "2026"


# Ouro Visual Identity - Color Palette (Based on OURO_VISUAL_IDENTITY_SPEC.md)
class Colors:
    """Ouro color palette - Modern Minimalist Premium."""

    # Primary Brand Colors
    OURO_SLATE_DARK = "#2C3E50"  # Main brand color, headers
    OURO_SLATE_MEDIUM = "#34495E"  # Secondary elements
    OURO_SLATE_LIGHT = "#7F8C8D"  # Muted text, borders
    OURO_ACCENT_PRIMARY = "#5DADE2"  # Links, interactive elements
    OURO_ACCENT_SECONDARY = "#85C1E9"  # Hover states, subtle highlights

    # Status Colors (Semantic)
    SUCCESS_GREEN = "#27AE60"  # Success messages, [OK] indicator
    SUCCESS_GREEN_LIGHT = "#52BE80"  # Success backgrounds
    SUCCESS_GREEN_DARK = "#1E8449"  # Success borders

    WARNING_AMBER = "#F39C12"  # Warning messages, [WARN] indicator
    WARNING_AMBER_LIGHT = "#F8C471"  # Warning backgrounds
    WARNING_AMBER_DARK = "#D68910"  # Warning borders

    ERROR_RED = "#E74C3C"  # Error messages, [ERR] indicator
    ERROR_RED_LIGHT = "#EC7063"  # Error backgrounds
    ERROR_RED_DARK = "#C0392B"  # Error borders

    INFO_BLUE = "#3498DB"  # Info messages, [INFO] indicator
    INFO_BLUE_LIGHT = "#5DADE2"  # Info backgrounds
    INFO_BLUE_DARK = "#2874A6"  # Info borders

    # Neutral Palette
    WHITE = "#FFFFFF"  # Bright text on dark backgrounds
    LIGHT_GRAY = "#BDC3C7"  # Secondary text
    MEDIUM_GRAY = "#95A5A6"  # Muted text, separators
    DARK_GRAY = "#7F8C8D"  # Subtle elements
    CHARCOAL = "#2C3E50"  # Dark text on light backgrounds
    BLACK = "#1C1C1C"  # Terminal background reference

    # Backward compatibility aliases
    PRIMARY = OURO_ACCENT_PRIMARY
    SUCCESS = SUCCESS_GREEN
    WARNING = WARNING_AMBER
    ERROR = ERROR_RED
    INFO = INFO_BLUE
    ACCENT = OURO_ACCENT_PRIMARY
    MUTED = MEDIUM_GRAY
    HIGHLIGHT = OURO_ACCENT_SECONDARY

    # Status colors
    PENDING = MEDIUM_GRAY
    IN_PROGRESS = OURO_ACCENT_PRIMARY
    COMPLETE = SUCCESS_GREEN
    FAILED = ERROR_RED
    SKIPPED = MEDIUM_GRAY

    # Module-specific colors (using new palette)
    RENAMER = OURO_ACCENT_PRIMARY
    CLEANMKV = INFO_BLUE
    NFO = OURO_SLATE_MEDIUM
    PREZ = WARNING_AMBER
    TORRENT = SUCCESS_GREEN
    CHECKSUM = INFO_BLUE_LIGHT
    METADATA = OURO_ACCENT_SECONDARY
    PIPELINE = OURO_ACCENT_PRIMARY


# Ouro Theme for Rich Console
ouro_theme = Theme(
    {
        # Brand Colors
        "ouro.primary": Colors.OURO_SLATE_DARK,
        "ouro.accent": Colors.OURO_ACCENT_PRIMARY,
        "ouro.muted": Colors.OURO_SLATE_LIGHT,
        # Status Colors
        "status.success": f"{Colors.SUCCESS_GREEN} bold",
        "status.warning": f"{Colors.WARNING_AMBER} bold",
        "status.error": f"{Colors.ERROR_RED} bold",
        "status.info": Colors.INFO_BLUE,
        "status.skip": Colors.MEDIUM_GRAY,
        "status.processing": Colors.OURO_ACCENT_PRIMARY,
        "status.done": f"{Colors.SUCCESS_GREEN} bold",
        # Text Styles
        "header.main": f"{Colors.OURO_SLATE_DARK} bold",
        "header.section": f"{Colors.OURO_SLATE_MEDIUM} bold",
        "header.subsection": f"{Colors.OURO_ACCENT_PRIMARY} bold",
        "text.body": "white",
        "text.secondary": Colors.LIGHT_GRAY,
        "text.code": Colors.OURO_ACCENT_SECONDARY,
        # UI Elements
        "separator": Colors.OURO_SLATE_LIGHT,
        "progress.bar": Colors.OURO_ACCENT_PRIMARY,
        "progress.complete": Colors.SUCCESS_GREEN,
    }
)


# Text-Based Status Indicators (replacing icons)
class StatusIndicators:
    """Text-based status indicators for modern minimalist design."""

    OK = "[OK]"
    WARN = "[WARN]"
    ERR = "[ERR]"
    INFO = "[INFO]"
    SKIP = "[SKIP]"
    PROC = "[PROC]"
    DONE = "[DONE]"


# Legacy Icons class (deprecated, kept for backward compatibility)
class Icons:
    """Deprecated: Use StatusIndicators instead."""

    # Status icons (deprecated)
    SUCCESS = "✓"
    ERROR = "✗"
    WARNING = "⚠"
    INFO = "ℹ"
    PENDING = "○"
    IN_PROGRESS = "◐"


# Style helpers
def get_module_color(module: str) -> str:
    """Get the color for a specific module."""
    return getattr(Colors, module.upper(), Colors.PRIMARY)


def format_status(
    status: Literal[
        "success",
        "error",
        "warning",
        "info",
        "pending",
        "in_progress",
        "skip",
        "processing",
        "done",
    ],
) -> str:
    """Format a status with text-based indicator and color.

    Returns formatted status indicator like [OK], [WARN], [ERR], etc.
    """
    indicator_map = {
        "success": StatusIndicators.OK,
        "error": StatusIndicators.ERR,
        "warning": StatusIndicators.WARN,
        "info": StatusIndicators.INFO,
        "pending": StatusIndicators.SKIP,
        "in_progress": StatusIndicators.PROC,
        "skip": StatusIndicators.SKIP,
        "processing": StatusIndicators.PROC,
        "done": StatusIndicators.DONE,
    }
    style_map = {
        "success": "status.success",
        "error": "status.error",
        "warning": "status.warning",
        "info": "status.info",
        "pending": "status.skip",
        "in_progress": "status.processing",
        "skip": "status.skip",
        "processing": "status.processing",
        "done": "status.done",
    }
    indicator = indicator_map.get(status, StatusIndicators.INFO)
    style = style_map.get(status, "status.info")
    return f"[{style}]{indicator}[/{style}]"


OURO_LOGO_LINES = [
    "███████╗██████╗  █████╗ ███╗   ███╗███████╗██╗  ██╗██╗████████╗",
    "██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝██║ ██╔╝██║╚══██╔══╝",
    "█████╗  ██████╔╝███████║██╔████╔██║█████╗  █████╔╝ ██║   ██║",
    "██╔══╝  ██╔══██╗██╔══██║██║╚██╔╝██║██╔══╝  ██╔═██╗ ██║   ██║",
    "██║     ██║  ██║██║  ██║██║ ╚═╝ ██║███████╗██║  ██╗██║   ██║",
    "╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝",
]


def _art_width(lines: list[str]) -> int:
    return max((len(line) for line in lines), default=0)


def _left_padding(text: str, width: int) -> str:
    return " " * max((width - len(text)) // 2, 0)


def build_logo_text() -> Text:
    """Build logo text."""
    text = Text()

    for index, line in enumerate(OURO_LOGO_LINES):
        style = f"bold {LOGO_ACCENT}" if index == 0 else f"bold {LOGO_PRIMARY}"
        text.append(line, style=style)

        if index < len(OURO_LOGO_LINES) - 1:
            text.append("\n")

    return text


def build_meta_text() -> Text:
    """Build meta text."""
    total_width = _art_width(OURO_LOGO_LINES)
    raw_line = f"v {__version__} – © {COPYRIGHT_YEARS} – {PROJECT_REPO_LABEL}"

    text = Text()
    text.append(_left_padding(raw_line, total_width))
    text.append("v ", style=f"bold {LOGO_META}")
    text.append(__version__, style=f"bold {LOGO_META_ACCENT}")
    text.append(" – © ", style=f"bold {LOGO_META}")
    text.append(COPYRIGHT_YEARS, style=f"bold {LOGO_META_ACCENT}")
    text.append(" – ", style=f"bold {LOGO_META}")
    text.append(PROJECT_REPO_LABEL, style=f"bold {LOGO_META}")

    return text


def build_module_text(module_name: str) -> Text:
    """Build module text."""
    total_width = _art_width(OURO_LOGO_LINES)
    label = module_name.strip()

    text = Text()
    text.append(label.center(total_width), style=f"bold {LOGO_MODULE}")

    return text


def build_banner(module_name: str | None = None) -> Group:
    """Build banner."""
    logo = build_logo_text()
    meta = build_meta_text()

    if module_name:
        return Group(logo, meta, build_module_text(module_name))

    return Group(logo, meta)


def print_module_banner(module_name: str | None = None) -> None:
    """Print the Ouro banner with optional module name.

    Suppressed when ``OURO_WEB_JOB=1`` is set in the environment so that
    web-runner subprocesses produce clean output without the ASCII logo header.
    """
    import os

    if os.environ.get("OURO_WEB_JOB"):
        return
    from ouro.ui.console import console

    console.print(build_banner(module_name=module_name))
