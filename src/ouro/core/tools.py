from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path

from ouro.core.i18n import tr
from ouro.core.settings import SettingsStore
from ouro.core.subprocess_safe import MissingToolError, SafeSubprocessError, run_safe


@dataclass(slots=True)
class ToolStatus:
    """Tool status."""

    name: str
    configured_path: str | None
    resolved_path: str | None
    available: bool
    version: str | None
    error: str | None = None


TOOL_COMMANDS: dict[str, list[str]] = {
    "mkvmerge": ["--version"],
    "ffmpeg": ["-version"],
    "ffprobe": ["-version"],
    "mediainfo": ["--version"],
}


# Some tools ship multiple binaries — typically a CLI binary and a GUI binary
# (especially on macOS where the GUI version is bundled inside a `.app` package).
# We try CLI-friendly names first to avoid accidentally launching the GUI when
# probing the version (e.g. running `MediaInfo` from `MediaInfo.app/Contents/MacOS`
# would open the GUI on macOS instead of returning a version string).
TOOL_BINARY_CANDIDATES: dict[str, tuple[str, ...]] = {
    "mkvmerge": ("mkvmerge",),
    "ffmpeg": ("ffmpeg",),
    "ffprobe": ("ffprobe",),
    "mediainfo": ("mediainfo", "MediaInfo"),
}


# Installation instructions for each tool by platform
TOOL_INSTALL_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "mkvmerge": {
        "windows": "choco install mkvtoolnix",
        "macos": "brew install mkvtoolnix",
        "linux": "sudo apt install mkvtoolnix",
        "description": "MKVToolNix (mkvmerge) - Matroska container manipulation",
        "url": "https://mkvtoolnix.download/",
    },
    "ffmpeg": {
        "windows": "choco install ffmpeg",
        "macos": "brew install ffmpeg",
        "linux": "sudo apt install ffmpeg",
        "description": "FFmpeg - Video/audio processing",
        "url": "https://ffmpeg.org/download.html",
    },
    "ffprobe": {
        "windows": "choco install ffmpeg",
        "macos": "brew install ffmpeg",
        "linux": "sudo apt install ffmpeg",
        "description": "FFprobe (part of FFmpeg) - Media file analysis",
        "url": "https://ffmpeg.org/download.html",
    },
    "mediainfo": {
        "windows": "choco install mediainfo-cli",
        "macos": "brew install mediainfo",
        "linux": "sudo apt install mediainfo",
        "description": "MediaInfo - Media file technical information",
        "url": "https://mediaarea.net/en/MediaInfo",
    },
}


# Backward-compatible alias kept for any external caller relying on a single
# binary name per tool. Prefer ``TOOL_BINARY_CANDIDATES`` for new code.
TOOL_BINARIES: dict[str, str] = {
    name: candidates[0] for name, candidates in TOOL_BINARY_CANDIDATES.items()
}


def _is_macos_app_bundle(path: str) -> bool:
    """Return True when *path* points inside a macOS ``.app`` bundle.

    Running such a binary typically launches a GUI application rather than a
    CLI process — that's the root cause of the historical ``ouro doctor`` bug
    that opened MediaInfo's window on macOS.
    """
    return ".app/" in path.replace("\\", "/")


def _subprocess_creation_flags() -> int:
    """Avoid spawning a console window on Windows when probing tools."""
    if os.name == "nt":
        # ``CREATE_NO_WINDOW`` exists on Windows; on POSIX we return 0 so the
        # call site can pass it unconditionally.
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _run_version_command(
    binary_path: str, version_args: list[str]
) -> tuple[str | None, str | None]:
    try:
        result = run_safe(
            [binary_path, *version_args],
            timeout=5,
            check=False,
            capture_output=True,
            log_label=f"{Path(binary_path).name} --version",
        )
    except MissingToolError:
        return None, tr("tools.binary_not_found", default="binary not found")
    except SafeSubprocessError as exc:
        if exc.returncode is None:
            return None, tr("tools.version_timeout", default="version command timed out")
        return None, str(exc)
    except OSError as exc:
        return None, str(exc)

    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0 and not output:
        return None, tr(
            "tools.version_failed",
            default="version command failed with exit code {code}",
            code=result.returncode,
        )

    first_line = output.splitlines()[0].strip() if output else None
    return first_line, None


