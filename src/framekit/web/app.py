from __future__ import annotations

import re
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from framekit.commands.doctor import collect_doctor_payload
from framekit.core.auth.models import UserRole, UserStore
from framekit.core.auth.tokens import TokenError, create_access_token, decode_access_token
from framekit.core.webhooks import (
    add_webhook,
    load_webhooks,
    remove_webhook,
    update_webhook,
)
from framekit.web.modules import (
    RunModuleRequest,
    activate_settings_profile,
    add_alias_entry,
    add_torrent_announce_url,
    add_watch_folder,
    create_settings_profile,
    deactivate_settings_profile,
    delete_settings_profile,
    disable_alias_entry,
    enable_alias_entry,
    delete_all_yaml_presets,
    list_settings_profiles,
    create_yaml_preset,
    delete_yaml_preset,
    get_image_host_key,
    get_provider_token_value,
    get_torrent_client_password,
    set_image_host_key,
    set_provider_token_value,
    set_torrent_client_password,
    cancel_module_job,
    clear_module_jobs,
    check_tools,
    create_seedbox_profile,
    enqueue_module_job,
    get_module_job,
    get_settings_summary,
    get_tmdb_token_value,
    get_upload_state,
    get_upload_tracker_info,
    get_vault_status_info,
    get_embedded_watcher_state,
    get_watch_service_status,
    start_embedded_watcher,
    stop_embedded_watcher,
    stop_watch_service,
    list_intake_sources,
    create_intake_source,
    delete_intake_source,
    verify_intake_token,
    submit_intake_release,
    list_aliases_summary,
    list_module_jobs,
    list_modules,
    list_modules_spec,
    list_presets,
    get_seedbox_default_by_profile,
    list_seedbox_history,
    list_seedboxes_summary,
    list_pipeline_batch_resources,
    list_runs_from_ledger,
    list_torrent_announces_info,
    list_upload_history,
    list_upload_trackers_summary,
    list_watch_folders,
    patch_settings_values,
    read_log_lines,
    remove_alias_entry,
    remove_seedbox_profile,
    remove_torrent_announce_url,
    remove_watch_folder,
    rename_torrent_announce_label,
    rerun_module_job,
    run_module_command,
    select_torrent_announce_url,
    set_default_seedbox,
    set_tmdb_token_value,
    set_upload_state,
)

# Built frontend assets resolution order:
# 1) Packaged static assets inside framekit.web (works for installed wheel/sdist/editable)
# 2) Source-tree Vite output at web-ui/dist (works in repository checkouts)
_PACKAGE_STATIC_DIR: Path = Path(__file__).resolve().parent / "static"
_SOURCE_DIST_DIR: Path = Path(__file__).parent.parent.parent.parent / "web-ui" / "dist"


def _resolve_frontend_dist_dir() -> Path | None:
    """Return frontend build directory, preferring packaged assets over source-tree dist."""
    for candidate in (_PACKAGE_STATIC_DIR, _SOURCE_DIST_DIR):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_dir():
            return resolved
    return None


class UploadStateRequest(BaseModel):
    """Request payload for upload state mutation."""

    enabled: bool
    auto_upload: bool | None = None


class SettingsPatchRequest(BaseModel):
    """Request payload for restricted settings patch."""

    changes: dict[str, Any]


class SeedboxCreateRequest(BaseModel):
    """Request payload for creating seedbox profile."""

    name: str
    rclone_remote: str
    remote_base_path: str
    max_concurrent_uploads: int | None = None
    bandwidth_limit: str = ""
    set_default: bool = False


class SeedboxNameRequest(BaseModel):
    """Request payload for seedbox target name."""

    name: str
    profile_name: str | None = None


class TmdbTokenRequest(BaseModel):
    """Request payload for TMDB token write."""

    token: str


class AnnounceAddRequest(BaseModel):
    """Request payload for adding a torrent announce URL."""

    url: str


class AnnounceSelectRequest(BaseModel):
    """Request payload for selecting a torrent announce URL."""

    url: str


class ImageHostKeyRequest(BaseModel):
    """Request payload for setting an image host API key."""

    key: str


class TorrentClientPasswordRequest(BaseModel):
    """Request payload for setting the torrent client password."""

    password: str


class PresetCreateRequest(BaseModel):
    """Request payload for creating a YAML preset."""

    name: str
    content: str


