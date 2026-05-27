from __future__ import annotations

import sys
from importlib import metadata as importlib_metadata
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
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
    get_watch_service_status,
    stop_watch_service,
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

    @app.middleware("http")
    async def enforce_auth(request: Request, call_next):  # type: ignore[return]
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in _ALWAYS_OPEN or path.startswith("/api/v1/auth/"):
            return await call_next(request)
        if _is_auth_active() and _get_current_user(request) is None:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

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
        """Spawn the watch daemon as a background module job (2 h max)."""
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

    return app


app = create_app()
