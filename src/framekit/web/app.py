from __future__ import annotations

import sys
from importlib import metadata as importlib_metadata
from typing import Any

from fastapi import FastAPI, HTTPException

from framekit.commands.doctor import collect_doctor_payload
from framekit.web.modules import (
    RunModuleRequest,
    cancel_module_job,
    enqueue_module_job,
    get_module_job,
    list_module_jobs,
    list_modules,
    list_presets,
    rerun_module_job,
    run_module_command,
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
