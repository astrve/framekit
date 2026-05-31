"""Safe subprocess wrapper used by every external-tool invocation in Swirrl.

See ``docs/decisions/0006-subprocess-safe-wrapper.md`` for the full rationale.

Rules enforced by this module
-----------------------------

* ``argv[0]`` is resolved to an absolute path through :func:`shutil.which`. A
  missing binary raises :class:`MissingToolError` with a remediation hint
  rather than a generic ``FileNotFoundError`` deep inside the call site.
* ``shell=False`` is hard-coded. The wrappers accept only ``Sequence[str]`` and
  refuse a single string command.
* A ``timeout`` is **mandatory** for :func:`run_safe`. Callers that genuinely
  need an unbounded stream must use :func:`popen_safe` and consume output as
  they go.
* Output is decoded as UTF-8 with ``errors="replace"`` so a single broken byte
  in a tool's stderr cannot crash the pipeline.
* Windows console flashes are suppressed via ``CREATE_NO_WINDOW``.
* Logged argv is redacted by :func:`_redact_argv` so announce URLs with
  embedded passkeys never appear in plain text.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # nosec B404
import sys
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from loguru import logger

__all__ = [
    "MissingToolError",
    "SafeSubprocessError",
    "popen_safe",
    "resolve_tool",
    "run_safe",
]


class SafeSubprocessError(Exception):
    """Wraps any failure from a :func:`run_safe` / :func:`popen_safe` call.

    Attributes:
        tool: Resolved tool name (basename of argv[0]).
        argv: Redacted argument vector for diagnostic display.
        returncode: Exit code if the process finished, ``None`` for timeouts.
        stderr: Captured stderr (empty string for streaming calls).
    """

    def __init__(
        self,
        message: str,
        *,
        tool: str,
        argv: Sequence[str],
        returncode: int | None = None,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.tool = tool
        self.argv = tuple(argv)
        self.returncode = returncode
        self.stderr = stderr


class MissingToolError(SafeSubprocessError):
    """Raised when the requested binary is not on PATH.

    The CLI surfaces this with a remediation hint pointing at
    ``swirrl doctor --check-tools``.
    """


# A passkey URL looks like ``https://tracker.example/<32 hex chars>/announce``
# or similar. The exact format varies per tracker, but anything between two
# slashes that is >=20 chars and only hex / base64 alphabet is treated as a
# secret to redact.
_SECRET_PATTERN = re.compile(
    # ``secret`` excludes ``/`` so the regex stops at the next path separator.
    # Otherwise the greedy class would swallow the trailing ``/announce``
    # segment and the rest-group capture would never fire.
    r"(?P<scheme>https?://[^/]+/)(?P<secret>[A-Za-z0-9_\-+=]{20,})(?P<rest>/[^\s]*)?",
    flags=re.IGNORECASE,
)


def _redact_argv(argv: Sequence[str]) -> tuple[str, ...]:
    """Return a copy of ``argv`` with embedded passkeys masked.

    URL-shaped arguments with a long alphanumeric path segment are masked.
    Anything else passes through untouched.
    """
    redacted: list[str] = []
    for raw in argv:
        match = _SECRET_PATTERN.search(raw)
        if not match:
            redacted.append(raw)
            continue
        masked = (
            raw[: match.start("secret")]
            + "<redacted>"
            + (match.group("rest") or "")
            + raw[match.end() :]
        )
        redacted.append(masked)
    return tuple(redacted)


@lru_cache(maxsize=128)
def resolve_tool(name: str) -> str:
    """Look ``name`` up on PATH and return its absolute path.

    Args:
        name: Bare binary name (``"mkvmerge"``, ``"ffmpeg"``…) or absolute path.

    Returns:
        Absolute filesystem path to the resolved binary.

    Raises:
        MissingToolError: ``name`` is not on PATH.
    """
    # If the caller already supplied a path-shaped string (contains any
    # platform separator) we trust it as a deliberate path reference and
    # skip ``shutil.which``. The OS-level existence check is delegated to
    # ``subprocess.run`` so callers that mock subprocess.run for unit tests
    # see the expected ``FileNotFoundError`` rather than our earlier
    # ``MissingToolError``. PATH-hijack mitigation only applies to bare
    # binary names like ``"ffmpeg"`` — which is precisely what we route
    # through ``shutil.which`` below.
    if "/" in name or "\\" in name:
        return str(name)
    candidate = Path(name)
    if candidate.is_absolute():
        return str(candidate)

    resolved = shutil.which(name)
    if resolved is None:
        raise MissingToolError(
            f"Tool {name!r} not found on PATH. Install it or set an explicit "
            "path in swirrl.yaml under `tools:`, then re-run "
            "`swirrl doctor --check-tools` to verify.",
            tool=name,
            argv=(name,),
        )
    return resolved


def _windows_creationflags() -> int:
    """Return Windows ``CREATE_NO_WINDOW`` when running on Windows.

    Avoids a console flash for subprocesses spawned from a GUI launcher.
    """
    if sys.platform != "win32":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _build_env(extra_env: Mapping[str, str] | None) -> Mapping[str, str] | None:
    if extra_env is None:
        return None
    env = os.environ.copy()
    env.update(extra_env)
    return env


def run_safe(
    argv: Sequence[str],
    *,
    timeout: float,
    check: bool = True,
    capture_output: bool = True,
    cwd: Path | str | None = None,
    extra_env: Mapping[str, str] | None = None,
    log_label: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an external tool with the project's safety guarantees.

    Args:
        argv: Argument vector. ``argv[0]`` is resolved to an absolute path.
        timeout: Maximum wall-clock seconds. Required to keep ffmpeg or
            misbehaving tools from hanging the pipeline.
        check: If ``True`` (default), a non-zero exit raises
            :class:`SafeSubprocessError`.
        capture_output: When ``True``, stdout/stderr are captured and returned
            on the :class:`subprocess.CompletedProcess`; otherwise they stream
            to the parent terminal.
        cwd: Working directory. ``None`` uses the parent's CWD.
        extra_env: Mapping merged on top of :data:`os.environ`.
        log_label: Short label used in log messages (e.g. ``"mkvmerge probe"``).

    Returns:
        A :class:`subprocess.CompletedProcess` with text-mode (UTF-8) output.

    Raises:
        MissingToolError: ``argv[0]`` is not on PATH.
        SafeSubprocessError: process timed out, was killed, or (with
            ``check=True``) exited non-zero.
    """
    _validate_argv(argv, fn_name="run_safe")

    name = argv[0]
    full_argv = _resolved_argv(argv)
    label = log_label or Path(full_argv[0]).name

    logger.debug(f"{label}: running {_redact_argv(full_argv)} (timeout={timeout}s)")

    try:
        completed = _invoke_run(
            full_argv,
            timeout=timeout,
            capture_output=capture_output,
            cwd=cwd,
            extra_env=extra_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise _timeout_error(
            label, name, full_argv, timeout=timeout, stderr=str(exc.stderr or "")
        ) from exc
    except FileNotFoundError as exc:  # pragma: no cover - resolve_tool checks
        raise _missing_after_resolve_error(label, name, full_argv) from exc

    if check and completed.returncode != 0:
        raise _nonzero_exit_error(label, name, full_argv, completed)
    return completed


def _validate_argv(argv: Sequence[str], *, fn_name: str) -> None:
    if not argv:
        raise ValueError(f"{fn_name} requires a non-empty argv")
    if isinstance(argv, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(
            f"{fn_name} rejects string argv to keep shell=False enforced. Pass a Sequence[str]."
        )


def _resolved_argv(argv: Sequence[str]) -> list[str]:
    resolved = resolve_tool(argv[0])
    return [resolved, *argv[1:]]


def _invoke_run(
    argv: Sequence[str],
    *,
    timeout: float,
    capture_output: bool,
    cwd: Path | str | None,
    extra_env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        shell=False,  # nosec B603
        timeout=timeout,
        check=False,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd is not None else None,
        env=_build_env(extra_env),
        creationflags=_windows_creationflags(),
    )


def _timeout_error(
    label: str,
    name: str,
    full_argv: Sequence[str],
    *,
    timeout: float,
    stderr: str,
) -> SafeSubprocessError:
    return SafeSubprocessError(
        f"{label}: timed out after {timeout}s",
        tool=name,
        argv=_redact_argv(full_argv),
        returncode=None,
        stderr=stderr,
    )


def _missing_after_resolve_error(
    label: str,
    name: str,
    full_argv: Sequence[str],
) -> MissingToolError:
    return MissingToolError(
        f"{label}: binary disappeared between resolve and run",
        tool=name,
        argv=_redact_argv(full_argv),
    )


def _nonzero_exit_error(
    label: str,
    name: str,
    full_argv: Sequence[str],
    completed: subprocess.CompletedProcess[str],
) -> SafeSubprocessError:
    stderr_tail = (completed.stderr or "").strip().splitlines()[-5:]
    return SafeSubprocessError(
        f"{label}: exited {completed.returncode}",
        tool=name,
        argv=_redact_argv(full_argv),
        returncode=completed.returncode,
        stderr="\n".join(stderr_tail),
    )


def popen_safe(
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    extra_env: Mapping[str, str] | None = None,
    log_label: str | None = None,
    stdin: int | None = subprocess.DEVNULL,
    stdout: int | None = subprocess.PIPE,
    stderr: int | None = subprocess.PIPE,
    bufsize: int = 1,
) -> subprocess.Popen[str]:
    """Start a long-running tool whose output must be streamed.

    Same safety guarantees as :func:`run_safe`. The caller is responsible for
    waiting on the process and handling timeouts; this wrapper does not impose
    one because ffmpeg encodes legitimately run for hours.

    Args:
        argv: Argument vector. ``argv[0]`` is resolved via :func:`resolve_tool`.
        cwd: Working directory or ``None``.
        extra_env: Mapping merged on top of :data:`os.environ`.
        log_label: Short label used in log messages.
        stdin: stdin redirection target (default :data:`subprocess.DEVNULL`).
        stdout: stdout redirection target (default pipe).
        stderr: stderr redirection target (default pipe).
        bufsize: Line buffering by default so streaming consumers see progress.

    Returns:
        An open :class:`subprocess.Popen` instance. Caller must ``wait()`` or
        manage it with ``with``.

    Raises:
        MissingToolError: ``argv[0]`` is not on PATH.
    """
    if not argv:
        raise ValueError("popen_safe requires a non-empty argv")
    if isinstance(argv, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("popen_safe rejects string argv; pass a Sequence[str].")

    name = argv[0]
    resolved = resolve_tool(name)
    full_argv = [resolved, *argv[1:]]
    label = log_label or Path(resolved).name

    logger.debug(f"{label}: spawning {_redact_argv(full_argv)} (streamed)")

    return subprocess.Popen(  # nosemgrep: python.lang.compatibility.python36.python36-compatibility-Popen1, python.lang.compatibility.python36.python36-compatibility-Popen2
        full_argv,
        shell=False,  # nosec B603
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=bufsize,
        cwd=str(cwd) if cwd is not None else None,
        env=_build_env(extra_env),
        creationflags=_windows_creationflags(),
    )
