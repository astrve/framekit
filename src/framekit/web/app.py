from __future__ import annotations

import sys
from importlib import metadata as importlib_metadata
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from framekit.commands.doctor import collect_doctor_payload
from framekit.web.modules import (
    RunModuleRequest,
    cancel_module_job,
    enqueue_module_job,
    get_module_job,
    get_settings_summary,
    create_seedbox_profile,
    patch_settings_values,
    remove_seedbox_profile,
    set_default_seedbox,
    get_upload_state,
    list_seedbox_history,
    list_module_jobs,
    list_modules,
    list_presets,
    list_seedboxes_summary,
    list_upload_history,
    list_upload_trackers_summary,
    rerun_module_job,
    run_module_command,
    set_upload_state,
)


class UploadStateRequest(BaseModel):
    enabled: bool
    auto_upload: bool | None = None


class SettingsPatchRequest(BaseModel):
    changes: dict[str, Any]


class SeedboxCreateRequest(BaseModel):
    name: str
    rclone_remote: str
    remote_base_path: str
    max_concurrent_uploads: int | None = None
    bandwidth_limit: str = ""
    set_default: bool = False


class SeedboxNameRequest(BaseModel):
    name: str


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

    @app.get("/api/v1/modules/presets")
    def modules_presets() -> dict[str, Any]:
        return {"presets": list_presets()}

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
        return {"seedboxes": list_seedboxes_summary()}

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
            return {"seedboxes": set_default_seedbox(request.name)}
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

    return app


app = create_app()
