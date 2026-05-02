from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from framekit.core.i18n import tr
from framekit.core.settings import SettingsStore


@dataclass(slots=True)
class ToolStatus:
    name: str
    configured_path: str | None
    resolved_path: str | None
    available: bool
    version: str | None
    error: str | None = None


TOOL_COMMANDS: dict[str, list[str]] = {
    "mkvmerge": ["--version"],
    "mediainfo": ["--version"],
}


# Some tools ship multiple binaries — typically a CLI binary and a GUI binary
# (especially on macOS where the GUI version is bundled inside a `.app` package).
# We try CLI-friendly names first to avoid accidentally launching the GUI when
# probing the version (e.g. running `MediaInfo` from `MediaInfo.app/Contents/MacOS`
# would open the GUI on macOS instead of returning a version string).
TOOL_BINARY_CANDIDATES: dict[str, tuple[str, ...]] = {
    "mkvmerge": ("mkvmerge",),
    "mediainfo": ("mediainfo", "mediainfo-cli", "MediaInfoCLI"),
}


# Backward-compatible alias kept for any external caller relying on a single
# binary name per tool. Prefer ``TOOL_BINARY_CANDIDATES`` for new code.
TOOL_BINARIES: dict[str, str] = {
    name: candidates[0] for name, candidates in TOOL_BINARY_CANDIDATES.items()
}


def _is_macos_app_bundle(path: str) -> bool:
    """Return True when *path* points inside a macOS ``.app`` bundle.

    Running such a binary typically launches a GUI application rather than a
    CLI process — that's the root cause of the historical ``fk doctor`` bug
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
        result = subprocess.run(
            [binary_path, *version_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=_subprocess_creation_flags(),
        )
    except FileNotFoundError:
        return None, tr("tools.binary_not_found", default="binary not found")
    except subprocess.TimeoutExpired:
        return None, tr("tools.version_timeout", default="version command timed out")
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


class ToolRegistry:
    def __init__(self, settings: SettingsStore | None = None) -> None:
        self.settings = settings or SettingsStore()

    def resolve_tool_path(self, tool_name: str) -> str | None:
        configured = self.settings.get(f"tools.{tool_name}")
        if isinstance(configured, str) and configured.strip():
            configured_path = Path(configured.strip()).expanduser()
            if configured_path.exists():
                return str(configured_path.resolve())

        # Try CLI-friendly candidates in order. We deliberately skip macOS
        # ``.app`` bundle paths because invoking the GUI binary they wrap
        # opens a window instead of returning a version string (this is the
        # root cause of the historical ``fk doctor`` opening MediaInfo bug).
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
        configured = self.settings.get(f"tools.{tool_name}")
        configured = configured.strip() if isinstance(configured, str) else ""

        resolved = self.resolve_tool_path(tool_name)
        if not resolved:
            return ToolStatus(
                name=tool_name,
                configured_path=configured or None,
                resolved_path=None,
                available=False,
                version=None,
                error=tr("tools.not_found", default="not found"),
            )

        # If the only resolvable binary points inside a macOS ``.app`` bundle,
        # skip the version probe — invoking the GUI executable would launch a
        # window. We still surface the path so the user can install the CLI.
        if _is_macos_app_bundle(resolved):
            return ToolStatus(
                name=tool_name,
                configured_path=configured or None,
                resolved_path=resolved,
                available=False,
                version=None,
                error=tr(
                    "tools.gui_only",
                    default="GUI-only binary detected; install the CLI version of {tool}.",
                    tool=tool_name,
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
        return [self.get_status(name) for name in TOOL_BINARIES]
