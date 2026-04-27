from __future__ import annotations

from rich.console import Group
from rich.text import Text

from framekit import __version__
from framekit.ui.console import console

LOGO_PRIMARY = "#bf945c"
LOGO_ACCENT = "#e2b97d"
LOGO_META = "#cfd5ff"
LOGO_META_ACCENT = "#dfe79e"
LOGO_MODULE = "white"

PROJECT_REPO_LABEL = "github.com/astrve/framekit"
COPYRIGHT_YEARS = "2026"

FRAMEKIT_LOGO_LINES = [
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
    text = Text()

    for index, line in enumerate(FRAMEKIT_LOGO_LINES):
        style = f"bold {LOGO_ACCENT}" if index == 0 else f"bold {LOGO_PRIMARY}"
        text.append(line, style=style)

        if index < len(FRAMEKIT_LOGO_LINES) - 1:
            text.append("\n")

    return text


def build_meta_text() -> Text:
    total_width = _art_width(FRAMEKIT_LOGO_LINES)
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
    total_width = _art_width(FRAMEKIT_LOGO_LINES)
    label = module_name.strip()

    text = Text()
    text.append(label.center(total_width), style=f"bold {LOGO_MODULE}")

    return text


def build_banner(module_name: str | None = None) -> Group:
    """
    Build the Framekit CLI banner.

    The banner intentionally keeps the visual identity compact:

    - ASCII logo;
    - visible plain-text version / copyright / repository line;
    - optional module name below the metadata line.

    The repository is displayed as plain text instead of relying on terminal
    hyperlink support, so it remains visible in every terminal.
    """
    logo = build_logo_text()
    meta = build_meta_text()

    if module_name:
        return Group(logo, meta, build_module_text(module_name))

    return Group(logo, meta)


def print_module_banner(module_name: str | None = None) -> None:
    console.print(build_banner(module_name=module_name))