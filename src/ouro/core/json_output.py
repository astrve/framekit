"""Helpers for ``--json`` output across CLI commands.

A growing number of Ouro subcommands expose ``--json`` so they integrate
cleanly with shell pipelines (``jq``, ``yq``, CI scripts). To keep the JSON
contract consistent across commands, all of them funnel through this module
which:

* Serialises ``Path``, ``datetime``, ``dataclasses`` and ``enum`` values out
  of the box — callers can pass typed objects without pre-flattening.
* Writes to ``sys.stdout`` so the output is pipeable, untouched by Rich's
  ANSI codes (Rich's ``console.print(json.dumps(...))`` would still pass
  the bytes through the theme renderer).
* Uses indent=2 by default so the output is human-eyeballable.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _default(value: Any) -> Any:
    """Fallback encoder for objects ``json`` does not natively know."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, set | frozenset):
        return sorted(value, key=str)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    # Fall back to repr so callers see *something* useful instead of a crash.
    return repr(value)


def emit_json(payload: Any, *, indent: int = 2, sort_keys: bool = False) -> None:
    """Print ``payload`` as JSON on stdout (no Rich formatting).

    Args:
        payload: Anything JSON-serialisable, possibly containing ``Path``,
            ``datetime``, dataclasses, enums or sets. See :func:`_default`
            for the supported coercions.
        indent: Indentation level. Default 2 matches the rest of the project.
        sort_keys: Whether keys should be alphabetised. Default False so
            callers can choose meaningful field order.
    """
    text = json.dumps(
        payload,
        indent=indent,
        ensure_ascii=False,
        sort_keys=sort_keys,
        default=_default,
    )
    sys.stdout.write(text)
    sys.stdout.write("\n")
    sys.stdout.flush()


def json_envelope(
    *,
    status: str = "ok",
    command: str | None = None,
    data: Any | None = None,
    error: str | None = None,
    exit_code: int = 0,
) -> dict[str, Any]:
    """Return the standard envelope wrapping any command's JSON output.

    The envelope shape::

        {
          "status": "ok" | "error" | "skipped",
          "command": "metadata",          # optional: name of the originating cmd
          "exit_code": 0,                 # canonical exit status the CLI would emit
          "data": { ... },                # command-specific payload (optional)
          "error": "..."                  # human-readable error (only on failure)
        }

    Args:
        status: One of ``"ok"``, ``"error"`` or ``"skipped"``.
        command: Originating CLI command name. Useful when the JSON is
            consumed alongside other commands in a pipeline.
        data: The command-specific payload, if any.
        error: Optional error message — only present when ``status="error"``.
        exit_code: The integer exit code the surrounding command would
            return. Lets pipeline consumers branch on success without
            re-parsing the process exit status.
    """
    envelope: dict[str, Any] = {"status": status, "exit_code": exit_code}
    if command is not None:
        envelope["command"] = command
    if data is not None:
        envelope["data"] = data
    if error is not None:
        envelope["error"] = error
    return envelope


__all__ = [
    "emit_json",
    "json_envelope",
]