def get_install_instructions(tool_name: str) -> str:
    """Get installation instructions for a tool.

    Args:
        tool_name: Name of the tool (e.g., 'mkvmerge', 'ffmpeg')

    Returns:
        Formatted installation instructions
    """
    import platform

    instructions = TOOL_INSTALL_INSTRUCTIONS.get(tool_name)
    if not instructions:
        return tr(
            "tools.install_generic",
            default="Install {tool} and ensure it's in your PATH",
            tool=tool_name,
        )

    system = platform.system().lower()
    platform_key = "linux"
    if "windows" in system:
        platform_key = "windows"
    elif "darwin" in system:
        platform_key = "macos"

    install_cmd = instructions.get(platform_key, "")
    description = instructions.get("description", tool_name)
    url = instructions.get("url", "")

    parts = [description]
    if install_cmd:
        parts.append(f"Install: {install_cmd}")
    if url:
        parts.append(f"Download: {url}")

    return " | ".join(parts)


class ToolRegistry:
    """Registry of tool."""

    def __init__(self, settings: SettingsStore | None = None) -> None:
        self.settings = settings or SettingsStore()

    def resolve_tool_path(self, tool_name: str) -> str | None:
        """Resolve tool path."""
        configured = self.settings.get(f"tools.{tool_name}")
        if isinstance(configured, str) and configured.strip():
            configured_path = Path(configured.strip()).expanduser()
            if configured_path.exists():
                return str(configured_path.resolve())

        # Try CLI-friendly candidates in order. We deliberately skip macOS
        # ``.app`` bundle paths because invoking the GUI binary they wrap
        # opens a window instead of returning a version string (this is the
        # root cause of the historical ``ouro doctor`` opening MediaInfo bug).
        candidates = TOOL_BINARY_CANDIDATES.get(tool_name, (tool_name,))
        for candidate in candidates:
            found = shutil.which(candidate)
            if found and not _is_macos_app_bundle(found):
                return found

        # As a last resort, accept a ``.app`` bundle path so we at least
        # report the tool as configured — but the version probe below will
        # still skip the version call to avoid launching the GUI.
        for candidate in candidates:
            found = shutil.which(candidate)
            if found:
                return found

        return None

    def get_status(self, tool_name: str) -> ToolStatus:
        """Return the status."""
        configured = self.settings.get(f"tools.{tool_name}")
        configured = configured.strip() if isinstance(configured, str) else ""

        resolved = self.resolve_tool_path(tool_name)
        if not resolved:
            # Provide helpful installation instructions when tool is not found
            install_help = get_install_instructions(tool_name)
            error_msg = tr(
                "tools.not_found_with_help",
                default="not found - {help}",
                help=install_help,
            )
            return ToolStatus(
                name=tool_name,
                configured_path=configured or None,
                resolved_path=None,
                available=False,
                version=None,
                error=error_msg,
            )

        # If the only resolvable binary points inside a macOS ``.app`` bundle,
        # skip the version probe — invoking the GUI executable would launch a
        # window. We still surface the path so the user can install the CLI.
        if _is_macos_app_bundle(resolved):
            install_help = get_install_instructions(tool_name)
            return ToolStatus(
                name=tool_name,
                configured_path=configured or None,
                resolved_path=resolved,
                available=False,
                version=None,
                error=tr(
                    "tools.gui_only_with_help",
                    default="GUI-only binary detected; install CLI version - {help}",
                    help=install_help,
                ),
            )

        version_args = TOOL_COMMANDS.get(tool_name, ["--version"])
        version, error = _run_version_command(resolved, version_args)

        return ToolStatus(
            name=tool_name,
            configured_path=configured or None,
            resolved_path=resolved,
            available=error is None,
            version=version,
            error=error,
        )

    def get_all_statuses(self) -> list[ToolStatus]:
        """Return the all statuses."""
        return [self.get_status(name) for name in TOOL_BINARIES]

    def require_tool(self, tool_name: str) -> str:
        """Require a tool to be available, raising an error with helpful message if not.

        Args:
            tool_name: Name of the tool to require

        Returns:
            Path to the tool executable

        Raises:
            RuntimeError: If tool is not available, with installation instructions
        """
        status = self.get_status(tool_name)
        if not status.available:
            install_help = get_install_instructions(tool_name)
            raise RuntimeError(
                tr(
                    "tools.required_missing",
                    default="{tool} is required but not available. {help}",
                    tool=tool_name,
                    help=install_help,
                )
            )

        if not status.resolved_path:
            raise RuntimeError(
                tr(
                    "tools.no_path",
                    default="{tool} is marked as available but path could not be resolved",
                    tool=tool_name,
                )
            )

        return status.resolved_path