class WatchFolderAddRequest(BaseModel):
    """Request payload for adding a watch folder."""

    path: str
    preset: str = "default"


class ProfileActivateRequest(BaseModel):
    """Request payload for activating a settings profile."""

    name: str


class ProviderTokenRequest(BaseModel):
    """Request payload for setting a metadata provider API token."""

    token: str


class AnnounceRenameRequest(BaseModel):
    """Request payload for setting an announce URL display label."""

    label: str


class ProfileCreateRequest(BaseModel):
    """Request payload for creating a settings profile."""

    name: str
    description: str = ""
    overrides: dict[str, Any] = {}


class AliasCreateRequest(BaseModel):
    """Request payload for creating a command alias."""

    name: str
    command: str
    description: str = ""
    enabled: bool = True


class WebhookCreateRequest(BaseModel):
    """Request payload for registering a webhook."""

    name: str
    url: str
    discord: bool = False
    events: list[str] | None = None
    title_template: str = ""
    body_template: str = ""


class WebhookUpdateRequest(BaseModel):
    """Request payload for updating a webhook. All fields are optional."""

    enabled: bool | None = None
    name: str | None = None
    url: str | None = None
    discord: bool | None = None
    events: list[str] | None = None
    # None = don't change; "" = clear; non-empty str = set new value
    title_template: str | None = None
    body_template: str | None = None


class WebhookTestPayloadRequest(BaseModel):
    """Request payload for testing an unsaved webhook config."""

    url: str
    discord: bool = False
    events: list[str] | None = None
    title_template: str = ""
    body_template: str = ""


class IntakeSourceCreateRequest(BaseModel):
    """Request payload for registering a new intake source."""

    name: str
    source_id: str
    default_preset: str | None = None


class IntakeReleaseRequest(BaseModel):
    """Request payload for submitting a release path via intake."""

    source: str
    path: str
    name: str | None = None
    preset: str | None = None
    profile: str | None = None
    dedup_key: str | None = None
    metadata: dict[str, Any] | None = None


# Sample data used by both webhook test endpoints so templates render with visible values.
_WEBHOOK_TEST_DATA: dict[str, Any] = {
    "module": "pipeline",
    "args_text": "--input example.mkv",
    "job_id": "test-job-123",
    "returncode": 0,
    "ok": True,
    "path": r"E:\Example\Movie.mkv",
}


class AuthLoginRequest(BaseModel):
    """Request payload for user login."""

    username: str
    password: str


class AuthSetupRequest(BaseModel):
    """Request payload for first-run admin setup."""

    username: str
    password: str


class AuthCreateUserRequest(BaseModel):
    """Request payload for admin user creation."""

    username: str
    password: str
    role: str = "viewer"


class AuthChangePasswordRequest(BaseModel):
    """Request payload for password change."""

    new_password: str


_user_store: UserStore | None = None


def _get_user_store() -> UserStore:
    global _user_store  # noqa: PLW0603
    if _user_store is None:
        _user_store = UserStore()
    return _user_store


def _is_auth_active() -> bool:
    """Return True when at least one user exists (auth-enabled mode)."""
    return _get_user_store().count() > 0


