"""``framekit seedbox`` — multi-seedbox transfer via rclone.

Supports multiple named seedbox profiles.  Credentials live in rclone's
own config; metadata (paths, limits, etc.) is stored in framekit.yaml.
Upload history is written to ~/.config/framekit/seedbox/history.ndjson.
"""

from __future__ import annotations

import json
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
    return list(_get_seedbox_cfg(settings).get("seedboxes", []))


def _find_seedbox(settings: dict, name: str) -> dict | None:
    for sb in _list_seedboxes(settings):
        if sb.get("name") == name:
            return sb
    return None


def _get_default_seedbox(settings: dict) -> dict | None:
    cfg = _get_seedbox_cfg(settings)
    default_name = cfg.get("default", "")
    if default_name:
        sb = _find_seedbox(settings, default_name)
        if sb:
            return sb
    # Fall back to first configured seedbox
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
    sb = _get_default_seedbox(settings)
    if not sb:
        print_error(
            tr(
                "seedbox.error.no_seedbox",
                default="No seedbox configured. Use 'fk seedbox add' to register one.",
            )
        )
    return sb


def _save_seedboxes(store: SettingsStore, seedboxes: list[dict], default: str = "") -> None:
    data = store.load()
    if "seedbox" not in data:
        data["seedbox"] = {}
    data["seedbox"]["seedboxes"] = seedboxes
    if default:
        data["seedbox"]["default"] = default
    store.save(data)


# ── rclone helpers ────────────────────────────────────────────────────────────


def _find_rclone() -> str | None:
    return shutil.which("rclone")


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
            return f"{base}/{cat_sub.lstrip('/')}"
        print_warning(
            tr(
                "seedbox.warn.unknown_category",
                default="Unknown category '{cat}' — using base path",
                cat=category,
            )
        )
    return base


