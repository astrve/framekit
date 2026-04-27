from __future__ import annotations

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


TOOL_BINARIES: dict[str, str] = {
    "mkvmerge": "mkvmerge",
    "mediainfo": "mediainfo",
}


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

        fallback_binary = TOOL_BINARIES.get(tool_name, tool_name)
        found = shutil.which(fallback_binary)
        return found

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