def _get_current_user(request: Any) -> dict[str, Any] | None:
    """Extract and validate Bearer token from request. Returns payload or None."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    try:
        return decode_access_token(token)
    except (TokenError, Exception):
        return None


def _require_auth(request: Any) -> dict[str, Any]:
    """Raise 401 if request has no valid token. Returns payload."""
    payload = _get_current_user(request)
    if payload is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return payload


def _require_admin(request: Any) -> dict[str, Any]:
    """Raise 401/403 if request is not from an admin user."""
    payload = _require_auth(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def _intake_auth_check(request: Any, source_id: str) -> None:
    """Validate intake request auth: intake token OR valid JWT.

    When auth is disabled (no users), every request is accepted.
    Raises ``HTTPException(401)`` if auth is active and neither credential is valid.
    """
    if not _is_auth_active():
        return
    # Accept valid JWT session token.
    if _get_current_user(request) is not None:
        return
    # Accept intake-source token from Authorization header.
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        if verify_intake_token(source_id, token):
            return
    raise HTTPException(
        status_code=401,
        detail="Valid intake token or session required",
    )


def _resolve_version() -> str:
    for distribution_name in ("framekit-cli", "framekit"):
        try:
            return importlib_metadata.version(distribution_name)
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:  # nosec B112
            continue

    try:
        from framekit import __version__

        return __version__
    except Exception:
        return "unknown"


def create_app() -> FastAPI:
    """Create FastAPI app exposing Framekit web endpoints."""
    app = FastAPI(title="Framekit Web API", version=_resolve_version())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _ALWAYS_OPEN = frozenset({
        "/healthz",
        "/api/v1/system/info",
        "/api/v1/auth/status",
        "/api/v1/auth/login",
        "/api/v1/auth/setup",
        "/docs",
        "/openapi.json",
        "/redoc",
    })

    # Intake submit paths bypass JWT auth — each handler validates intake token or JWT itself.
    # Uses a precise regex so only the two submit routes are exempt; future /intake/* routes
    # (e.g. admin CRUD) still go through the normal JWT guard.
    _INTAKE_SUBMIT_RE = re.compile(r"^/api/v1/intake/(release|webhook/[^/]+)$")

    @app.middleware("http")
    async def enforce_auth(request: Request, call_next):  # type: ignore[return]
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in _ALWAYS_OPEN or path.startswith("/api/v1/auth/"):
            return await call_next(request)
        if _INTAKE_SUBMIT_RE.match(path):
            return await call_next(request)
        # Non-API paths (static assets, SPA routes) bypass server-side auth.
        # The React app handles client-side auth state and redirects to /login.
        if not path.startswith("/api/"):
            return await call_next(request)
        if _is_auth_active() and _get_current_user(request) is None:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/service/status")
    def service_status() -> dict[str, Any]:
        """Return running/stopped status of the Framekit service process.

        Guards against stale state files left by unclean shutdown via two checks:
          1. Heartbeat staleness: heartbeat_at older than 3× interval → stopped.
          2. PID liveness: os.kill(pid, 0) raises ProcessLookupError → stopped.
        """
        import os as _os
        import time as _time

        from framekit.core.paths import get_service_dir
        from framekit.core.service.supervisor import ServiceSupervisor

        _stopped: dict[str, Any] = {
            "status": "stopped",
            "pid": None,
            "started_at": None,
            "heartbeat_at": None,
            "uptime_seconds": None,
        }

        state = ServiceSupervisor(get_service_dir()).read_state()
        if state is None or state.get("status") not in {"starting", "running"}:
            return _stopped

        # Staleness check: heartbeat older than 3× interval indicates crashed process.
        heartbeat_at: float | None = state.get("heartbeat_at")
        stale_threshold = ServiceSupervisor.HEARTBEAT_INTERVAL_S * 3  # 30 s
        if heartbeat_at is not None and (_time.time() - heartbeat_at) > stale_threshold:
            return _stopped

        # PID liveness check: signal 0 = existence probe, no actual signal sent.
        pid: int | None = state.get("pid")
        if pid is not None:
            try:
                _os.kill(pid, 0)
            except ProcessLookupError:
                # Process is gone — state file is stale.
                return _stopped
            except (PermissionError, OSError):
                # Process exists but we lack permission to signal it — treat as running.
                pass

        started_at: float | None = state.get("started_at")
        uptime = round(_time.time() - started_at, 1) if started_at else None
        return {
            "status": state.get("status", "running"),
            "pid": pid,
            "started_at": started_at,
            "heartbeat_at": heartbeat_at,
            "uptime_seconds": uptime,
            "watcher": get_embedded_watcher_state(),
        }

    @app.post("/api/v1/service/reload")
    def service_reload() -> dict[str, Any]:
        """Reload embedded watcher settings without restarting the service.

        Stops the running embedded watcher (if any), then re-reads
        ``settings.watch.folders`` and restarts it.  This is a no-op and
        returns ``{"ok": true}`` when no service supervisor is active.
        """
        stop_embedded_watcher()
        start_embedded_watcher()
        return {"ok": True, "watcher": get_embedded_watcher_state()}

    # ── Intake API ───────────────────────────────────────────────────────────

    @app.get("/api/v1/intake/sources")
    def intake_list_sources(request: Request) -> dict[str, Any]:
        """List all configured intake sources (tokens not included). Admin-only."""
        if _is_auth_active():
            _require_admin(request)
        return {"sources": list_intake_sources()}

    @app.post("/api/v1/intake/sources")
    def intake_create_source(req: IntakeSourceCreateRequest, request: Request) -> dict[str, Any]:
        """Create an intake source.  Returns the token once — store it securely."""
        if _is_auth_active():
            _require_admin(request)
        try:
            return create_intake_source(
                req.name,
                req.source_id,
                default_preset=req.default_preset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/intake/sources/{source_id}")
    def intake_delete_source(source_id: str, request: Request) -> dict[str, Any]:
        """Delete an intake source and revoke its token."""
        if _is_auth_active():
            _require_admin(request)
        try:
            return delete_intake_source(source_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/intake/release")
    def intake_submit_release(req: IntakeReleaseRequest, request: Request) -> dict[str, Any]:
        """Submit a release path for pipeline processing.

        Authentication: ``Authorization: Bearer <intake_token>`` for the given
        ``source`` field, OR a valid JWT session token.  When auth is disabled
        (no users configured), any request is accepted.
        """
        _intake_auth_check(request, req.source)
        try:
            return submit_intake_release(
                req.source,
                req.path,
                preset=req.preset,
                dedup_key=req.dedup_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/intake/webhook/{source_id}")
    def intake_webhook(source_id: str, req: IntakeReleaseRequest, request: Request) -> dict[str, Any]:
        """Alias for ``POST /api/v1/intake/release`` with source taken from the URL path.

        ``source_id`` in the URL is the authoritative identity for both auth
        validation and job submission — ``req.source`` in the body is ignored on
        this route to prevent a source-spoofing attack where a caller authenticates
        with token A but submits a body claiming source B.
        """
        _intake_auth_check(request, source_id)
        try:
            return submit_intake_release(
                source_id,  # URL param is authoritative — body req.source ignored
                req.path,
                preset=req.preset,
                dedup_key=req.dedup_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/system/info")
    def system_info() -> dict[str, str]:
        return {
            "name": "framekit",
            "version": _resolve_version(),
            "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        }

    @app.get("/api/v1/doctor")
    def doctor() -> dict[str, Any]:
        return collect_doctor_payload()

    @app.get("/api/v1/modules/catalog")
    def modules_catalog() -> dict[str, Any]:
        return {"modules": list_modules()}

    @app.get("/api/v1/modules/spec")
    def modules_spec() -> dict[str, Any]:
        return list_modules_spec()

    @app.get("/api/v1/modules/presets")
    def modules_presets() -> dict[str, Any]:
        return {"presets": list_presets()}

    @app.get("/api/v1/modules/resources")
    def modules_resources() -> dict[str, Any]:
        return list_pipeline_batch_resources()

    @app.get("/api/v1/settings/summary")
    def settings_summary() -> dict[str, Any]:
        return get_settings_summary()

    @app.post("/api/v1/settings/patch")
    def settings_patch(request: SettingsPatchRequest) -> dict[str, Any]:
        try:
            return patch_settings_values(request.changes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/seedbox/list")
    def seedbox_list() -> dict[str, Any]:
        return {"seedboxes": list_seedboxes_summary(), "default_by_profile": get_seedbox_default_by_profile()}

    @app.post("/api/v1/seedbox/add")
    def seedbox_add(request: SeedboxCreateRequest) -> dict[str, Any]:
        try:
            return {
                "seedboxes": create_seedbox_profile(
                    name=request.name,
                    rclone_remote=request.rclone_remote,
                    remote_base_path=request.remote_base_path,
                    max_concurrent_uploads=request.max_concurrent_uploads,
                    bandwidth_limit=request.bandwidth_limit,
                    set_default=request.set_default,
                )
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/seedbox/use")
    def seedbox_use(request: SeedboxNameRequest) -> dict[str, Any]:
        try:
            return {
                "seedboxes": set_default_seedbox(request.name, profile_name=request.profile_name),
                "default_by_profile": get_seedbox_default_by_profile(),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/seedbox/remove")
    def seedbox_remove(request: SeedboxNameRequest) -> dict[str, Any]:
        try:
            return {"seedboxes": remove_seedbox_profile(request.name)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/upload/trackers")
    def upload_trackers() -> dict[str, Any]:
        return {"trackers": list_upload_trackers_summary()}

    @app.get("/api/v1/upload/tracker/{tracker_name}")
    def upload_tracker(tracker_name: str) -> dict[str, Any]:
        info = get_upload_tracker_info(tracker_name)
        if info is None:
            raise HTTPException(status_code=404, detail="tracker not found")
        return {"tracker": info}

    @app.get("/api/v1/upload/state")
    def upload_state() -> dict[str, Any]:
        return get_upload_state()

    @app.post("/api/v1/upload/state")
    def update_upload_state(request: UploadStateRequest) -> dict[str, Any]:
        return set_upload_state(enabled=request.enabled, auto_upload=request.auto_upload)

    @app.get("/api/v1/upload/history")
    def upload_history(limit: int = 20) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
        return {"entries": list_upload_history(limit=limit)}

    @app.get("/api/v1/seedbox/history")
    def seedbox_history(limit: int = 50, seedbox_name: str | None = None) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
        return {"entries": list_seedbox_history(limit=limit, seedbox_name=seedbox_name)}

    @app.get("/api/v1/logs/read")
    def logs_read(lines: int = 200, level: str | None = None) -> dict[str, Any]:
        if lines < 1 or lines > 5000:
            raise HTTPException(status_code=400, detail="lines must be between 1 and 5000")
        return {"entries": read_log_lines(lines=lines, level=level or None)}

    @app.post("/api/v1/modules/run")
    def run_module(request: RunModuleRequest) -> dict[str, Any]:
        try:
            return run_module_command(request).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/modules/jobs")
    def create_module_job(request: RunModuleRequest) -> dict[str, Any]:
        try:
            return enqueue_module_job(request).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/runs")
    def list_runs(limit: int = 50) -> dict[str, Any]:
        if limit < 1 or limit > 200:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
        return {"runs": list_runs_from_ledger(limit=limit)}

    @app.get("/api/v1/modules/jobs")
    def list_jobs(limit: int = 20) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
        return {"jobs": [item.model_dump() for item in list_module_jobs(limit=limit)]}

    @app.get("/api/v1/modules/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = get_module_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.model_dump()

    @app.delete("/api/v1/modules/jobs")
    def clear_jobs() -> dict[str, Any]:
        return {"deleted": clear_module_jobs()}

    @app.delete("/api/v1/modules/jobs/{job_id}")
    def cancel_job(job_id: str) -> dict[str, Any]:
        job = cancel_module_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.model_dump()

    @app.post("/api/v1/modules/jobs/{job_id}/rerun")
    def rerun_job(job_id: str) -> dict[str, Any]:
        job = rerun_module_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job.model_dump()

    @app.get("/api/v1/security/vault")
    def security_vault() -> dict[str, Any]:
        return get_vault_status_info()

    @app.get("/api/v1/settings/tmdb-token")
    def tmdb_token_get() -> dict[str, Any]:
        return get_tmdb_token_value()

    @app.post("/api/v1/settings/tmdb-token")
    def tmdb_token_set(request: TmdbTokenRequest) -> dict[str, Any]:
        try:
            return set_tmdb_token_value(request.token)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/settings/provider-token/{provider}")
    def provider_token_get(provider: str) -> dict[str, Any]:
        try:
            return get_provider_token_value(provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/settings/provider-token/{provider}")
    def provider_token_set(provider: str, request: ProviderTokenRequest) -> dict[str, Any]:
        try:
            return set_provider_token_value(provider, request.token)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/torrent/announces")
    def torrent_announces_list() -> dict[str, Any]:
        return list_torrent_announces_info()

    @app.post("/api/v1/torrent/announces")
    def torrent_announces_add(request: AnnounceAddRequest) -> dict[str, Any]:
        try:
            return add_torrent_announce_url(request.url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/torrent/announces/{index}")
    def torrent_announces_remove(index: int) -> dict[str, Any]:
        try:
            return remove_torrent_announce_url(index)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/torrent/announces/select")
    def torrent_announces_select(request: AnnounceSelectRequest) -> dict[str, Any]:
        try:
            return select_torrent_announce_url(request.url)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/v1/torrent/announces/{index}")
    def torrent_announces_rename(index: int, request: AnnounceRenameRequest) -> dict[str, Any]:
        try:
            return rename_torrent_announce_label(index, request.label)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/upload/image-host-key/{host}")
    def image_host_key_get(host: str) -> dict[str, Any]:
        try:
            return get_image_host_key(host)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/upload/image-host-key/{host}")
    def image_host_key_set(host: str, request: ImageHostKeyRequest) -> dict[str, Any]:
        try:
            return set_image_host_key(host, request.key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/upload/torrent-client-password")
    def torrent_client_password_get() -> dict[str, Any]:
        return get_torrent_client_password()

    @app.post("/api/v1/upload/torrent-client-password")
    def torrent_client_password_set(request: TorrentClientPasswordRequest) -> dict[str, Any]:
        return set_torrent_client_password(request.password)

    @app.post("/api/v1/presets/{kind}")
    def preset_create(kind: str, request: PresetCreateRequest) -> dict[str, Any]:
        try:
            return create_yaml_preset(kind, request.name, request.content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/presets/{kind}/all")
    def preset_delete_all(kind: str) -> dict[str, Any]:
        try:
            return delete_all_yaml_presets(kind)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/presets/{kind}/{name}")
    def preset_delete(kind: str, name: str) -> dict[str, Any]:
        try:
            return delete_yaml_preset(kind, name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/watch/folders")
    def watch_folders_list() -> dict[str, Any]:
        return {"folders": list_watch_folders()}

    @app.post("/api/v1/watch/folders")
    def watch_folders_add(request: WatchFolderAddRequest) -> dict[str, Any]:
        try:
            return {"folders": add_watch_folder(request.path, request.preset)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/watch/folders/{index}")
    def watch_folders_remove(index: int) -> dict[str, Any]:
        try:
            return {"folders": remove_watch_folder(index)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/watch/service")
    def watch_service_status() -> dict[str, Any]:
        return get_watch_service_status()

    @app.post("/api/v1/watch/service/start")
    def watch_service_start() -> dict[str, Any]:
        """Spawn the watch daemon.

        When the embedded watcher is running (service mode via ``framekit serve``),
        returns 409 — the service process owns the watch lifecycle and the Web UI
        cannot spawn a competing subprocess watcher.

        When no service is active (ephemeral/dev mode), falls back to the legacy
        2 h background-job spawn so existing behaviour is preserved.
        """
        # Service-mode guard: refuse if embedded watcher is already running.
        watcher_state = get_embedded_watcher_state()
        if watcher_state.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Watch is managed by the service process. "
                    "The embedded watcher is already running — no action needed."
                ),
            )

        try:
            job = enqueue_module_job(
                RunModuleRequest(
                    module="watch",
                    args_text="start --all --no-status-updates",
                    dry_run=False,
                    auto_yes=True,
                    confirm_destructive=True,
                    timeout_seconds=7200,
                )
            )
            return job.model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/watch/service/stop")
    def watch_service_stop() -> dict[str, Any]:
        return stop_watch_service()

    @app.get("/api/v1/profiles")
    def profiles_list() -> dict[str, Any]:
        return list_settings_profiles()

    @app.post("/api/v1/profiles/activate")
    def profiles_activate(request: ProfileActivateRequest) -> dict[str, Any]:
        try:
            return activate_settings_profile(request.name)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/profiles/deactivate")
    def profiles_deactivate() -> dict[str, Any]:
        return deactivate_settings_profile()

    @app.post("/api/v1/profiles")
    def profiles_create(request: ProfileCreateRequest) -> dict[str, Any]:
        try:
            return create_settings_profile(request.name, request.description, request.overrides)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/profiles/{name}")
    def profiles_delete(name: str) -> dict[str, Any]:
        try:
            return delete_settings_profile(name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/tools/check")
    def tools_check() -> dict[str, Any]:
        return check_tools()

    @app.get("/api/v1/aliases")
    def aliases_list() -> dict[str, Any]:
        return {"aliases": list_aliases_summary()}

    @app.post("/api/v1/aliases")
    def aliases_add(request: AliasCreateRequest) -> dict[str, Any]:
        try:
            return {"aliases": add_alias_entry(request.name, request.command, request.description, request.enabled)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/v1/aliases/{name}")
    def aliases_remove(name: str) -> dict[str, Any]:
        try:
            return {"aliases": remove_alias_entry(name)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/aliases/{name}/enable")
    def aliases_enable(name: str) -> dict[str, Any]:
        try:
            return {"aliases": enable_alias_entry(name)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/aliases/{name}/disable")
    def aliases_disable(name: str) -> dict[str, Any]:
        try:
            return {"aliases": disable_alias_entry(name)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    @app.get("/api/v1/webhooks")
    def webhooks_list() -> dict[str, Any]:
        return {"webhooks": [w.to_dict() for w in load_webhooks()]}

    @app.post("/api/v1/webhooks")
    def webhooks_add(request: WebhookCreateRequest) -> dict[str, Any]:
        try:
            webhooks = add_webhook(
                name=request.name,
                url=request.url,
                discord=request.discord,
                events=request.events,
                title_template=request.title_template,
                body_template=request.body_template,
            )
            return {"webhooks": [w.to_dict() for w in webhooks]}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/webhooks/test")
    def webhooks_test_payload(request: WebhookTestPayloadRequest) -> dict[str, Any]:
        from framekit.core.webhooks import _build_discord_payload, _build_generic_payload, _validate_template  # noqa: PLC0415
        url = request.url.strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
        # Normalize and validate templates
        title_template = request.title_template.strip() or None
        body_template = request.body_template.strip() or None
        try:
            if title_template:
                _validate_template(title_template)
            if body_template:
                _validate_template(body_template)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        event = "job.completed"
        data = _WEBHOOK_TEST_DATA
        payload = (
            _build_discord_payload(event, data, title_template=title_template, body_template=body_template)
            if request.discord
            else _build_generic_payload(event, data)
        )
        try:
            import httpx  # noqa: PLC0415
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload, headers={"Content-Type": "application/json", "User-Agent": "Framekit/2.0"})
                if resp.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"Webhook returned HTTP {resp.status_code}: {resp.text[:300]}")
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Request failed: {exc}") from exc
        return {"ok": True}

    @app.patch("/api/v1/webhooks/{webhook_id}")
    def webhooks_update(webhook_id: str, request: WebhookUpdateRequest) -> dict[str, Any]:
        try:
            webhooks = update_webhook(
                webhook_id,
                enabled=request.enabled,
                name=request.name,
                url=request.url,
                discord=request.discord,
                events=request.events,
                title_template=request.title_template,
                body_template=request.body_template,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"webhooks": [w.to_dict() for w in webhooks]}

    @app.delete("/api/v1/webhooks/{webhook_id}")
    def webhooks_delete(webhook_id: str) -> dict[str, Any]:
        webhooks = remove_webhook(webhook_id)
        return {"webhooks": [w.to_dict() for w in webhooks]}

    @app.post("/api/v1/webhooks/{webhook_id}/test")
    def webhooks_test(webhook_id: str) -> dict[str, Any]:
        from framekit.core.webhooks import _build_discord_payload, _build_generic_payload  # noqa: PLC0415
        whs = [w for w in load_webhooks() if w.id == webhook_id]
        if not whs:
            raise HTTPException(status_code=404, detail="Webhook not found")
        wh = whs[0]
        event = "job.completed"
        data = _WEBHOOK_TEST_DATA
        payload = (
            _build_discord_payload(event, data, title_template=wh.title_template, body_template=wh.body_template)
            if wh.discord
            else _build_generic_payload(event, data)
        )
        try:
            import httpx  # noqa: PLC0415
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(wh.url, json=payload, headers={"Content-Type": "application/json", "User-Agent": "Framekit/2.0"})
                if resp.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"Webhook returned HTTP {resp.status_code}: {resp.text[:300]}")
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Request failed: {exc}") from exc
        return {"ok": True}

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    @app.get("/api/v1/auth/status")
    def auth_status() -> dict[str, Any]:
        store = _get_user_store()
        return {"enabled": True, "has_users": store.count() > 0, "user_count": store.count()}

    @app.post("/api/v1/auth/setup")
    def auth_setup(request: AuthSetupRequest) -> dict[str, Any]:
        """First-run admin setup — only works when no users exist."""
        store = _get_user_store()
        if store.count() > 0:
            raise HTTPException(status_code=409, detail="Setup already complete")
        try:
            user = store.create(username=request.username, password=request.password, role=UserRole.ADMIN)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
        return {"access_token": token, "token_type": "bearer", "user": user.to_public_dict()}

    @app.post("/api/v1/auth/login")
    def auth_login(request: AuthLoginRequest) -> dict[str, Any]:
        store = _get_user_store()
        user = store.authenticate(username=request.username, password=request.password)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
        return {"access_token": token, "token_type": "bearer", "user": user.to_public_dict()}

    @app.get("/api/v1/auth/me")
    def auth_me(req: Request) -> dict[str, Any]:
        payload = _require_auth(req)
        store = _get_user_store()
        user = store.get_by_id(payload["sub"])
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user.to_public_dict()

    @app.get("/api/v1/auth/users")
    def auth_users_list(req: Request) -> dict[str, Any]:
        _require_admin(req)
        store = _get_user_store()
        return {"users": [u.to_public_dict() for u in store.list_users()]}

    @app.post("/api/v1/auth/users")
    def auth_users_create(request: AuthCreateUserRequest, req: Request) -> dict[str, Any]:
        _require_admin(req)
        store = _get_user_store()
        try:
            role = UserRole(request.role) if request.role in ("admin", "viewer") else UserRole.VIEWER
            user = store.create(username=request.username, password=request.password, role=role)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return user.to_public_dict()

    @app.delete("/api/v1/auth/users/{user_id}")
    def auth_users_delete(user_id: str, req: Request) -> dict[str, Any]:
        payload = _require_admin(req)
        if payload.get("sub") == user_id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        store = _get_user_store()
        if not store.delete(user_id):
            raise HTTPException(status_code=404, detail="User not found")
        return {"ok": True}

    @app.post("/api/v1/auth/users/{user_id}/enable")
    def auth_users_enable(user_id: str, req: Request) -> dict[str, Any]:
        _require_admin(req)
        if not _get_user_store().set_enabled(user_id, enabled=True):
            raise HTTPException(status_code=404, detail="User not found")
        return {"ok": True}

    @app.post("/api/v1/auth/users/{user_id}/disable")
    def auth_users_disable(user_id: str, req: Request) -> dict[str, Any]:
        payload = _require_admin(req)
        if payload.get("sub") == user_id:
            raise HTTPException(status_code=400, detail="Cannot disable your own account")
        if not _get_user_store().set_enabled(user_id, enabled=False):
            raise HTTPException(status_code=404, detail="User not found")
        return {"ok": True}

    @app.post("/api/v1/auth/users/{user_id}/password")
    def auth_users_password(user_id: str, request: AuthChangePasswordRequest, req: Request) -> dict[str, Any]:
        payload = _require_auth(req)
        # Admins can change any password; regular users only their own
        if payload.get("role") != "admin" and payload.get("sub") != user_id:
            raise HTTPException(status_code=403, detail="Cannot change another user's password")
        try:
            if not _get_user_store().change_password(user_id, request.new_password):
                raise HTTPException(status_code=404, detail="User not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    # ── Static / SPA serving ─────────────────────────────────────────────────
    # Registered last so every /api/v1/* route takes priority.

    _dist_resolved = _resolve_frontend_dist_dir()

    if _dist_resolved is not None:

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:  # type: ignore[return]
            """Serve built frontend assets or fall back to index.html for SPA routing.

            Security: resolves the candidate path and verifies it stays inside
            dist directory before serving, preventing path-traversal.
            """
            # Undefined /api/* sub-paths should 404, not silently serve the SPA.
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")

            candidate = _dist_resolved / full_path
            try:
                resolved = candidate.resolve()
                if not resolved.is_relative_to(_dist_resolved):
                    raise HTTPException(status_code=400, detail="Bad request")
                if resolved.is_file():
                    return FileResponse(resolved)
            except (ValueError, OSError):
                pass  # fall through to index.html

            index = _dist_resolved / "index.html"
            if index.exists():
                return FileResponse(index)
            raise HTTPException(status_code=404, detail="index.html not found in dist")

    else:

        @app.get("/", include_in_schema=False)
        async def no_ui() -> JSONResponse:
            """Inform users the Web UI is not built yet."""
            return JSONResponse({
                "message": "Framekit API is running. Web UI has not been built.",
                "hint": (
                    "Run 'npm run build' from the repository root to build and copy UI assets. "
                    "If this is an installed package, reinstall with bundled web assets."
                ),
                "api_docs": "/docs",
            })

    return app


app = create_app()
