"""Opt-out PyPI update check.

Compares the installed ``swirrl-auto`` version against the latest release on
PyPI no more than once per day, and prints a subtle upgrade banner when a
newer version is available.

The check is intentionally lightweight:

* Cached for 24 h in ``~/.cache/swirrl/update_check.json`` (per-user).
* Disabled via ``SWIRRL_DISABLE_UPDATE_CHECK=1`` or by the
  ``general.update_check`` setting once exposed in the YAML.
* Skipped automatically when stdout is not a TTY, when running inside CI
  (``CI=true``), or when the network probe fails — never blocks the command.
* Uses ``httpx`` (already a runtime dependency) with a 2 s timeout. Failures
  swallow silently; the user-facing command is never delayed for an update
  banner.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from loguru import logger

PYPI_URL = "https://pypi.org/pypi/swirrl-auto/json"
CACHE_TTL_SECONDS = 24 * 60 * 60
NETWORK_TIMEOUT_SECONDS = 2.0
DISABLE_ENV_VAR = "SWIRRL_DISABLE_UPDATE_CHECK"


@dataclass(slots=True)
class UpdateInfo:
    """Result of a single update lookup."""

    installed: str
    latest: str
    checked_at: float
    is_stale: bool = False

    @property
    def update_available(self) -> bool:
        """Handle update available."""
        return _is_newer(self.latest, self.installed)


def _cache_path() -> Path:
    from swirrl.core.paths import get_cache_dir

    return get_cache_dir() / "update_check.json"


def _installed_version() -> str | None:
    """Return the installed ``swirrl-auto`` version, or ``None`` when unknown."""
    for dist_name in ("swirrl-auto", "swirrl"):
        try:
            return importlib_metadata.version(dist_name)
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:  # pragma: no cover - defensive
            return None
    return None


def _is_newer(candidate: str, baseline: str) -> bool:
    """Return ``True`` when ``candidate`` is strictly newer than ``baseline``.

    Uses ``packaging.version`` when available (already pulled in transitively
    by setuptools/uv) and falls back to a tuple comparison otherwise.
    """
    try:
        from packaging.version import InvalidVersion, Version

        try:
            return Version(candidate) > Version(baseline)
        except InvalidVersion:
            return False
    except ImportError:  # pragma: no cover - packaging is always installed

        def _tuple(value: str) -> tuple[int, ...]:
            parts: list[int] = []
            for chunk in value.split("."):
                try:
                    parts.append(int(chunk))
                except ValueError:
                    parts.append(0)
            return tuple(parts)

        return _tuple(candidate) > _tuple(baseline)


def _load_cache() -> dict[str, Any] | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_cache(installed: str, latest: str) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "installed": installed,
                    "latest": latest,
                    "checked_at": time.time(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug(f"Could not write update-check cache: {exc}")


def _disabled() -> bool:
    """Skip the check when explicitly disabled or in non-interactive contexts."""
    if os.environ.get(DISABLE_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}:
        return True
    if not sys.stdout.isatty():
        return True
    return False


def _fetch_latest_version() -> str | None:
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx is always installed
        return None

    try:
        with httpx.Client(timeout=NETWORK_TIMEOUT_SECONDS) as client:
            response = client.get(PYPI_URL, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.debug(f"Update check network probe failed: {exc}")
        return None

    info = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        return None
    latest = info.get("version")
    if isinstance(latest, str) and latest.strip():
        return latest.strip()
    return None


def get_update_info(*, use_cache: bool = True) -> UpdateInfo | None:
    """Return cached or freshly fetched update info, or ``None``.

    Returns ``None`` when the installed version cannot be resolved, when the
    network probe fails, or when the check is disabled by env/CI/non-TTY.
    """
    installed = _installed_version()
    if installed is None:
        return None

    if use_cache:
        cached = _load_cache()
        if cached and isinstance(cached, dict):  # pyright: ignore[reportUnnecessaryIsInstance]  # Defensive guard: cache file may have been tampered with
            checked_at = float(cached.get("checked_at") or 0.0)
            age = time.time() - checked_at
            cached_latest = cached.get("latest")
            if age < CACHE_TTL_SECONDS and isinstance(cached_latest, str) and cached_latest:
                return UpdateInfo(
                    installed=installed,
                    latest=cached_latest,
                    checked_at=checked_at,
                    is_stale=False,
                )

    latest = _fetch_latest_version()
    if latest is None:
        return None

    _save_cache(installed, latest)
    return UpdateInfo(installed=installed, latest=latest, checked_at=time.time())


def show_update_banner_if_available() -> None:
    """Print a single-line upgrade banner when a newer release exists.

    Designed to be called once at CLI startup. Cheap when cache is warm
    (no network call). Never raises; always best-effort.
    """
    if _disabled():
        return

    try:
        info = get_update_info(use_cache=True)
    except Exception as exc:  # pragma: no cover - belt and braces
        logger.debug(f"Update check failed: {exc}")
        return

    if info is None or not info.update_available:
        return

    try:
        from swirrl.ui.console import console

        console.print(
            f"[yellow]▲ Swirrl {info.latest} is available "
            f"(installed {info.installed}). Upgrade with:[/yellow] "
            f"[cyan]pip install -U swirrl-auto[/cyan]"
        )
    except Exception:
        # Fallback to a plain stderr line if rich is somehow unavailable.
        sys.stderr.write(
            f"Swirrl {info.latest} available (installed {info.installed}). "
            f"Run: pip install -U swirrl-auto\n"
        )


def start_background_update_check() -> None:
    """Kick off the update check on a daemon thread.

    The check runs concurrently with the user's command so it does not delay
    the foreground action. The result lands in the cache and is shown on the
    *next* invocation. The current invocation prints the banner only when
    the cache is already warm.
    """
    if _disabled():
        return

    cached = _load_cache()
    has_warm_cache = bool(cached and isinstance(cached, dict))  # pyright: ignore[reportUnnecessaryIsInstance]  # Defensive guard: cache file may have been tampered with

    if has_warm_cache:
        show_update_banner_if_available()
        return

    def _runner() -> None:
        try:
            get_update_info(use_cache=False)
        except Exception:  # pragma: no cover - defensive  # nosec B110
            pass

    thread = threading.Thread(
        target=_runner,
        name="swirrl-update-check",
        daemon=True,
    )
    thread.start()
