"""``framekit seedbox`` — multi-seedbox transfer via rclone.

Supports multiple named seedbox profiles.  Credentials live in rclone's
own config; metadata (paths, limits, etc.) is stored in framekit.yaml.
Upload history is written to ~/.config/framekit/seedbox/history.ndjson.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.table import Table

from framekit.core.cli_helpers import join_path_parts
from framekit.core.i18n import tr
from framekit.core.paths import get_config_dir
from framekit.core.release_payload import find_release_payload, find_release_payloads
from framekit.core.settings import SettingsStore
from framekit.core.subprocess_safe import run_safe
from framekit.ui.branding import print_module_banner
from framekit.ui.click_helper import click
from framekit.ui.console import console, print_error, print_info, print_success, print_warning

RCLONE_TRANSFER_TIMEOUT_SECONDS = 24 * 60 * 60
POST_UPLOAD_TIMEOUT_SECONDS = 5 * 60

# ── History ──────────────────────────────────────────────────────────────────


def _history_path() -> Path:
    path = get_config_dir() / "seedbox"
    path.mkdir(parents=True, exist_ok=True)
    return path / "history.ndjson"


def _append_history(entry: dict[str, Any]) -> None:
    path = _history_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_history(seedbox_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if seedbox_name and entry.get("seedbox") != seedbox_name:
                continue
            entries.append(entry)
    return entries[-limit:]


# ── Config helpers ────────────────────────────────────────────────────────────


def _get_seedbox_cfg(settings: dict) -> dict:
    return settings.get("seedbox", {})


def _list_seedboxes(settings: dict) -> list[dict]:
    raw = _get_seedbox_cfg(settings).get("seedboxes", [])
    return list(raw) if isinstance(raw, list) else []


def _find_seedbox(settings: dict, name: str) -> dict | None:
    for sb in _list_seedboxes(settings):
        if sb.get("name") == name:
            return sb
    return None


def _active_profile_name() -> str | None:
    try:
        from framekit.core.settings.profiles import get_active_profile

        active = get_active_profile()
    except Exception:
        return None
    if not active:
        return None
    profile_name = str(active).strip()
    return profile_name or None


def _default_by_profile(settings: dict) -> dict[str, str]:
    cfg = _get_seedbox_cfg(settings)
    raw = cfg.get("default_by_profile", {})
    if not isinstance(raw, dict):
        return {}
    return {
        str(profile).strip(): str(seedbox_name).strip()
        for profile, seedbox_name in raw.items()
        if str(profile).strip() and str(seedbox_name).strip()
    }


def _configured_default_seedbox_name(settings: dict, *, profile_name: str | None = None) -> str:
    profile_defaults = _default_by_profile(settings)
    if profile_name and profile_name in profile_defaults:
        return profile_defaults[profile_name]

    cfg = _get_seedbox_cfg(settings)
    default_name = str(cfg.get("default", "") or "").strip()
    if default_name:
        return default_name

    # Fall back to first configured seedbox
    seedboxes = _list_seedboxes(settings)
    return str(seedboxes[0].get("name", "") or "").strip() if seedboxes else ""


def _get_default_seedbox(settings: dict, *, profile_name: str | None = None) -> dict | None:
    preferred_name = _configured_default_seedbox_name(settings, profile_name=profile_name)
    if preferred_name:
        sb = _find_seedbox(settings, preferred_name)
        if sb:
            return sb

    # Profile mapping can become stale if a seedbox was removed.
    cfg_default = str(_get_seedbox_cfg(settings).get("default", "") or "").strip()
    if cfg_default and cfg_default != preferred_name:
        sb = _find_seedbox(settings, cfg_default)
        if sb:
            return sb

    seedboxes = _list_seedboxes(settings)
    return seedboxes[0] if seedboxes else None


def _resolve_seedbox(settings: dict, name: str | None) -> dict | None:
    if name:
        sb = _find_seedbox(settings, name)
        if not sb:
            print_error(
                tr(
                    "seedbox.error.not_found",
                    default="Seedbox '{name}' not configured. Use 'fk seedbox list' to see available seedboxes.",
                    name=name,
                )
            )
        return sb
    active_profile = _active_profile_name()
    profile_default = ""
    if active_profile:
        profile_default = _default_by_profile(settings).get(active_profile, "")
    if profile_default and not _find_seedbox(settings, profile_default):
        print_warning(
            f"Active profile '{active_profile}' maps to unknown seedbox '{profile_default}'. Falling back."
        )

    sb = _get_default_seedbox(settings, profile_name=active_profile)
    if not sb:
        print_error(
            tr(
                "seedbox.error.no_seedbox",
                default="No seedbox configured. Use 'fk seedbox add' to register one.",
            )
        )
    elif active_profile and profile_default and sb.get("name") == profile_default:
        print_info(f"Using seedbox '{profile_default}' mapped to active profile '{active_profile}'.")
    return sb


def _save_seedboxes(
    store: SettingsStore,
    seedboxes: list[dict],
    default: str | None = None,
    *,
    default_by_profile: dict[str, str] | None = None,
    max_concurrent_uploads: int | None = None,
) -> None:
    data = store.load()
    if "seedbox" not in data:
        data["seedbox"] = {}
    data["seedbox"]["seedboxes"] = seedboxes
    if default is not None:
        data["seedbox"]["default"] = default
    if default_by_profile is not None:
        data["seedbox"]["default_by_profile"] = default_by_profile
    if max_concurrent_uploads is not None:
        data["seedbox"]["max_concurrent_uploads"] = max(1, int(max_concurrent_uploads))
    store.save(data)


# ── rclone helpers ────────────────────────────────────────────────────────────


def _find_rclone() -> str | None:
    return shutil.which("rclone")


def _list_rclone_remotes(rclone_path: str) -> tuple[set[str], str | None]:
    try:
        result = run_safe(
            [rclone_path, "listremotes"],
            capture_output=True,
            timeout=15,
            check=False,
            log_label="rclone listremotes",
        )
    except Exception as exc:
        return set(), str(exc)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip() or "listremotes failed"
        return set(), message
    remotes = {
        line.rstrip(":").strip()
        for line in result.stdout.splitlines()
        if line.rstrip(":").strip()
    }
    return remotes, None


def _rclone_remote_exists(rclone_path: str, remote: str) -> tuple[bool, str | None]:
    remotes, error = _list_rclone_remotes(rclone_path)
    if error:
        return False, error
    if remote in remotes:
        return True, None
    return False, f"Remote '{remote}' not found in rclone config."


def _remote_target(remote: str, base_path: str | None) -> str:
    path_value = str(base_path or "/").strip() or "/"
    if path_value.startswith("/"):
        return f"{remote}:{path_value}"
    return f"{remote}:/{path_value}"


def _validate_remote_path_access(
    rclone_path: str, remote: str, base_path: str
) -> tuple[bool, str | None]:
    target = _remote_target(remote, base_path)
    try:
        result = run_safe(
            [rclone_path, "lsf", target, "--max-depth", "1"],
            capture_output=True,
            timeout=20,
            check=False,
            log_label="rclone lsf",
        )
    except Exception as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, None
    message = (result.stderr or result.stdout or "").strip() or "unable to access remote path"
    return False, message


_BWLIMIT_RE = re.compile(r"^(off|\d+(\.\d+)?[kKmMgGtTpP]?)$")


def _validate_bandwidth_limit(value: str) -> bool:
    raw = value.strip()
    if not raw:
        return True
    return bool(_BWLIMIT_RE.match(raw))


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _seedbox_transfer_limit(settings: dict, sb: dict) -> int:
    cfg = _get_seedbox_cfg(settings)
    default_limit = _positive_int(cfg.get("max_concurrent_uploads", 3), 3)
    return _positive_int(sb.get("max_concurrent_uploads", default_limit), default_limit)


def _run_rclone(args: list[str], *, dry_run: bool = False, verbose: bool = False) -> int:
    rclone = _find_rclone()
    if not rclone:
        print_error(
            tr(
                "seedbox.error.rclone_not_found",
                default="rclone not found on PATH. Install it from https://rclone.org/downloads/",
            )
        )
        return 1

    cmd = [rclone, *args]
    if dry_run:
        cmd.append("--dry-run")
    if verbose:
        cmd.append("-v")

    print_info(f"[dim]$ {' '.join(cmd)}[/dim]")
    try:
        result = run_safe(
            cmd,
            timeout=RCLONE_TRANSFER_TIMEOUT_SECONDS,
            check=False,
            capture_output=False,
            log_label="rclone transfer",
        )
        return result.returncode
    except Exception as exc:
        print_error(
            tr(
                "seedbox.error.rclone_failed",
                default="rclone execution failed: {error}",
                error=str(exc),
            )
        )
        return 1


def _check_disk_space(rclone: str, remote: str, min_free_gb: float) -> bool:
    """Return True if remote has at least min_free_gb free, or if the check fails (non-blocking)."""
    try:
        result = run_safe(
            [rclone, "about", f"{remote}:", "--json"],
            capture_output=True,
            timeout=30,
            check=False,
            log_label="rclone about",
        )
        if result.returncode != 0:
            return True  # Can't check — allow upload
        data = json.loads(result.stdout)
        free_bytes = data.get("free", 0)
        free_gb = free_bytes / (1024**3)
        if free_gb < min_free_gb:
            print_warning(
                tr(
                    "seedbox.warn.low_disk",
                    default="Low disk space on remote: {free:.1f} GB free, {min} GB required",
                    free=free_gb,
                    min=min_free_gb,
                )
            )
            return False
        return True
    except Exception:
        return True  # Non-blocking if check fails


def _run_post_upload_command(command: str, context: dict[str, str]) -> None:
    if not command:
        return
    try:
        expanded = command.format(**context)
        if expanded.strip().lower().startswith("echo "):
            print_info(expanded.strip()[5:].strip().strip("'\""))
            return
        print_info(tr("seedbox.info.post_upload", default="Running post-upload command..."))
        argv = shlex.split(expanded)
        if not argv:
            return
        run_safe(
            argv,
            timeout=POST_UPLOAD_TIMEOUT_SECONDS,
            check=False,
            capture_output=False,
            log_label="post-upload command",
        )
    except Exception as exc:
        print_warning(
            tr(
                "seedbox.warn.post_upload_failed",
                default="Post-upload command failed: {error}",
                error=str(exc),
            )
        )


# ── Core operations ───────────────────────────────────────────────────────────


def _resolve_remote_path(sb: dict, *, remote_path: str | None, category: str | None) -> str:
    base = sb.get("remote_base_path", "/").rstrip("/")
    if remote_path:
        return remote_path
    if category:
        cat_paths = sb.get("category_paths", {})
        cat_sub = cat_paths.get(category, "")
        if cat_sub:
            if str(cat_sub).startswith("/"):
                return str(cat_sub).rstrip("/")
            return f"{base}/{cat_sub.lstrip('/')}"
        print_warning(
            tr(
                "seedbox.warn.unknown_category",
                default="Unknown category '{cat}' — using base path",
                cat=category,
            )
        )
    return base


def _resolve_local_payload(local_path: Path) -> tuple[Path, str | None]:
    payload = find_release_payload(local_path)
    if payload is None:
        return local_path, None
    if payload.path != local_path:
        print_info(
            tr(
                "seedbox.info.detected_payload",
                default="Detected release payload folder: {path}",
                path=payload.path,
            )
        )
    return payload.path, payload.category


def _resolve_local_payloads(local_path: Path) -> list[tuple[Path, str | None]]:
    payloads = find_release_payloads(local_path)
    if not payloads:
        return [(local_path, None)]

    if len(payloads) > 1:
        print_info(
            tr(
                "seedbox.info.detected_payloads",
                default="Detected {count} release payload folders.",
                count=len(payloads),
            )
        )

    resolved: list[tuple[Path, str | None]] = []
    for payload in payloads:
        if payload.path != local_path:
            print_info(
                tr(
                    "seedbox.info.detected_payload",
                    default="Detected release payload folder: {path}",
                    path=payload.path,
                )
            )
        resolved.append((payload.path, payload.category))
    return resolved


def _destination_path_for_source(dest_path: str, local_path: Path) -> str:
    if not local_path.is_dir():
        return dest_path
    normalized = (dest_path or "/").rstrip("/") or "/"
    if normalized.rstrip("/").endswith(f"/{local_path.name}") or normalized == local_path.name:
        return normalized
    if normalized == "/":
        return f"/{local_path.name}"
    return f"{normalized}/{local_path.name}"


def run_seedbox_push(
    *,
    path: str | None,
    seedbox_name: str | None,
    remote_path: str | None,
    category: str | None,
    dry_run: bool = False,
    verbose: bool = False,
    allow_cwd: bool = False,
    non_interactive: bool = False,
) -> int:
    """Upload local files to seedbox via rclone copy."""
    print_module_banner("Seedbox — Push")

    store = SettingsStore()
    settings = store.load()
    sb = _resolve_seedbox(settings, seedbox_name)
    if not sb:
        return 1

    if not path and not allow_cwd:
        print_error("Refusing implicit current-directory upload. Pass a path or use --cwd.")
        return 1
    requested_path = Path(path) if path else Path.cwd()
    if not requested_path.exists():
        print_error(
            tr(
                "seedbox.error.path_not_found",
                default="Path not found: {path}",
                path=requested_path,
            )
        )
        return 1
    payloads = _resolve_local_payloads(requested_path)

    remote = sb.get("rclone_remote", "")
    if not remote:
        print_error(
            tr(
                "seedbox.error.no_remote_in_config",
                default="Seedbox '{name}' has no rclone_remote configured.",
                name=sb.get("name"),
            )
        )
        return 1

    # Disk space check
    if sb.get("disk_check_enabled", True):
        rclone = _find_rclone()
        if rclone:
            min_free = float(sb.get("min_free_gb", 5))
            if not _check_disk_space(rclone, remote, min_free):
                if non_interactive:
                    print_error(
                        tr(
                            "seedbox.error.low_disk_abort",
                            default="Upload aborted: remote free disk is below configured minimum.",
                        )
                    )
                    return 1
                if not click.confirm(
                    tr("seedbox.confirm.low_disk", default="Continue despite low disk space?"),
                    default=False,
                ):
                    return 1

    success = True
    for local_path, inferred_category in payloads:
        effective_category = category or inferred_category
        if not category and inferred_category:
            print_info(
                tr(
                    "seedbox.info.detected_category",
                    default="Detected category: {category}",
                    category=inferred_category,
                )
            )

        dest_path = _destination_path_for_source(
            _resolve_remote_path(sb, remote_path=remote_path, category=effective_category),
            local_path,
        )
        dest = f"{remote}:{dest_path}"

        print_info(
            tr(
                "seedbox.info.pushing",
                default="Pushing {source} → {dest}",
                source=local_path,
                dest=dest,
            )
        )

        transfers = _seedbox_transfer_limit(settings, sb)
        rclone_args = ["copy", str(local_path), dest, "--progress", "--transfers", str(transfers)]
        bw_limit = sb.get("bandwidth_limit", "")
        if bw_limit:
            rclone_args += ["--bwlimit", bw_limit]

        rc = _run_rclone(rclone_args, dry_run=dry_run, verbose=verbose)
        success = success and rc == 0

        if not dry_run and _get_seedbox_cfg(settings).get("history_enabled", True):
            _append_history(
                {
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "action": "push",
                    "seedbox": sb.get("name", ""),
                    "local_path": str(local_path),
                    "remote_path": dest_path,
                    "success": rc == 0,
                }
            )

        if rc == 0:
            if dry_run:
                print_success(tr("seedbox.success.push_dry_run", default="Dry-run complete."))
            else:
                print_success(tr("seedbox.success.push", default="Upload complete."))
            post_cmd = sb.get("post_upload_command", "")
            if post_cmd and not dry_run:
                _run_post_upload_command(
                    post_cmd,
                    {"local_path": str(local_path), "remote_path": dest_path, "remote": remote},
                )
    return 0 if success else 1


def run_seedbox_pull(
    *,
    seedbox_name: str | None,
    remote_path: str | None,
    local_path: str | None,
    dry_run: bool = False,
    verbose: bool = False,
    allow_cwd: bool = False,
) -> int:
    """Download files from seedbox via rclone copy."""
    print_module_banner("Seedbox — Pull")

    store = SettingsStore()
    settings = store.load()
    sb = _resolve_seedbox(settings, seedbox_name)
    if not sb:
        return 1

    remote = sb.get("rclone_remote", "")
    if not remote:
        print_error(
            tr(
                "seedbox.error.no_remote_in_config",
                default="Seedbox '{name}' has no rclone_remote configured.",
                name=sb.get("name"),
            )
        )
        return 1

    src_path = remote_path or sb.get("remote_base_path", "/")
    source = f"{remote}:{src_path}"
    if not local_path and not allow_cwd:
        print_error(
            "Refusing implicit current-directory download. Pass a destination or use --cwd."
        )
        return 1
    dest = Path(local_path) if local_path else Path.cwd()

    print_info(
        tr("seedbox.info.pulling", default="Pulling {source} → {dest}", source=source, dest=dest)
    )

    rclone_args = ["copy", source, str(dest), "--progress"]
    bw_limit = sb.get("bandwidth_limit", "")
    if bw_limit:
        rclone_args += ["--bwlimit", bw_limit]

    rc = _run_rclone(rclone_args, dry_run=dry_run, verbose=verbose)

    if not dry_run and _get_seedbox_cfg(settings).get("history_enabled", True):
        _append_history(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "action": "pull",
                "seedbox": sb.get("name", ""),
                "remote_path": src_path,
                "local_path": str(dest),
                "success": rc == 0,
            }
        )

    if rc == 0:
        if dry_run:
            print_success(tr("seedbox.success.pull_dry_run", default="Dry-run complete."))
        else:
            print_success(tr("seedbox.success.pull", default="Download complete."))
    return rc


def run_seedbox_status(*, seedbox_name: str | None) -> int:
    """Show seedbox remote info and disk usage."""
    print_module_banner("Seedbox — Status")

    store = SettingsStore()
    settings = store.load()
    sb = _resolve_seedbox(settings, seedbox_name)
    if not sb:
        return 1

    remote = sb.get("rclone_remote", "")
    rclone = _find_rclone()
    if not rclone:
        print_error(
            tr(
                "seedbox.error.rclone_not_found",
                default="rclone not found on PATH. Install it from https://rclone.org/downloads/",
            )
        )
        return 1

    table = Table(
        title=tr("seedbox.status.title", default="Seedbox — {name}", name=sb.get("name", "")),
        expand=True,
        box=box.HEAVY,
        border_style="white",
    )
    table.add_column(tr("common.field", default="Field"), width=24, no_wrap=True)
    table.add_column(tr("common.value", default="Value"), ratio=1)
    table.add_row("Name", sb.get("name", ""))
    table.add_row("rclone remote", remote)
    table.add_row("Base path", sb.get("remote_base_path", "/"))
    table.add_row("Max concurrent uploads", str(_seedbox_transfer_limit(settings, sb)))
    bw = sb.get("bandwidth_limit", "") or "unlimited"
    table.add_row("Bandwidth limit", bw)
    table.add_row("Disk check", "enabled" if sb.get("disk_check_enabled", True) else "disabled")
    table.add_row("Min free GB", str(sb.get("min_free_gb", 5)))
    cat_paths = sb.get("category_paths", {})
    if cat_paths:
        for cat, p in cat_paths.items():
            table.add_row(f"  Category: {cat}", p)
    post_cmd = sb.get("post_upload_command", "")
    if post_cmd:
        table.add_row("Post-upload command", post_cmd)
    table.add_row("rclone path", rclone)
    console.print(table)
    remote_ok, remote_error = _rclone_remote_exists(rclone, remote)
    if not remote_ok:
        print_error(
            tr(
                "seedbox.error.remote_not_found",
                default="Remote '{remote}' was not found in rclone config.",
                remote=remote,
            )
        )
        if remote_error:
            print_warning(remote_error)
        return 1

    base_path = str(sb.get("remote_base_path", "/") or "/").strip() or "/"
    path_ok, path_error = _validate_remote_path_access(rclone, remote, base_path)
    if not path_ok:
        print_error(
            tr(
                "seedbox.error.base_path_unreachable",
                default="Cannot access remote base path: {target}",
                target=_remote_target(remote, base_path),
            )
        )
        if path_error:
            print_warning(path_error)
        return 1

    print_info(tr("seedbox.status.checking", default="Checking remote disk usage..."))
    return _run_rclone(["about", f"{remote}:"])


def run_seedbox_explain() -> int:
    """Explain seedbox behavior and safety defaults."""
    print_module_banner("Seedbox — Explain")
    table = Table(title="Seedbox module", expand=True, box=box.HEAVY)
    table.add_column("Field", width=24, no_wrap=True)
    table.add_column("Value", ratio=1, overflow="fold")
    table.add_row("status", "experimental")
    table.add_row("backend", "rclone copy")
    table.add_row("credentials", "stored by rclone, not Framekit")
    table.add_row("history", str(_history_path()))
    table.add_row("profile defaults", "optional: map active Framekit profile -> seedbox")
    table.add_row("concurrency", "uses rclone --transfers from seedbox max_concurrent_uploads")
    table.add_row("push safety", "path required; use --cwd to opt into current directory")
    table.add_row("pull safety", "destination required; use --cwd to opt into current directory")
    table.add_row("advanced", "post_upload_command runs a local command from config")
    console.print(table)
    return 0


def run_seedbox_doctor() -> int:
    """Validate seedbox configuration without transferring files."""
    print_module_banner("Seedbox — Doctor")
    store = SettingsStore()
    settings = store.load()
    seedboxes = _list_seedboxes(settings)
    errors: list[str] = []
    warnings: list[str] = []
    rclone = _find_rclone()
    if not rclone:
        warnings.append("rclone not found on PATH.")
    raw_global_limit = _get_seedbox_cfg(settings).get("max_concurrent_uploads", 3)
    try:
        global_max_concurrent = int(raw_global_limit)
    except (TypeError, ValueError):
        errors.append("seedbox.max_concurrent_uploads must be numeric")
        global_max_concurrent = 3
    if global_max_concurrent < 1:
        errors.append("seedbox.max_concurrent_uploads must be >= 1")
        global_max_concurrent = 3
    seen_names: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    for sb in seedboxes:
        name = str(sb.get("name", "") or "")
        remote = str(sb.get("rclone_remote", "") or "")
        base_path = str(sb.get("remote_base_path", "") or "")
        if not name:
            errors.append("seedbox entry missing name")
        elif name in seen_names:
            errors.append(f"duplicate seedbox name: {name}")
        else:
            seen_names.add(name)
        if not remote:
            errors.append(f"{name or '<unnamed>'}: missing rclone_remote")
        if not base_path:
            errors.append(f"{name or '<unnamed>'}: missing remote_base_path")
        if remote and base_path:
            pair = (remote, base_path)
            if pair in seen_pairs:
                errors.append(
                    f"{name or '<unnamed>'}: duplicate remote/base path combination ({remote}:{base_path})"
                )
            else:
                seen_pairs.add(pair)
        try:
            min_free = float(sb.get("min_free_gb", 5))
            if min_free <= 0:
                errors.append(f"{name or '<unnamed>'}: min_free_gb must be > 0")
        except (TypeError, ValueError):
            errors.append(f"{name or '<unnamed>'}: min_free_gb must be numeric")
        bwlimit = str(sb.get("bandwidth_limit", "") or "").strip()
        if bwlimit and not _validate_bandwidth_limit(bwlimit):
            errors.append(f"{name or '<unnamed>'}: invalid bandwidth_limit '{bwlimit}'")
        try:
            max_transfers = int(sb.get("max_concurrent_uploads", global_max_concurrent))
        except (TypeError, ValueError):
            errors.append(f"{name or '<unnamed>'}: max_concurrent_uploads must be numeric")
            max_transfers = global_max_concurrent
        if max_transfers < 1:
            errors.append(f"{name or '<unnamed>'}: max_concurrent_uploads must be >= 1")
        if rclone and remote:
            remote_ok, remote_error = _rclone_remote_exists(rclone, remote)
            if not remote_ok:
                errors.append(
                    f"{name or '<unnamed>'}: rclone remote '{remote}' invalid"
                    + (f" ({remote_error})" if remote_error else "")
                )
            elif base_path:
                path_ok, path_error = _validate_remote_path_access(rclone, remote, base_path)
                if not path_ok:
                    errors.append(
                        f"{name or '<unnamed>'}: base path inaccessible {_remote_target(remote, base_path)}"
                        + (f" ({path_error})" if path_error else "")
                    )
        if sb.get("post_upload_command"):
            warnings.append(f"{name}: post_upload_command is advanced and runs locally.")
    default_name = str(_get_seedbox_cfg(settings).get("default", "") or "").strip()
    if default_name and default_name not in seen_names:
        errors.append(f"default seedbox '{default_name}' is not defined")
    default_by_profile = _default_by_profile(settings)
    for profile_name, seedbox_name in default_by_profile.items():
        if seedbox_name not in seen_names:
            errors.append(
                f"profile '{profile_name}' maps to undefined seedbox '{seedbox_name}'"
            )
    if errors:
        for error in errors:
            print_error(error)
        return 1
    for warning in warnings:
        print_warning(warning)
    print_success("Seedbox config valid.")
    return 0


# ── Management subcommands ────────────────────────────────────────────────────


def _step_indicator(steps: list[str], current_index: int) -> str:
    """Render step breadcrumb: completed=green-dim, current=bold-yellow, pending=dim."""
    parts = []
    for i, label in enumerate(steps):
        if i < current_index:
            parts.append(f"[dim green]✓ {label}[/dim green]")
        elif i == current_index:
            parts.append(f"[bold yellow]→ {label}[/bold yellow]")
        else:
            parts.append(f"[dim]{label}[/dim]")
    return "  ".join(parts)


def _print_wizard_step(title: str, explanation: str, steps: list[str], current: int) -> None:
    """Print wizard step: title, explanation, breadcrumb, separator."""
    console.print()
    console.print(f"[bold]{title}[/bold]")
    console.print(f"[dim]{explanation}[/dim]")
    console.print()
    console.print(_step_indicator(steps, current))
    console.print("[dim]" + "─" * 60 + "[/dim]")


def _validate_rclone_remote(remote: str) -> bool:
    """Return True if the remote exists in rclone config."""
    rclone = _find_rclone()
    if not rclone:
        return False
    ok, _error = _rclone_remote_exists(rclone, remote)
    return ok


def seedbox_ready_for_pipeline(settings: dict) -> tuple[bool, str]:
    """Return whether seedbox can be auto-enabled for pipeline usage."""
    active_profile = _active_profile_name()
    sb = _get_default_seedbox(settings, profile_name=active_profile)
    if not sb:
        return False, "Seedbox not configured. Use 'fk seedbox add'."
    rclone = _find_rclone()
    if not rclone:
        return False, "rclone not found on PATH."
    remote = str(sb.get("rclone_remote", "") or "").strip()
    if not remote:
        return False, f"Seedbox '{sb.get('name', '<unnamed>')}' has no rclone_remote."
    exists, remote_error = _rclone_remote_exists(rclone, remote)
    if not exists:
        return (
            False,
            remote_error
            or f"Seedbox remote '{remote}' is invalid. Run 'rclone config' then 'fk seedbox add'.",
        )
    base_path = str(sb.get("remote_base_path", "/") or "/").strip() or "/"
    accessible, path_error = _validate_remote_path_access(rclone, remote, base_path)
    if not accessible:
        return (
            False,
            f"Seedbox path not reachable: {_remote_target(remote, base_path)} ({path_error or 'unknown error'})",
        )
    return True, "ok"


def run_seedbox_add(
    *,
    name: str | None,
    rclone_remote: str | None,
    base_path: str | None,
) -> int:
    """Interactive wizard to add/register a new seedbox."""
    print_module_banner("Seedbox — Add")

    store = SettingsStore()
    settings = store.load()
    seedboxes = _list_seedboxes(settings)
    rclone = _find_rclone()
    if not rclone:
        print_error(
            tr(
                "seedbox.error.rclone_required_for_add",
                default=(
                    "rclone is required to add a seedbox profile.\n"
                    "Install rclone first, run 'rclone config', then retry."
                ),
            )
        )
        return 1

    STEPS = [
        "Name",
        "rclone Remote",
        "Base Path",
        "Concurrency",
        "Bandwidth",
        "Disk Check",
        "Categories",
        "Post-upload",
        "Defaults",
    ]

    # ── Step 0: Name ──────────────────────────────────────────────────────────
    _print_wizard_step(
        "Seedbox name",
        "A short identifier for this seedbox (e.g. 'orbit', 'seedhost', 'htpc').\n"
        "Used in commands like:  fk seedbox push --seedbox orbit",
        STEPS,
        0,
    )
    if not name:
        name = click.prompt("  Name")
    name = (name or "").strip()
    if not name:
        print_error(tr("seedbox.error.empty_name", default="Seedbox name cannot be empty."))
        return 1
    if _find_seedbox(settings, name):
        print_error(
            tr(
                "seedbox.error.already_exists",
                default="A seedbox named '{name}' already exists. Remove it first.",
                name=name,
            )
        )
        return 1

    # ── Step 1: rclone remote ─────────────────────────────────────────────────
    _print_wizard_step(
        "rclone remote name",
        "The name of a remote already set up in rclone.\n"
        "  → Run 'rclone config' to add a new remote (SFTP, FTP, etc.)\n"
        "  → Run 'rclone listremotes' to see existing remotes\n"
        "  Example: if your remote is named 'mybox', enter 'mybox'",
        STEPS,
        1,
    )
    if not rclone_remote:
        rclone_remote = click.prompt("  rclone remote name", default=name)
    rclone_remote = (rclone_remote or "").strip()
    if not rclone_remote:
        print_error("rclone remote name cannot be empty.")
        return 1
    remote_ok, remote_error = _rclone_remote_exists(rclone, rclone_remote)
    if not remote_ok:
        print_error(
            tr(
                "seedbox.error.remote_not_found",
                default=(
                    "Remote '{remote}' was not found in rclone config.\n"
                    "Run 'rclone config' then retry."
                ),
                remote=rclone_remote,
            )
        )
        if remote_error:
            print_warning(remote_error)
        return 1

    # ── Step 2: Base path ─────────────────────────────────────────────────────
    _print_wizard_step(
        "Remote base path",
        "The root directory on the seedbox where files will be uploaded.\n"
        "  Example: /home/user/torrents   or   /downloads\n"
        "  Leave blank to use '/' (root of the remote).",
        STEPS,
        2,
    )
    if not base_path:
        base_path = click.prompt("  Remote base path", default="/")
    base_path = (base_path or "").strip() or "/"
    access_ok, access_error = _validate_remote_path_access(rclone, rclone_remote, base_path)
    if not access_ok:
        print_error(
            tr(
                "seedbox.error.base_path_unreachable",
                default="Cannot access remote base path: {target}",
                target=_remote_target(rclone_remote, base_path),
            )
        )
        if access_error:
            print_warning(access_error)
        return 1

    # ── Step 3: Concurrency ───────────────────────────────────────────────────
    _print_wizard_step(
        "Concurrent uploads",
        "Maximum simultaneous file transfers for this seedbox profile.\n"
        "  This maps to rclone '--transfers'.\n"
        "  Recommended: 2-6 depending on your line and provider limits.",
        STEPS,
        3,
    )
    cfg = _get_seedbox_cfg(settings)
    default_max_transfers = _positive_int(cfg.get("max_concurrent_uploads", 3), 3)
    raw_max_transfers = click.prompt(
        "  Max concurrent uploads",
        default=str(default_max_transfers),
    ).strip()
    try:
        max_transfers = int(raw_max_transfers)
    except ValueError:
        print_error("Max concurrent uploads must be numeric.")
        return 1
    if max_transfers <= 0:
        print_error("Max concurrent uploads must be greater than 0.")
        return 1

    # ── Step 4: Bandwidth limit ───────────────────────────────────────────────
    _print_wizard_step(
        "Bandwidth limit (optional)",
        "Throttle the upload speed to avoid saturating your connection.\n"
        "  Format: '10M' = 10 MB/s,  '500K' = 500 KB/s\n"
        "  Leave blank for unlimited.",
        STEPS,
        4,
    )
    bw = click.prompt("  Bandwidth limit (e.g. 10M)", default="").strip()
    if not _validate_bandwidth_limit(bw):
        print_error("Invalid bandwidth limit. Use values like 500K, 10M, 1.5G or off.")
        return 1

    # ── Step 5: Disk space check ──────────────────────────────────────────────
    _print_wizard_step(
        "Disk space check (optional)",
        "Framekit can query available disk space on the seedbox before uploading\n"
        "and warn you if free space falls below a minimum threshold.",
        STEPS,
        5,
    )
    disk_check = click.confirm("  Enable disk space check before upload?", default=True)
    min_free = 5.0
    if disk_check:
        min_free_str = click.prompt("  Minimum free space required (GB)", default="5")
        try:
            min_free = float(min_free_str)
        except ValueError:
            print_error("Minimum free space must be numeric.")
            return 1
        if min_free <= 0:
            print_error("Minimum free space must be greater than 0.")
            return 1

    # ── Step 6: Category paths ────────────────────────────────────────────────
    _print_wizard_step(
        "Category paths (optional)",
        "Map upload categories to sub-folders on the seedbox.\n"
        "  Used with:  fk seedbox push /path --category movies\n"
        "  Example: movies → 'Movies',  series → 'Series'\n"
        "  Press Enter to skip a category.",
        STEPS,
        6,
    )
    category_paths: dict[str, str] = {}
    for cat in ("movies", "series", "anime"):
        sub = click.prompt(f"  Path for '{cat}' (relative to base path)", default="").strip()
        if sub:
            category_paths[cat] = sub

    # ── Step 7: Post-upload command ───────────────────────────────────────────
    _print_wizard_step(
        "Post-upload command (optional)",
        "A shell command to run after a successful upload.\n"
        "  Available variables: {local_path}  {remote_path}  {remote}\n"
        "  Example: echo 'Uploaded {local_path}'\n"
        "  Leave blank to skip.",
        STEPS,
        7,
    )
    post_cmd = click.prompt("  Post-upload command", default="").strip()

    # ── Step 8: Defaults ──────────────────────────────────────────────────────
    _print_wizard_step(
        "Default selection",
        "You can set this seedbox as global default and optionally for the active Framekit profile.",
        STEPS,
        8,
    )
    active_profile = _active_profile_name()

    # ── Build and save ────────────────────────────────────────────────────────
    new_sb: dict[str, Any] = {
        "name": name,
        "rclone_remote": rclone_remote,
        "remote_base_path": base_path,
        "max_concurrent_uploads": max_transfers,
        "bandwidth_limit": bw,
        "disk_check_enabled": disk_check,
        "min_free_gb": min_free,
        "post_upload_command": post_cmd,
        "category_paths": category_paths,
    }
    duplicate = next(
        (
            sb
            for sb in seedboxes
            if str(sb.get("rclone_remote", "")).strip() == rclone_remote
            and str(sb.get("remote_base_path", "/")).strip() == base_path
        ),
        None,
    )
    if duplicate is not None:
        print_error(
            tr(
                "seedbox.error.duplicate_remote_path",
                default=(
                    "A seedbox profile already uses this remote/base path combination: "
                    "{name} ({remote}:{base_path})"
                ),
                name=str(duplicate.get("name", "<unnamed>")),
                remote=rclone_remote,
                base_path=base_path,
            )
        )
        return 1
    seedboxes.append(new_sb)

    current_default = cfg.get("default", "")
    if not current_default or click.confirm(
        tr("seedbox.add.set_default", default="Set '{name}' as default seedbox?", name=name),
        default=not bool(current_default),
    ):
        current_default = name

    profile_defaults = _default_by_profile(settings)
    if active_profile:
        if click.confirm(
            f"  Use '{name}' by default for active profile '{active_profile}'?",
            default=True,
        ):
            profile_defaults[active_profile] = name

    _save_seedboxes(
        store,
        seedboxes,
        default=current_default,
        default_by_profile=profile_defaults,
    )
    print_success(
        tr("seedbox.add.success", default="Seedbox '{name}' registered successfully.", name=name)
    )
    return 0


def run_seedbox_list() -> int:
    """List all configured seedboxes."""
    store = SettingsStore()
    settings = store.load()
    seedboxes = _list_seedboxes(settings)
    cfg = _get_seedbox_cfg(settings)
    default_name = cfg.get("default", "")

    if not seedboxes:
        print_info(
            tr(
                "seedbox.list.empty",
                default="No seedboxes configured. Use 'fk seedbox add' to register one.",
            )
        )
        return 0

    table = Table(
        title=tr("seedbox.list.title", default="Configured Seedboxes"),
        expand=True,
        box=box.SIMPLE_HEAD,
        border_style="dim",
    )
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("rclone Remote")
    table.add_column("Base Path")
    table.add_column("Max Xfers", justify="right")
    table.add_column("BW Limit")
    table.add_column("Default", justify="center")

    global_default_xfers = _positive_int(cfg.get("max_concurrent_uploads", 3), 3)
    for sb in seedboxes:
        name = sb.get("name", "")
        is_default = "✓" if name == default_name else ""
        max_xfers = _positive_int(sb.get("max_concurrent_uploads", global_default_xfers), global_default_xfers)
        table.add_row(
            name,
            sb.get("rclone_remote", ""),
            sb.get("remote_base_path", "/"),
            str(max_xfers),
            sb.get("bandwidth_limit", "") or "unlimited",
            is_default,
        )

    console.print(table)
    profile_defaults = _default_by_profile(settings)
    if profile_defaults:
        mappings = ", ".join(
            f"{profile}:{seedbox_name}" for profile, seedbox_name in sorted(profile_defaults.items())
        )
        print_info(f"Profile defaults: {mappings}")
    return 0


def run_seedbox_remove(*, name: str) -> int:
    """Remove a seedbox registration."""
    store = SettingsStore()
    settings = store.load()
    seedboxes = _list_seedboxes(settings)

    before = len(seedboxes)
    seedboxes = [sb for sb in seedboxes if sb.get("name") != name]
    if len(seedboxes) == before:
        print_error(
            tr("seedbox.error.not_found", default="Seedbox '{name}' not configured.", name=name)
        )
        return 1

    cfg = _get_seedbox_cfg(settings)
    new_default = cfg.get("default", "")
    if new_default == name:
        new_default = seedboxes[0].get("name", "") if seedboxes else ""

    profile_defaults = {
        profile: seedbox_name
        for profile, seedbox_name in _default_by_profile(settings).items()
        if seedbox_name != name
    }

    _save_seedboxes(
        store,
        seedboxes,
        default=new_default,
        default_by_profile=profile_defaults,
    )
    print_success(tr("seedbox.remove.success", default="Seedbox '{name}' removed.", name=name))
    return 0


def run_seedbox_use(*, name: str, profile_name: str | None = None) -> int:
    """Set a seedbox as the default globally or for a specific profile."""
    store = SettingsStore()
    settings = store.load()
    if not _find_seedbox(settings, name):
        print_error(
            tr("seedbox.error.not_found", default="Seedbox '{name}' not configured.", name=name)
        )
        return 1

    data = store.load()
    if "seedbox" not in data:
        data["seedbox"] = {}
    seedbox_cfg = data["seedbox"]
    if profile_name:
        mapping = seedbox_cfg.get("default_by_profile", {})
        if not isinstance(mapping, dict):
            mapping = {}
        mapping[str(profile_name).strip()] = name
        seedbox_cfg["default_by_profile"] = mapping
        print_success(
            f"Default seedbox for profile '{profile_name}' set to '{name}'."
        )
    else:
        seedbox_cfg["default"] = name
        print_success(
            tr("seedbox.use.success", default="Default seedbox set to '{name}'.", name=name)
        )
    store.save(data)
    return 0


def run_seedbox_history(*, seedbox_name: str | None, limit: int) -> int:
    """Show upload/download history."""
    entries = _load_history(seedbox_name, limit=limit)
    if not entries:
        print_info(tr("seedbox.history.empty", default="No history found."))
        return 0

    table = Table(
        title=tr(
            "seedbox.history.title",
            default="Upload History{filter}",
            filter=f" — {seedbox_name}" if seedbox_name else "",
        ),
        expand=True,
        box=box.SIMPLE_HEAD,
        border_style="dim",
    )
    table.add_column("Timestamp", no_wrap=True)
    table.add_column("Action", no_wrap=True)
    table.add_column("Seedbox", no_wrap=True)
    table.add_column("Local Path")
    table.add_column("Remote Path")
    table.add_column("Status", justify="center")

    for entry in reversed(entries):
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        action = entry.get("action", "")
        sb = entry.get("seedbox", "")
        local = entry.get("local_path", "")
        remote = entry.get("remote_path", "")
        ok = entry.get("success", False)
        status_cell = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(ts, action, sb, local, remote, status_cell)

    console.print(table)
    return 0


# ── CLI groups & commands ─────────────────────────────────────────────────────


@click.group(
    "seedbox",
    context_settings={"help_option_names": ["-h", "--help"]},
    help=tr(
        "cli.seedbox.help",
        default=(
            "-[BETA]- Manage seedbox transfers via rclone.\n\n"
            "Register seedboxes with 'fk seedbox add', then use push/pull to transfer files.\n"
            "Configure rclone remotes separately with 'rclone config'.\n\n"
            "Examples:\n"
            "  fk seedbox add\n"
            "  fk seedbox push /path/to/release --category movies\n"
            "  fk seedbox status\n"
            "  fk seedbox history"
        ),
    ),
)
def seedbox_group() -> None:
    """Seedbox management commands."""


@seedbox_group.command("add", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--name", "-n", default=None, help="Seedbox name")
@click.option("--remote", "rclone_remote", default=None, help="rclone remote name")
@click.option("--path", "base_path", default=None, help="Remote base path")
def seedbox_add_command(name: str | None, rclone_remote: str | None, base_path: str | None) -> int:
    """Register a new seedbox."""
    return run_seedbox_add(name=name, rclone_remote=rclone_remote, base_path=base_path)


@seedbox_group.command("list", context_settings={"help_option_names": ["-h", "--help"]})
def seedbox_list_command() -> int:
    """List all configured seedboxes."""
    return run_seedbox_list()


@seedbox_group.command("remove", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
def seedbox_remove_command(name: str) -> int:
    """Remove a seedbox registration."""
    return run_seedbox_remove(name=name)


@seedbox_group.command("use", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
@click.option("--profile", "profile_name", default=None, help="Bind default to a Framekit profile")
def seedbox_use_command(name: str, profile_name: str | None) -> int:
    """Set a seedbox as default (global or per profile)."""
    return run_seedbox_use(name=name, profile_name=profile_name)


@seedbox_group.command("push", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("path_parts", nargs=-1)
@click.option(
    "-s",
    "--seedbox",
    "seedbox_name",
    default=None,
    help="Seedbox to use (default: configured default)",
)
@click.option("--remote-path", default=None, help="Override remote destination path")
@click.option("-c", "--category", default=None, help="Upload category (movies, series, anime, ...)")
@click.option("-d", "--dry-run", is_flag=True, help="Preview only (rclone --dry-run)")
@click.option("-v", "--verbose", is_flag=True, help="Verbose rclone output")
@click.option("--cwd", is_flag=True, help="Explicitly allow current directory as source")
def seedbox_push_command(
    path_parts: tuple[str, ...],
    seedbox_name: str | None,
    remote_path: str | None,
    category: str | None,
    dry_run: bool,
    verbose: bool,
    cwd: bool,
) -> int:
    """Upload local files to the seedbox."""
    return run_seedbox_push(
        path=join_path_parts(path_parts) or None,
        seedbox_name=seedbox_name,
        remote_path=remote_path,
        category=category,
        dry_run=dry_run,
        verbose=verbose,
        allow_cwd=cwd,
    )


@seedbox_group.command("pull", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("remote_path_arg", required=False)
@click.argument("local_path_arg", required=False)
@click.option("-s", "--seedbox", "seedbox_name", default=None, help="Seedbox to use")
@click.option("--remote-path", default=None, help="Remote source path")
@click.option("-l", "--local", "local_path", help="Local destination path")
@click.option("-d", "--dry-run", is_flag=True, help="Preview only (rclone --dry-run)")
@click.option("-v", "--verbose", is_flag=True, help="Verbose rclone output")
@click.option("--cwd", is_flag=True, help="Explicitly allow current directory as destination")
def seedbox_pull_command(
    remote_path_arg: str | None,
    local_path_arg: str | None,
    seedbox_name: str | None,
    remote_path: str | None,
    local_path: str | None,
    dry_run: bool,
    verbose: bool,
    cwd: bool,
) -> int:
    """Download files from the seedbox."""
    return run_seedbox_pull(
        seedbox_name=seedbox_name,
        remote_path=remote_path or remote_path_arg,
        local_path=local_path or local_path_arg,
        dry_run=dry_run,
        verbose=verbose,
        allow_cwd=cwd,
    )


@seedbox_group.command("explain", context_settings={"help_option_names": ["-h", "--help"]})
def seedbox_explain_command() -> int:
    """Explain seedbox module behavior."""
    return run_seedbox_explain()


@seedbox_group.command("doctor", context_settings={"help_option_names": ["-h", "--help"]})
def seedbox_doctor_command() -> int:
    """Validate seedbox configuration."""
    return run_seedbox_doctor()


@seedbox_group.command("status", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-s", "--seedbox", "seedbox_name", default=None, help="Seedbox to inspect")
def seedbox_status_command(seedbox_name: str | None) -> int:
    """Show seedbox configuration and remote disk usage."""
    return run_seedbox_status(seedbox_name=seedbox_name)


@seedbox_group.command("history", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-s", "--seedbox", "seedbox_name", default=None, help="Filter by seedbox name")
@click.option("--limit", default=50, show_default=True, help="Maximum entries to show")
def seedbox_history_command(seedbox_name: str | None, limit: int) -> int:
    """Show upload/download history."""
    return run_seedbox_history(seedbox_name=seedbox_name, limit=limit)