def run_seedbox_push(
    *,
    path: str | None,
    seedbox_name: str | None,
    remote_path: str | None,
    category: str | None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Upload local files to seedbox via rclone copy."""
    print_module_banner("Seedbox — Push")

    store = SettingsStore()
    settings = store.load()
    sb = _resolve_seedbox(settings, seedbox_name)
    if not sb:
        return 1

    local_path = Path(path) if path else Path.cwd()
    if not local_path.exists():
        print_error(
            tr("seedbox.error.path_not_found", default="Path not found: {path}", path=local_path)
        )
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

    # Disk space check
    if sb.get("disk_check_enabled", True):
        rclone = _find_rclone()
        if rclone:
            min_free = float(sb.get("min_free_gb", 5))
            if not _check_disk_space(rclone, remote, min_free):
                if not click.confirm(
                    tr("seedbox.confirm.low_disk", default="Continue despite low disk space?"),
                    default=False,
                ):
                    return 1

    dest_path = _resolve_remote_path(sb, remote_path=remote_path, category=category)
    dest = f"{remote}:{dest_path}"

    print_info(
        tr(
            "seedbox.info.pushing",
            default="Pushing {source} → {dest}",
            source=local_path,
            dest=dest,
        )
    )

    rclone_args = ["copy", str(local_path), dest, "--progress"]
    bw_limit = sb.get("bandwidth_limit", "")
    if bw_limit:
        rclone_args += ["--bwlimit", bw_limit]

    rc = _run_rclone(rclone_args, dry_run=dry_run, verbose=verbose)

    # Record history
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
        print_success(tr("seedbox.success.push", default="Upload complete."))
        post_cmd = sb.get("post_upload_command", "")
        if post_cmd:
            _run_post_upload_command(
                post_cmd,
                {"local_path": str(local_path), "remote_path": dest_path, "remote": remote},
            )
    return rc


def run_seedbox_pull(
    *,
    seedbox_name: str | None,
    remote_path: str | None,
    local_path: str | None,
    dry_run: bool = False,
    verbose: bool = False,
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

    print_info(tr("seedbox.status.checking", default="Checking remote disk usage..."))
    return _run_rclone(["about", f"{remote}:"])


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
    """Return True if the remote appears in `rclone listremotes`, or if check cannot run."""
    rclone = _find_rclone()
    if not rclone:
        return True
    try:
        result = run_safe(
            [rclone, "listremotes"],
            capture_output=True,
            timeout=10,
            check=False,
            log_label="rclone listremotes",
        )
        listed = [line.rstrip(":").strip() for line in result.stdout.splitlines() if line.strip()]
        return remote in listed
    except Exception:
        return True


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

    STEPS = [
        "Name",
        "rclone Remote",
        "Base Path",
        "Bandwidth",
        "Disk Check",
        "Categories",
        "Post-upload",
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

    if not _validate_rclone_remote(rclone_remote):
        print_warning(
            tr(
                "seedbox.warn.remote_not_found",
                default=(
                    "Remote '{remote}' was not found in 'rclone listremotes'.\n"
                    "  Make sure it exists in your rclone config before uploading."
                ),
                remote=rclone_remote,
            )
        )
        if not click.confirm("  Continue anyway?", default=False):
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

    # ── Step 3: Bandwidth limit ───────────────────────────────────────────────
    _print_wizard_step(
        "Bandwidth limit (optional)",
        "Throttle the upload speed to avoid saturating your connection.\n"
        "  Format: '10M' = 10 MB/s,  '500K' = 500 KB/s\n"
        "  Leave blank for unlimited.",
        STEPS,
        3,
    )
    bw = click.prompt("  Bandwidth limit (e.g. 10M)", default="").strip()

    # ── Step 4: Disk space check ──────────────────────────────────────────────
    _print_wizard_step(
        "Disk space check (optional)",
        "Framekit can query available disk space on the seedbox before uploading\n"
        "and warn you if free space falls below a minimum threshold.",
        STEPS,
        4,
    )
    disk_check = click.confirm("  Enable disk space check before upload?", default=True)
    min_free = 5
    if disk_check:
        min_free_str = click.prompt("  Minimum free space required (GB)", default="5")
        try:
            min_free = int(min_free_str)
        except ValueError:
            min_free = 5

    # ── Step 5: Category paths ────────────────────────────────────────────────
    _print_wizard_step(
        "Category paths (optional)",
        "Map upload categories to sub-folders on the seedbox.\n"
        "  Used with:  fk seedbox push /path --category movies\n"
        "  Example: movies → 'Movies',  series → 'Series'\n"
        "  Press Enter to skip a category.",
        STEPS,
        5,
    )
    category_paths: dict[str, str] = {}
    for cat in ("movies", "series", "anime"):
        sub = click.prompt(f"  Path for '{cat}' (relative to base path)", default="").strip()
        if sub:
            category_paths[cat] = sub

    # ── Step 6: Post-upload command ───────────────────────────────────────────
    _print_wizard_step(
        "Post-upload command (optional)",
        "A shell command to run after a successful upload.\n"
        "  Available variables: {local_path}  {remote_path}  {remote}\n"
        "  Example: echo 'Uploaded {local_path}'\n"
        "  Leave blank to skip.",
        STEPS,
        6,
    )
    post_cmd = click.prompt("  Post-upload command", default="").strip()

    # ── Build and save ────────────────────────────────────────────────────────
    new_sb: dict[str, Any] = {
        "name": name,
        "rclone_remote": rclone_remote,
        "remote_base_path": base_path,
        "bandwidth_limit": bw,
        "disk_check_enabled": disk_check,
        "min_free_gb": min_free,
        "post_upload_command": post_cmd,
        "category_paths": category_paths,
    }
    seedboxes.append(new_sb)

    cfg = _get_seedbox_cfg(settings)
    current_default = cfg.get("default", "")
    if not current_default or click.confirm(
        tr("seedbox.add.set_default", default="Set '{name}' as default seedbox?", name=name),
        default=not bool(current_default),
    ):
        current_default = name

    _save_seedboxes(store, seedboxes, default=current_default)
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
    table.add_column("BW Limit")
    table.add_column("Default", justify="center")

    for sb in seedboxes:
        name = sb.get("name", "")
        is_default = "✓" if name == default_name else ""
        table.add_row(
            name,
            sb.get("rclone_remote", ""),
            sb.get("remote_base_path", "/"),
            sb.get("bandwidth_limit", "") or "unlimited",
            is_default,
        )

    console.print(table)
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

    _save_seedboxes(store, seedboxes, default=new_default)
    print_success(tr("seedbox.remove.success", default="Seedbox '{name}' removed.", name=name))
    return 0


def run_seedbox_use(*, name: str) -> int:
    """Set a seedbox as the default."""
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
    data["seedbox"]["default"] = name
    store.save(data)
    print_success(tr("seedbox.use.success", default="Default seedbox set to '{name}'.", name=name))
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
            "Manage seedbox transfers via rclone.\n\n"
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
def seedbox_use_command(name: str) -> int:
    """Set a seedbox as default."""
    return run_seedbox_use(name=name)


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
def seedbox_push_command(
    path_parts: tuple[str, ...],
    seedbox_name: str | None,
    remote_path: str | None,
    category: str | None,
    dry_run: bool,
    verbose: bool,
) -> int:
    """Upload local files to the seedbox."""
    return run_seedbox_push(
        path=join_path_parts(path_parts) or None,
        seedbox_name=seedbox_name,
        remote_path=remote_path,
        category=category,
        dry_run=dry_run,
        verbose=verbose,
    )


@seedbox_group.command("pull", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-s", "--seedbox", "seedbox_name", default=None, help="Seedbox to use")
@click.option("--remote-path", default=None, help="Remote source path")
@click.option("-l", "--local", "local_path", help="Local destination path")
@click.option("-d", "--dry-run", is_flag=True, help="Preview only (rclone --dry-run)")
@click.option("-v", "--verbose", is_flag=True, help="Verbose rclone output")
def seedbox_pull_command(
    seedbox_name: str | None,
    remote_path: str | None,
    local_path: str | None,
    dry_run: bool,
    verbose: bool,
) -> int:
    """Download files from the seedbox."""
    return run_seedbox_pull(
        seedbox_name=seedbox_name,
        remote_path=remote_path,
        local_path=local_path,
        dry_run=dry_run,
        verbose=verbose,
    )


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
