"""Heuristic suggestion engine for user-facing errors.

Maps recurring error patterns (missing credentials, missing tools, network
failures, schema mismatches, etc.) to short recovery hints. The CLI handler
in :mod:`ouro.__main__` consults this when an exception lacks its own
``suggestions`` tuple, so legacy raise sites still benefit from the new UX
without touching every call site.

The engine is deliberately conservative: only patterns that we are confident
about emit hints. Anything else falls through to the bare error message.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ouro.core.exceptions import (
    OuroConfigError,
    OuroError,
    OuroExternalToolError,
    OuroHttpError,
    OuroMetadataError,
    OuroUserInputError,
)


@dataclass(slots=True, frozen=True)
class _Rule:
    """A single pattern → suggestions mapping."""

    keywords: tuple[str, ...]
    suggestions: tuple[str, ...]
    type_filter: tuple[type[BaseException], ...] = field(default=())

    def matches(self, exc: BaseException, message: str) -> bool:
        if self.type_filter and not isinstance(exc, self.type_filter):
            return False
        haystack = message.lower()
        return any(kw.lower() in haystack for kw in self.keywords)


# Order matters: more specific rules first.
_RULES: tuple[_Rule, ...] = (
    _Rule(
        keywords=("tmdb credentials are missing", "tmdb_read_access_token"),
        suggestions=(
            "Get a v4 read access token at https://www.themoviedb.org/settings/api",
            "Run: ouro metadata --token (paste the JWT-shaped value)",
            "Or export it: OURO_TMDB_READ_ACCESS_TOKEN=eyJ...",
        ),
        type_filter=(OuroMetadataError, OuroConfigError),
    ),
    _Rule(
        keywords=("ssl/tls handshake failed", "certificate verify failed", "self-signed"),
        suggestions=(
            "Verify the system clock is correct (TLS rejects skewed clocks)",
            "Update root certificates: pip install -U certifi",
            "If you are behind a corporate proxy, set the proxy env vars and retry",
        ),
        type_filter=(OuroHttpError,),
    ),
    _Rule(
        keywords=("getaddrinfo failed", "name or service not known", "name resolution"),
        suggestions=(
            "Check the host name in your settings (typo in tracker URL?)",
            "Run: ouro doctor to verify network connectivity",
        ),
        type_filter=(OuroHttpError,),
    ),
    _Rule(
        keywords=("connection refused", "connection reset"),
        suggestions=(
            "Confirm the remote service is reachable (firewall, VPN, downtime?)",
            "Retry — transient connectivity issues happen",
        ),
        type_filter=(OuroHttpError,),
    ),
    _Rule(
        keywords=("mkvmerge", "mediainfo", "ffmpeg", "ffprobe"),
        suggestions=(
            "Install MKVToolNix (mkvmerge) and MediaInfo via your package manager:",
            "  Windows:  choco install mkvtoolnix mediainfo-cli",
            "  macOS:    brew install mkvtoolnix mediainfo",
            "  Linux:    sudo apt install mkvtoolnix mediainfo",
            "Run: ouro doctor to confirm the tools are visible on PATH",
        ),
        type_filter=(OuroExternalToolError,),
    ),
    _Rule(
        keywords=("schema_version", "unsupported ui locale", "unsupported metadata provider"),
        suggestions=(
            "Open ouro.yaml and confirm schema_version matches the installed version",
            "Reset the file with: ouro init --force (backs up nothing — copy yours first)",
            "Run: ouro doctor for a guided diagnosis",
        ),
        type_filter=(OuroConfigError,),
    ),
    _Rule(
        keywords=("vault", "encryption manager", "key file"),
        suggestions=(
            "Enable security: ouro settings set security.enabled true",
            "Re-create the vault: ouro settings security init",
            "Move the token back into the vault: ouro metadata --token",
        ),
        type_filter=(OuroConfigError,),
    ),
    _Rule(
        keywords=("unknown settings key",),
        suggestions=(
            "List valid keys with: ouro settings show",
            "Check the schema in ouro.example.yaml (shipped with the release)",
        ),
        type_filter=(OuroUserInputError, OuroConfigError),
    ),
    _Rule(
        keywords=("permission denied", "icacls", "chmod"),
        suggestions=(
            "Run the command in a terminal launched as the same user that owns the file",
            "On Windows, re-acquire ownership: takeown /F <path> /R",
        ),
    ),
    _Rule(
        keywords=("path outside allowed directories",),
        suggestions=(
            "The strict-mode path validator rejected the path.",
            "Pass an explicit ``allowed_base_dirs=`` or disable strict mode.",
            "See: ouro doctor → Settings → path_validation.",
        ),
    ),
)


def derive_suggestions(exc: BaseException) -> tuple[str, ...]:
    """Return a small bundle of recovery hints for ``exc``.

    If the exception already carries its own ``suggestions`` tuple, that wins
    untouched. Otherwise we walk the rule table and return the first match.
    Returns an empty tuple when nothing fits — callers should treat that as
    "do not render a suggestions block".
    """
    own = getattr(exc, "suggestions", None)
    if isinstance(own, tuple) and own:
        return own
    if isinstance(own, list) and own:
        return tuple(own)

    message = str(exc)
    for rule in _RULES:
        if rule.matches(exc, message):
            return rule.suggestions
    return ()


def did_you_mean(
    candidate: str,
    options: Iterable[str],
    *,
    limit: int = 3,
    cutoff: float = 0.6,
) -> tuple[str, ...]:
    """Return up to ``limit`` close matches for ``candidate`` from ``options``.

    Thin wrapper around ``difflib.get_close_matches`` so callers don't import
    ``difflib`` directly and so we can tune cutoff/limit centrally if needed.
    """
    from difflib import get_close_matches

    matches = get_close_matches(candidate, list(options), n=limit, cutoff=cutoff)
    return tuple(matches)


__all__ = [
    "OuroError",
    "derive_suggestions",
    "did_you_mean",
]
