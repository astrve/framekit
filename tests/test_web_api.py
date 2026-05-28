from __future__ import annotations

from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

from framekit.web.app import create_app


@pytest.fixture(autouse=True)
def _open_access_mode(monkeypatch: MonkeyPatch) -> None:
    """Run all web API tests as if no users are registered (open-access mode).

    Patches _is_auth_active to False so middleware never blocks requests with 401.
    Auth-specific tests that need auth active must override this with their own patch.
    """
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)


def test_healthz_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_system_info_shape() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/system/info")
    payload = response.json()

    assert response.status_code == 200
    assert payload["name"] == "framekit"
    assert isinstance(payload["version"], str)
    assert isinstance(payload["python_version"], str)


def test_doctor_endpoint_returns_tools_and_checks(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.collect_doctor_payload",
        lambda: {
            "tools": [{"name": "ffmpeg", "found": True}],
            "checks": [{"section": "Runtime", "name": "python", "status": "ok", "detail": "3.12"}],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/v1/doctor")
    payload = response.json()

    assert response.status_code == 200
    assert "tools" in payload
    assert "checks" in payload
    assert isinstance(payload["checks"], list)


def test_modules_catalog_contains_known_module() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/modules/catalog")
    payload = response.json()

    assert response.status_code == 200
    assert any(item["name"] == "inspect" for item in payload["modules"])


def test_modules_presets_returns_entries() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/modules/presets")
    payload = response.json()

    assert response.status_code == 200
    assert any(item["id"] == "doctor-json" for item in payload["presets"])


def test_modules_spec_returns_cli_shapes() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/modules/spec")
    payload = response.json()

    assert response.status_code == 200
    assert "modules" in payload
    inspect_module = next((item for item in payload["modules"] if item["name"] == "inspect"), None)
    assert inspect_module is not None
    assert "parameters" in inspect_module
    assert isinstance(inspect_module["parameters"], list)


def test_modules_resources_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.list_pipeline_batch_resources",
        lambda: {
            "pipeline_presets": [{"name": "multi_fr", "path": "x", "source": "bundled"}],
            "prez_presets": [{"name": "default", "path": "y", "source": "bundled"}],
            "announces": [{"value": "https://tracker/announce", "is_selected": True}],
            "selected_announce": "https://tracker/announce",
            "nfo_templates": ["movie_default"],
            "prez_templates": {"bbcode": ["classic"], "html": ["magazine_dark"]},
            "banner_previews": [{"name": "textual_blue", "preview_url": "https://example.test/banner.png"}],
        },
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/modules/resources")
    payload = response.json()

    assert response.status_code == 200
    assert payload["pipeline_presets"][0]["name"] == "multi_fr"
    assert payload["announces"][0]["is_selected"] is True


def test_settings_summary_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.get_settings_summary",
        lambda: {
            "settings_path": "C:/cfg/framekit.yaml",
            "config_dir": "C:/cfg",
            "cache_dir": "C:/cache",
            "settings": {"general": {"locale": "fr"}},
        },
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/settings/summary")
    payload = response.json()

    assert response.status_code == 200
    assert payload["settings_path"].endswith("framekit.yaml")
    assert payload["settings"]["general"]["locale"] == "fr"


def test_settings_patch_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.patch_settings_values",
        lambda changes: {
            "settings_path": "C:/cfg/framekit.yaml",
            "config_dir": "C:/cfg",
            "cache_dir": "C:/cache",
            "settings": {"general": {"locale": changes.get("general.locale", "fr")}},
        },
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/settings/patch",
        json={"changes": {"general.locale": "en"}},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["settings"]["general"]["locale"] == "en"


def test_settings_patch_endpoint_returns_400_on_unsupported_key(monkeypatch: MonkeyPatch) -> None:
    def _raise(_changes: dict[str, object]) -> dict[str, object]:
        raise ValueError("Unsupported settings key: foo.bar")

    monkeypatch.setattr("framekit.web.app.patch_settings_values", _raise)
    client = TestClient(create_app())
    response = client.post("/api/v1/settings/patch", json={"changes": {"foo.bar": "x"}})
    payload = response.json()

    assert response.status_code == 400
    assert payload["detail"] == "Unsupported settings key: foo.bar"


def test_seedbox_list_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.list_seedboxes_summary",
        lambda: [
            {
                "name": "main-seedbox",
                "rclone_remote": "main",
                "remote_base_path": "/downloads",
                "max_concurrent_uploads": 3,
                "bandwidth_limit": "",
                "is_default": True,
            }
        ],
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/seedbox/list")
    payload = response.json()

    assert response.status_code == 200
    assert payload["seedboxes"][0]["name"] == "main-seedbox"
    assert payload["seedboxes"][0]["is_default"] is True


def test_seedbox_add_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.create_seedbox_profile",
        lambda **kwargs: [
            {
                "name": kwargs["name"],
                "rclone_remote": kwargs["rclone_remote"],
                "remote_base_path": kwargs["remote_base_path"],
                "max_concurrent_uploads": kwargs.get("max_concurrent_uploads", 3),
                "bandwidth_limit": kwargs.get("bandwidth_limit", ""),
                "is_default": kwargs.get("set_default", False),
            }
        ],
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/seedbox/add",
        json={
            "name": "main",
            "rclone_remote": "main-remote",
            "remote_base_path": "/downloads",
            "max_concurrent_uploads": 3,
            "set_default": True,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["seedboxes"][0]["name"] == "main"
    assert payload["seedboxes"][0]["is_default"] is True


def test_seedbox_add_endpoint_returns_400_on_validation_error(monkeypatch: MonkeyPatch) -> None:
    def _raise(**_kwargs: object) -> list[dict[str, object]]:
        raise ValueError("invalid seedbox")

    monkeypatch.setattr("framekit.web.app.create_seedbox_profile", _raise)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/seedbox/add",
        json={
            "name": "",
            "rclone_remote": "",
            "remote_base_path": "/",
        },
    )
    payload = response.json()

    assert response.status_code == 400
    assert payload["detail"] == "invalid seedbox"


def test_seedbox_use_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.set_default_seedbox",
        lambda name, profile_name=None: [
            {
                "name": name,
                "rclone_remote": "remote",
                "remote_base_path": "/",
                "max_concurrent_uploads": 3,
                "bandwidth_limit": "",
                "is_default": True,
            }
        ],
    )
    monkeypatch.setattr("framekit.web.app.get_seedbox_default_by_profile", lambda: {})
    client = TestClient(create_app())
    response = client.post("/api/v1/seedbox/use", json={"name": "main"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["seedboxes"][0]["name"] == "main"
    assert payload["seedboxes"][0]["is_default"] is True


def test_seedbox_remove_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("framekit.web.app.remove_seedbox_profile", lambda name: [])
    client = TestClient(create_app())
    response = client.post("/api/v1/seedbox/remove", json={"name": "legacy"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["seedboxes"] == []


def test_upload_trackers_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.list_upload_trackers_summary",
        lambda: [
            {
                "name": "bhd",
                "type": "unit3d",
                "url": "https://example.test",
                "enabled": True,
            }
        ],
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/upload/trackers")
    payload = response.json()

    assert response.status_code == 200
    assert payload["trackers"][0]["name"] == "bhd"


def test_upload_tracker_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.get_upload_tracker_info",
        lambda tracker_name: {"name": tracker_name, "type": "unit3d", "url": "https://example.test"},
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/upload/tracker/bhd")
    payload = response.json()

    assert response.status_code == 200
    assert payload["tracker"]["name"] == "bhd"


def test_upload_state_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.get_upload_state",
        lambda: {"enabled": True, "auto_upload": False},
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/upload/state")
    payload = response.json()

    assert response.status_code == 200
    assert payload["enabled"] is True
    assert payload["auto_upload"] is False


def test_upload_state_update_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.set_upload_state",
        lambda enabled, auto_upload=None: {"enabled": enabled, "auto_upload": bool(auto_upload)},
    )
    client = TestClient(create_app())
    response = client.post("/api/v1/upload/state", json={"enabled": True, "auto_upload": True})
    payload = response.json()

    assert response.status_code == 200
    assert payload["enabled"] is True
    assert payload["auto_upload"] is True


def test_upload_history_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.list_upload_history",
        lambda limit=20: [{"tracker": "bhd", "success": True, "limit": limit}],
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/upload/history?limit=12")
    payload = response.json()

    assert response.status_code == 200
    assert payload["entries"][0]["tracker"] == "bhd"
    assert payload["entries"][0]["limit"] == 12


def test_seedbox_history_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.list_seedbox_history",
        lambda limit=50, seedbox_name=None: [{"seedbox": seedbox_name or "default", "limit": limit}],
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/seedbox/history?limit=25&seedbox_name=main")
    payload = response.json()

    assert response.status_code == 200
    assert payload["entries"][0]["seedbox"] == "main"
    assert payload["entries"][0]["limit"] == 25


def test_modules_run_endpoint_returns_payload(monkeypatch: MonkeyPatch) -> None:
    class ResponseStub:
        def model_dump(self) -> dict[str, object]:
            return {
                "ok": True,
                "argv": ["python", "-m", "framekit", "inspect"],
                "returncode": 0,
                "stdout": "ok",
                "stderr": "",
                "parsed_kind": None,
                "parsed_payload": None,
            }

    monkeypatch.setattr(
        "framekit.web.app.run_module_command",
        lambda _request: ResponseStub(),
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/modules/run",
        json={
            "module": "inspect",
            "args_text": "C:/demo",
            "dry_run": True,
            "auto_yes": False,
            "confirm_destructive": False,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["returncode"] == 0
    assert payload["parsed_kind"] is None


def test_modules_jobs_create_and_get(monkeypatch: MonkeyPatch) -> None:
    class JobStub:
        def model_dump(self) -> dict[str, object]:
            return {
                "id": "job-1",
                "status": "pending",
                "created_at": "2026-05-24T16:00:00+00:00",
                "started_at": None,
                "finished_at": None,
                "request": {"module": "inspect"},
                "result": None,
                "error": None,
            }

    monkeypatch.setattr("framekit.web.app.enqueue_module_job", lambda _request: JobStub())
    monkeypatch.setattr("framekit.web.app.get_module_job", lambda _job_id: JobStub())

    client = TestClient(create_app())
    create_response = client.post(
        "/api/v1/modules/jobs",
        json={
            "module": "inspect",
            "args_text": "C:/demo",
            "dry_run": False,
            "auto_yes": False,
            "confirm_destructive": False,
        },
    )
    get_response = client.get("/api/v1/modules/jobs/job-1")

    assert create_response.status_code == 200
    assert create_response.json()["id"] == "job-1"
    assert get_response.status_code == 200
    assert get_response.json()["id"] == "job-1"


def test_modules_jobs_cancel_endpoint(monkeypatch: MonkeyPatch) -> None:
    class JobStub:
        def model_dump(self) -> dict[str, object]:
            return {
                "id": "job-1",
                "status": "cancelled",
                "created_at": "2026-05-24T16:00:00+00:00",
                "started_at": "2026-05-24T16:00:01+00:00",
                "finished_at": "2026-05-24T16:00:02+00:00",
                "request": {"module": "inspect"},
                "result": None,
                "error": "Cancelled by user.",
            }

    monkeypatch.setattr("framekit.web.app.cancel_module_job", lambda _job_id: JobStub())

    client = TestClient(create_app())
    response = client.delete("/api/v1/modules/jobs/job-1")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "cancelled"


def test_modules_jobs_rerun_endpoint(monkeypatch: MonkeyPatch) -> None:
    class JobStub:
        def model_dump(self) -> dict[str, object]:
            return {
                "id": "job-2",
                "status": "pending",
                "created_at": "2026-05-24T16:00:03+00:00",
                "started_at": None,
                "finished_at": None,
                "request": {"module": "inspect"},
                "result": None,
                "error": None,
            }

    monkeypatch.setattr("framekit.web.app.rerun_module_job", lambda _job_id: JobStub())

    client = TestClient(create_app())
    response = client.post("/api/v1/modules/jobs/job-1/rerun")
    payload = response.json()

    assert response.status_code == 200
    assert payload["id"] == "job-2"
    assert payload["status"] == "pending"


def test_provider_token_get_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.get_provider_token_value",
        lambda provider: {"provider": provider, "token": "", "is_set": False, "encrypted": False},
    )
    client = TestClient(create_app())

    response = client.get("/api/v1/settings/provider-token/tvdb")
    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"] == "tvdb"
    assert payload["is_set"] is False


def test_provider_token_get_invalid_provider(monkeypatch: MonkeyPatch) -> None:
    def _raise(provider: str) -> None:
        raise ValueError(f"unsupported provider: {provider}")

    monkeypatch.setattr("framekit.web.app.get_provider_token_value", _raise)
    client = TestClient(create_app())

    response = client.get("/api/v1/settings/provider-token/unknown")

    assert response.status_code == 400


def test_provider_token_set_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.set_provider_token_value",
        lambda provider, token: {"provider": provider, "token": "", "is_set": True, "encrypted": True},
    )
    client = TestClient(create_app())

    response = client.post("/api/v1/settings/provider-token/tvdb", json={"token": "my-secret-key"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["provider"] == "tvdb"
    assert payload["is_set"] is True


def test_announce_rename_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.rename_torrent_announce_label",
        lambda index, label: {
            "announces": [{"value": "https://tracker.example.com/announce", "label": label, "is_selected": True}],
            "selected_announce": "https://tracker.example.com/announce",
        },
    )
    client = TestClient(create_app())

    response = client.patch("/api/v1/torrent/announces/0", json={"label": "My Tracker"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["announces"][0]["label"] == "My Tracker"


def test_profiles_create_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.create_settings_profile",
        lambda name, description, overrides: {
            "profiles": [{"name": name, "description": description, "active": False, "overrides": overrides}],
            "active": None,
        },
    )
    client = TestClient(create_app())

    response = client.post("/api/v1/profiles", json={"name": "test-profile", "description": "A test", "overrides": {"metadata.provider": "tvdb"}})
    payload = response.json()

    assert response.status_code == 200
    assert payload["profiles"][0]["name"] == "test-profile"


def test_profiles_create_missing_name(monkeypatch: MonkeyPatch) -> None:
    def _raise(name: str, description: str, overrides: dict) -> None:
        raise ValueError("profile name is required")

    monkeypatch.setattr("framekit.web.app.create_settings_profile", _raise)
    client = TestClient(create_app())

    response = client.post("/api/v1/profiles", json={"name": "", "description": "", "overrides": {}})

    assert response.status_code == 400


def test_profiles_delete_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.delete_settings_profile",
        lambda name: {"profiles": [], "active": None},
    )
    client = TestClient(create_app())

    response = client.delete("/api/v1/profiles/test-profile")
    payload = response.json()

    assert response.status_code == 200
    assert payload["profiles"] == []


def test_profiles_delete_not_found(monkeypatch: MonkeyPatch) -> None:
    def _raise(name: str) -> None:
        raise ValueError(f"profile not found: {name}")

    monkeypatch.setattr("framekit.web.app.delete_settings_profile", _raise)
    client = TestClient(create_app())

    response = client.delete("/api/v1/profiles/missing")

    assert response.status_code == 400


def test_delete_all_presets_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.delete_all_yaml_presets",
        lambda kind: {"kind": kind, "deleted": ["preset-a", "preset-b"], "count": 2},
    )
    client = TestClient(create_app())

    response = client.delete("/api/v1/presets/pipeline/all")
    payload = response.json()

    assert response.status_code == 200
    assert payload["kind"] == "pipeline"
    assert payload["count"] == 2
    assert "preset-a" in payload["deleted"]


# ---------------------------------------------------------------------------
# Batch G — regression tests for Batches A–F
# ---------------------------------------------------------------------------

# ── Auth middleware ──────────────────────────────────────────────────────────

def test_auth_middleware_open_mode_allows_data_route() -> None:
    """Zero users (open mode) → protected data route returns 200, no token needed."""
    # autouse _open_access_mode fixture patches _is_auth_active → False
    client = TestClient(create_app())
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200


def test_auth_middleware_active_blocks_unauthenticated_data_route(monkeypatch: MonkeyPatch) -> None:
    """Auth active + no token → 401 with 'Authentication required'."""
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: True)
    client = TestClient(create_app())
    response = client.get("/api/v1/settings/summary")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_auth_middleware_always_open_paths_bypass_auth(monkeypatch: MonkeyPatch) -> None:
    """healthz, system/info, auth/status stay open even when auth is active."""
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: True)
    client = TestClient(create_app())
    assert client.get("/healthz").status_code == 200
    assert client.get("/api/v1/system/info").status_code == 200
    assert client.get("/api/v1/auth/status").status_code == 200


# ── Static / SPA serving ──────────────────────────────────────────────────────


def _write_test_spa(dist_dir: Path, marker: str) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        f"<!doctype html><html><body>{marker}</body></html>",
        encoding="utf-8",
    )
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "main.js").write_text(f"console.log('{marker}')", encoding="utf-8")


def test_static_serving_prefers_packaged_assets(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """When both dirs exist, packaged framekit.web/static is used before source web-ui/dist."""
    packaged_dir = tmp_path / "packaged-static"
    source_dir = tmp_path / "source-dist"
    _write_test_spa(packaged_dir, marker="packaged-ui")
    _write_test_spa(source_dir, marker="source-ui")
    monkeypatch.setattr("framekit.web.app._PACKAGE_STATIC_DIR", packaged_dir)
    monkeypatch.setattr("framekit.web.app._SOURCE_DIST_DIR", source_dir)

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "packaged-ui" in response.text
    assert "source-ui" not in response.text


def test_static_serving_falls_back_to_source_dist(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """If packaged static is absent, source-tree web-ui/dist still serves UI."""
    packaged_dir = tmp_path / "missing-packaged"
    source_dir = tmp_path / "source-dist"
    _write_test_spa(source_dir, marker="source-fallback")
    monkeypatch.setattr("framekit.web.app._PACKAGE_STATIC_DIR", packaged_dir)
    monkeypatch.setattr("framekit.web.app._SOURCE_DIST_DIR", source_dir)

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "source-fallback" in response.text


def test_static_serving_returns_json_hint_when_no_assets(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """If no static assets exist, root returns JSON fallback hint."""
    monkeypatch.setattr("framekit.web.app._PACKAGE_STATIC_DIR", tmp_path / "missing-packaged")
    monkeypatch.setattr("framekit.web.app._SOURCE_DIST_DIR", tmp_path / "missing-source")

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Framekit API is running. Web UI has not been built."
    assert "npm run build" in payload["hint"]


def test_spa_catch_all_never_swallows_api_paths(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Unknown /api/* path stays 404 JSON even when SPA catch-all is active."""
    packaged_dir = tmp_path / "packaged-static"
    _write_test_spa(packaged_dir, marker="packaged-ui")
    monkeypatch.setattr("framekit.web.app._PACKAGE_STATIC_DIR", packaged_dir)
    monkeypatch.setattr("framekit.web.app._SOURCE_DIST_DIR", tmp_path / "missing-source")

    client = TestClient(create_app())
    response = client.get("/api/not-a-real-route")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"


# ── Batch A — selected_announce nullable + seedbox rclone colon ─────────────

def test_announces_selected_announce_is_nullable(monkeypatch: MonkeyPatch) -> None:
    """selected_announce field is null (not absent) when nothing is selected."""
    monkeypatch.setattr(
        "framekit.web.app.list_torrent_announces_info",
        lambda: {"announces": [], "selected_announce": None},
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/torrent/announces")
    payload = response.json()
    assert response.status_code == 200
    assert "selected_announce" in payload
    assert payload["selected_announce"] is None


def test_seedbox_add_accepts_rclone_remote_with_trailing_colon(monkeypatch: MonkeyPatch) -> None:
    """rclone_remote in 'name:' format (standard rclone syntax) is accepted unchanged."""
    monkeypatch.setattr(
        "framekit.web.app.create_seedbox_profile",
        lambda **kwargs: [
            {
                "name": kwargs["name"],
                "rclone_remote": kwargs["rclone_remote"],
                "remote_base_path": kwargs["remote_base_path"],
                "max_concurrent_uploads": None,
                "bandwidth_limit": "",
                "is_default": False,
            }
        ],
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/seedbox/add",
        json={"name": "gdrive", "rclone_remote": "gdrive:", "remote_base_path": "/uploads"},
    )
    assert response.status_code == 200
    assert response.json()["seedboxes"][0]["rclone_remote"] == "gdrive:"


# ── Batch C — settings patch allowlist + password endpoint ──────────────────

def test_settings_patch_rejects_torrent_client_password() -> None:
    """upload.torrent_client_password is not in the patch allowlist → 400."""
    # No monkeypatching: allowlist check raises ValueError before any Settings() call.
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/settings/patch",
        json={"changes": {"upload.torrent_client_password": "secret"}},
    )
    assert response.status_code == 400
    assert "torrent_client_password" in response.json()["detail"]


def test_torrent_client_password_get_returns_status_only(monkeypatch: MonkeyPatch) -> None:
    """GET torrent-client-password returns is_set+encrypted, never the password value."""
    monkeypatch.setattr(
        "framekit.web.app.get_torrent_client_password",
        lambda: {"is_set": True, "encrypted": True},
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/upload/torrent-client-password")
    payload = response.json()
    assert response.status_code == 200
    assert "is_set" in payload
    assert "encrypted" in payload
    assert "password" not in payload
    assert "token" not in payload


# ── Webhooks — template support + placeholder validation (Batch D) ───────────

def test_webhook_add_stores_title_and_body_template(monkeypatch: MonkeyPatch) -> None:
    """POST /webhooks with title_template/body_template → stored in response."""
    from framekit.core.webhooks import WebhookConfig

    def _add(**kwargs):  # type: ignore[return]
        return [
            WebhookConfig(
                id="wh-1",
                name=kwargs["name"],
                url=kwargs["url"],
                discord=kwargs.get("discord", False),
                title_template=kwargs.get("title_template") or None,
                body_template=kwargs.get("body_template") or None,
            )
        ]

    monkeypatch.setattr("framekit.web.app.add_webhook", _add)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/webhooks",
        json={
            "name": "ci",
            "url": "https://hooks.example.com/1",
            "title_template": "Job: {event}",
            "body_template": "Module: {module}",
        },
    )
    assert response.status_code == 200
    wh = response.json()["webhooks"][0]
    assert wh["title_template"] == "Job: {event}"
    assert wh["body_template"] == "Module: {module}"


def test_webhook_update_stores_templates(monkeypatch: MonkeyPatch) -> None:
    """PATCH /webhooks/{id} with templates → stored in response."""
    from framekit.core.webhooks import WebhookConfig

    def _update(webhook_id, **kwargs):  # type: ignore[return]
        return [
            WebhookConfig(
                id=webhook_id,
                name="ci",
                url="https://hooks.example.com/1",
                title_template=kwargs.get("title_template") or None,
                body_template=kwargs.get("body_template") or None,
            )
        ]

    monkeypatch.setattr("framekit.web.app.update_webhook", _update)
    client = TestClient(create_app())
    response = client.patch(
        "/api/v1/webhooks/wh-1",
        json={"title_template": "Done: {job_id}", "body_template": ""},
    )
    assert response.status_code == 200
    wh = response.json()["webhooks"][0]
    assert wh["title_template"] == "Done: {job_id}"
    # body_template="" → cleared → None in response
    assert wh["body_template"] is None


def test_webhook_add_unknown_placeholder_returns_400(monkeypatch: MonkeyPatch) -> None:
    """Unknown placeholder {movie} raises ValueError → 400 with placeholder name in detail."""
    # Monkeypatch only load/save to avoid disk I/O; validation runs for real.
    monkeypatch.setattr("framekit.core.webhooks.load_webhooks", lambda: [])
    monkeypatch.setattr("framekit.core.webhooks.save_webhooks", lambda _: None)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/webhooks",
        json={
            "name": "bad",
            "url": "https://hooks.example.com/1",
            "title_template": "{movie} was released",
        },
    )
    assert response.status_code == 400
    assert "movie" in response.json()["detail"]


def test_webhook_test_payload_returns_ok_with_mocked_http(monkeypatch: MonkeyPatch) -> None:
    """POST /webhooks/test fires request and returns ok:true when target responds 2xx."""

    class _FakeResponse:
        status_code = 200
        text = ""

    class _FakeClient:
        def __init__(self, **kwargs: object) -> None:  # noqa: ARG002
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def post(self, url: str, **kwargs: object) -> _FakeResponse:  # noqa: ARG002
            return _FakeResponse()

    monkeypatch.setattr("httpx.Client", _FakeClient)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/webhooks/test",
        json={"url": "https://hooks.example.com/1", "discord": False},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_clean_web_job_output_strips_ansi() -> None:
    """_clean_web_job_output removes ANSI escape sequences and leaves plain text intact."""
    from framekit.web.modules import _clean_web_job_output

    # SGR color reset and bold — produced by Rich when NO_COLOR is not effective
    assert _clean_web_job_output("\x1b[1m[\x1b[0m\x1b[1mERR\x1b[0m\x1b[1m]\x1b[0m message") == "[ERR] message"
    # 256-colour foreground code
    assert _clean_web_job_output("\x1b[1;38;5;180mFramekit\x1b[0m") == "Framekit"
    # Plain text is untouched
    assert _clean_web_job_output("[INFO] Processing 3 files...") == "[INFO] Processing 3 files..."
    # Empty string is safe
    assert _clean_web_job_output("") == ""
    # Mixed: ANSI before and after plain content
    assert _clean_web_job_output("\x1b[32mok\x1b[0m \x1b[31merr\x1b[0m") == "ok err"


# ---------------------------------------------------------------------------
# Batch L.1 — regression tests for Batches I / J / K backend additions
# ---------------------------------------------------------------------------

# ── GET /api/v1/runs ─────────────────────────────────────────────────────────

def test_runs_endpoint_returns_empty_list_when_no_ledger(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("framekit.web.app.list_runs_from_ledger", lambda limit=50: [])
    client = TestClient(create_app())
    response = client.get("/api/v1/runs")
    payload = response.json()
    assert response.status_code == 200
    assert payload["runs"] == []


def test_runs_endpoint_rejects_out_of_range_limit() -> None:
    """limit=0 and limit=201 must return 400."""
    # No monkeypatching needed — limit guard fires before list_runs_from_ledger.
    client = TestClient(create_app())
    assert client.get("/api/v1/runs?limit=0").status_code == 400
    assert client.get("/api/v1/runs?limit=201").status_code == 400


def test_runs_endpoint_passes_limit_to_helper(monkeypatch: MonkeyPatch) -> None:
    captured: list[int] = []

    def _stub(limit: int = 50) -> list[dict]:
        captured.append(limit)
        return []

    monkeypatch.setattr("framekit.web.app.list_runs_from_ledger", _stub)
    client = TestClient(create_app())
    client.get("/api/v1/runs?limit=7")
    assert captured == [7]


# ── list_runs_from_ledger unit tests (pure-function, tmp_path) ────────────────

def test_list_runs_from_ledger_missing_file_returns_empty(
    tmp_path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "framekit.core.runs.ledger.get_runs_ledger_path",
        lambda: tmp_path / "nonexistent.ndjson",
    )
    from framekit.web.modules import list_runs_from_ledger
    assert list_runs_from_ledger() == []


def test_list_runs_from_ledger_groups_by_run_id(
    tmp_path, monkeypatch: MonkeyPatch
) -> None:
    import json as _json

    ledger = tmp_path / "ledger.ndjson"
    ledger.write_text(
        _json.dumps({"run_id": "run-A", "module": "renamer", "src": "a.mkv", "timestamp": "2024-01-02T00:00:00"}) + "\n"
        + _json.dumps({"run_id": "run-A", "module": "renamer", "src": "b.mkv", "timestamp": "2024-01-02T00:00:01"}) + "\n"
        + _json.dumps({"run_id": "run-B", "module": "cleanmkv", "src": "c.mkv", "timestamp": "2024-01-03T00:00:00"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("framekit.core.runs.ledger.get_runs_ledger_path", lambda: ledger)
    from framekit.web.modules import list_runs_from_ledger
    runs = list_runs_from_ledger()
    assert len(runs) == 2
    run_a = next(r for r in runs if r["run_id"] == "run-A")
    assert run_a["file_count"] == 2
    assert run_a["module"] == "renamer"
    assert len(run_a["actions"]) == 2


def test_list_runs_from_ledger_newest_first(
    tmp_path, monkeypatch: MonkeyPatch
) -> None:
    import json as _json

    ledger = tmp_path / "ledger.ndjson"
    ledger.write_text(
        _json.dumps({"run_id": "old", "module": "renamer", "timestamp": "2024-01-01T00:00:00"}) + "\n"
        + _json.dumps({"run_id": "new", "module": "renamer", "timestamp": "2024-01-05T00:00:00"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("framekit.core.runs.ledger.get_runs_ledger_path", lambda: ledger)
    from framekit.web.modules import list_runs_from_ledger
    runs = list_runs_from_ledger()
    assert runs[0]["run_id"] == "new"
    assert runs[1]["run_id"] == "old"


def test_list_runs_from_ledger_respects_limit(
    tmp_path, monkeypatch: MonkeyPatch
) -> None:
    import json as _json

    lines = [
        _json.dumps({"run_id": f"run-{i}", "module": "renamer", "timestamp": f"2024-01-{i + 1:02d}T00:00:00"})
        for i in range(5)
    ]
    ledger = tmp_path / "ledger.ndjson"
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr("framekit.core.runs.ledger.get_runs_ledger_path", lambda: ledger)
    from framekit.web.modules import list_runs_from_ledger
    assert len(list_runs_from_ledger(limit=2)) == 2


# ── Service status API ────────────────────────────────────────────────────────

def test_service_status_stopped_when_no_state_file(monkeypatch: MonkeyPatch) -> None:
    """GET /api/v1/service/status returns stopped when no state file exists."""
    monkeypatch.setattr(
        "framekit.core.service.supervisor.ServiceSupervisor.read_state",
        lambda self: None,
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/service/status")
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "stopped"
    assert payload["pid"] is None


def test_service_status_running_with_fresh_heartbeat(monkeypatch: MonkeyPatch) -> None:
    """GET /api/v1/service/status returns running when state file is fresh and PID alive."""
    import os
    import time

    now = time.time()
    monkeypatch.setattr(
        "framekit.core.service.supervisor.ServiceSupervisor.read_state",
        lambda self: {
            "status": "running",
            "pid": os.getpid(),   # current test process — guaranteed alive
            "started_at": now - 5.0,
            "heartbeat_at": now - 1.0,
        },
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/service/status")
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "running"
    assert payload["pid"] == os.getpid()
    assert payload["uptime_seconds"] is not None


def test_service_status_stopped_when_heartbeat_stale(monkeypatch: MonkeyPatch) -> None:
    """GET /api/v1/service/status returns stopped when heartbeat is too old (crash guard)."""
    import time

    stale_ts = time.time() - 120.0  # 120 s ago — well past 30 s threshold
    monkeypatch.setattr(
        "framekit.core.service.supervisor.ServiceSupervisor.read_state",
        lambda self: {
            "status": "running",
            "pid": 99999,
            "started_at": stale_ts,
            "heartbeat_at": stale_ts,
        },
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/service/status")
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "stopped"


def test_service_status_running_includes_watcher_state(monkeypatch: MonkeyPatch) -> None:
    """GET /api/v1/service/status includes watcher subsystem state when running."""
    import os
    import time

    now = time.time()
    monkeypatch.setattr(
        "framekit.core.service.supervisor.ServiceSupervisor.read_state",
        lambda self: {
            "status": "running",
            "pid": os.getpid(),
            "started_at": now - 5.0,
            "heartbeat_at": now - 1.0,
        },
    )
    monkeypatch.setattr(
        "framekit.web.app.get_embedded_watcher_state",
        lambda: {"status": "stopped", "folders_active": 0, "last_error": None},
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/service/status")
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "running"
    assert "watcher" in payload
    watcher = payload["watcher"]
    assert watcher["status"] == "stopped"
    assert watcher["folders_active"] == 0
    assert watcher["last_error"] is None


def test_get_embedded_watcher_state_no_watcher() -> None:
    """get_embedded_watcher_state returns stopped state when no watcher is active."""
    import framekit.web.modules as mod

    # Ensure clean state (no embedded watcher from other tests)
    original = mod._EMBEDDED_WATCHER
    original_err = mod._EMBEDDED_WATCHER_ERROR
    try:
        mod._EMBEDDED_WATCHER = None
        mod._EMBEDDED_WATCHER_ERROR = None
        state = mod.get_embedded_watcher_state()
        assert state["status"] == "stopped"
        assert state["folders_active"] == 0
        assert state["last_error"] is None
    finally:
        mod._EMBEDDED_WATCHER = original
        mod._EMBEDDED_WATCHER_ERROR = original_err


def test_get_embedded_watcher_state_with_error() -> None:
    """get_embedded_watcher_state returns error status when startup failed."""
    import framekit.web.modules as mod

    original = mod._EMBEDDED_WATCHER
    original_err = mod._EMBEDDED_WATCHER_ERROR
    try:
        mod._EMBEDDED_WATCHER = None
        mod._EMBEDDED_WATCHER_ERROR = "watch folder does not exist"
        state = mod.get_embedded_watcher_state()
        assert state["status"] == "error"
        assert state["last_error"] == "watch folder does not exist"
    finally:
        mod._EMBEDDED_WATCHER = original
        mod._EMBEDDED_WATCHER_ERROR = original_err


# ── Watch service API ─────────────────────────────────────────────────────────

def test_watch_service_status_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "framekit.web.app.get_watch_service_status",
        lambda: {"status": "stopped", "pid": None},
    )
    client = TestClient(create_app())
    response = client.get("/api/v1/watch/service")
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "stopped"
    assert payload["pid"] is None


def test_watch_service_start_enqueues_watch_module_job(monkeypatch: MonkeyPatch) -> None:
    """POST /watch/service/start must enqueue module=watch with expected args."""
    captured: list = []

    class _JobStub:
        def model_dump(self) -> dict:
            return {
                "id": "job-watch",
                "status": "pending",
                "created_at": "2026-01-01T00:00:00Z",
                "started_at": None,
                "finished_at": None,
                "request": {},
                "result": None,
                "error": None,
            }

    def _enqueue(request):
        captured.append(request)
        return _JobStub()

    monkeypatch.setattr("framekit.web.app.enqueue_module_job", _enqueue)
    client = TestClient(create_app())
    response = client.post("/api/v1/watch/service/start")
    assert response.status_code == 200
    assert response.json()["id"] == "job-watch"
    assert len(captured) == 1
    req = captured[0]
    assert req.module == "watch"
    assert "start" in req.args_text
    assert "--all" in req.args_text
    assert req.auto_yes is True


def test_watch_service_stop_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("framekit.web.app.stop_watch_service", lambda: {"stopped": True})
    client = TestClient(create_app())
    response = client.post("/api/v1/watch/service/stop")
    payload = response.json()
    assert response.status_code == 200
    assert payload["stopped"] is True


def test_watch_service_start_returns_409_when_embedded_watcher_running(
    monkeypatch: MonkeyPatch,
) -> None:
    """POST /watch/service/start must return 409 when the embedded watcher is active."""
    monkeypatch.setattr(
        "framekit.web.app.get_embedded_watcher_state",
        lambda: {"status": "running", "folders_active": 2, "last_error": None},
    )
    client = TestClient(create_app())
    response = client.post("/api/v1/watch/service/start")
    assert response.status_code == 409
    assert "embedded" in response.json()["detail"].lower() or "service" in response.json()["detail"].lower()


def test_watch_service_start_enqueues_when_no_embedded_watcher(
    monkeypatch: MonkeyPatch,
) -> None:
    """POST /watch/service/start enqueues a watch job when no embedded watcher is running."""
    monkeypatch.setattr(
        "framekit.web.app.get_embedded_watcher_state",
        lambda: {"status": "stopped", "folders_active": 0, "last_error": None},
    )
    captured: list = []

    class _JobStub:
        def model_dump(self) -> dict:
            return {
                "id": "job-watch-2",
                "status": "pending",
                "created_at": "2026-01-01T00:00:00Z",
                "started_at": None,
                "finished_at": None,
                "request": {},
                "result": None,
                "error": None,
            }

    def _enqueue(request):
        captured.append(request)
        return _JobStub()

    monkeypatch.setattr("framekit.web.app.enqueue_module_job", _enqueue)
    client = TestClient(create_app())
    response = client.post("/api/v1/watch/service/start")
    assert response.status_code == 200
    assert response.json()["id"] == "job-watch-2"
    assert len(captured) == 1


def test_service_reload_restarts_embedded_watcher(monkeypatch: MonkeyPatch) -> None:
    """POST /api/v1/service/reload calls stop then start on embedded watcher."""
    calls: list[str] = []

    monkeypatch.setattr("framekit.web.app.stop_embedded_watcher", lambda: calls.append("stop"))
    monkeypatch.setattr("framekit.web.app.start_embedded_watcher", lambda: calls.append("start"))
    monkeypatch.setattr(
        "framekit.web.app.get_embedded_watcher_state",
        lambda: {"status": "stopped", "folders_active": 0, "last_error": None},
    )
    client = TestClient(create_app())
    response = client.post("/api/v1/service/reload")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "watcher" in payload
    assert calls == ["stop", "start"]


# ── Intake API ────────────────────────────────────────────────────────────────


def test_intake_list_sources_empty(monkeypatch: MonkeyPatch) -> None:
    """GET /api/v1/intake/sources returns empty list when no sources configured."""
    monkeypatch.setattr("framekit.web.app.list_intake_sources", lambda: [])
    client = TestClient(create_app())
    response = client.get("/api/v1/intake/sources")
    assert response.status_code == 200
    assert response.json() == {"sources": []}


def test_intake_create_source_returns_token(monkeypatch: MonkeyPatch) -> None:
    """POST /api/v1/intake/sources returns source dict including one-time token."""
    created = {
        "id": "abc-123",
        "name": "qBittorrent",
        "source_id": "qbittorrent",
        "enabled": True,
        "default_preset": None,
        "created_at": "2026-01-01T00:00:00Z",
        "token": "tok_abc",
    }
    monkeypatch.setattr("framekit.web.app.create_intake_source", lambda name, source_id, default_preset=None: created)
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/intake/sources",
        json={"name": "qBittorrent", "source_id": "qbittorrent"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == "qbittorrent"
    assert payload["token"] == "tok_abc"


def test_intake_create_source_requires_admin_when_auth_active(monkeypatch: MonkeyPatch) -> None:
    """POST /api/v1/intake/sources returns 401 when auth active and no credentials."""
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: True)
    monkeypatch.setattr("framekit.web.app._require_admin", lambda req: (_ for _ in ()).throw(
        __import__("fastapi").HTTPException(status_code=401, detail="Authentication required")
    ))
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        "/api/v1/intake/sources",
        json={"name": "qBittorrent", "source_id": "qbittorrent"},
    )
    assert response.status_code == 401


def test_intake_delete_source(monkeypatch: MonkeyPatch) -> None:
    """DELETE /api/v1/intake/sources/{id} returns deleted=True."""
    monkeypatch.setattr(
        "framekit.web.app.delete_intake_source",
        lambda source_id: {"deleted": True, "source_id": source_id},
    )
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.delete("/api/v1/intake/sources/qbittorrent")
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "source_id": "qbittorrent"}


def test_intake_delete_source_unknown_returns_404(monkeypatch: MonkeyPatch) -> None:
    """DELETE /api/v1/intake/sources/{id} returns 404 for unknown source."""
    monkeypatch.setattr(
        "framekit.web.app.delete_intake_source",
        lambda source_id: (_ for _ in ()).throw(ValueError(f"source_id '{source_id}' not found")),
    )
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.delete("/api/v1/intake/sources/unknown")
    assert response.status_code == 404


def test_intake_submit_release_accepted(monkeypatch: MonkeyPatch, tmp_path) -> None:
    """POST /api/v1/intake/release returns accepted=True and job_id when auth disabled."""
    result = {"job_id": "job-intake-1", "accepted": True, "dedup_hit": False}
    monkeypatch.setattr(
        "framekit.web.app.submit_intake_release",
        lambda source_id, path, preset=None, dedup_key=None: result,
    )
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/intake/release",
        json={"source": "qbittorrent", "path": str(tmp_path)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-intake-1"
    assert payload["accepted"] is True
    assert payload["dedup_hit"] is False


def test_intake_submit_release_dedup(monkeypatch: MonkeyPatch, tmp_path) -> None:
    """POST /api/v1/intake/release returns dedup_hit=True when duplicate detected."""
    result = {"job_id": "job-existing", "accepted": False, "dedup_hit": True}
    monkeypatch.setattr(
        "framekit.web.app.submit_intake_release",
        lambda source_id, path, preset=None, dedup_key=None: result,
    )
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/intake/release",
        json={"source": "qbittorrent", "path": str(tmp_path)},
    )
    assert response.status_code == 200
    assert response.json()["dedup_hit"] is True


def test_intake_submit_release_bad_path(monkeypatch: MonkeyPatch) -> None:
    """POST /api/v1/intake/release returns 400 when path validation fails."""
    monkeypatch.setattr(
        "framekit.web.app.submit_intake_release",
        lambda source_id, path, preset=None, dedup_key=None: (_ for _ in ()).throw(
            ValueError("Path does not exist: /nonexistent")
        ),
    )
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/intake/release",
        json={"source": "qbittorrent", "path": "/nonexistent"},
    )
    assert response.status_code == 400
    assert "Path does not exist" in response.json()["detail"]


def test_intake_submit_release_requires_token_when_auth_active(monkeypatch: MonkeyPatch, tmp_path) -> None:
    """POST /api/v1/intake/release returns 401 when auth active and no credentials."""
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: True)
    monkeypatch.setattr("framekit.web.app._get_current_user", lambda req: None)
    monkeypatch.setattr("framekit.web.app.verify_intake_token", lambda source_id, token: False)
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        "/api/v1/intake/release",
        json={"source": "qbittorrent", "path": str(tmp_path)},
    )
    assert response.status_code == 401


def test_intake_submit_release_accepts_valid_intake_token(monkeypatch: MonkeyPatch, tmp_path) -> None:
    """POST /api/v1/intake/release accepts valid intake token when auth is active."""
    result = {"job_id": "job-tok-1", "accepted": True, "dedup_hit": False}
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: True)
    monkeypatch.setattr("framekit.web.app._get_current_user", lambda req: None)
    monkeypatch.setattr("framekit.web.app.verify_intake_token", lambda source_id, token: True)
    monkeypatch.setattr(
        "framekit.web.app.submit_intake_release",
        lambda source_id, path, preset=None, dedup_key=None: result,
    )
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/intake/release",
        json={"source": "qbittorrent", "path": str(tmp_path)},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert response.status_code == 200
    assert response.json()["job_id"] == "job-tok-1"


def test_intake_webhook_alias_route(monkeypatch: MonkeyPatch, tmp_path) -> None:
    """POST /api/v1/intake/webhook/{source} routes to submit_intake_release with path source."""
    result = {"job_id": "job-wh-1", "accepted": True, "dedup_hit": False}
    monkeypatch.setattr(
        "framekit.web.app.submit_intake_release",
        lambda source_id, path, preset=None, dedup_key=None: result,
    )
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/intake/webhook/mydownloader",
        json={"source": "mydownloader", "path": str(tmp_path)},
    )
    assert response.status_code == 200
    assert response.json()["job_id"] == "job-wh-1"


def test_intake_rate_limit_exceeded(monkeypatch: MonkeyPatch, tmp_path) -> None:
    """POST /api/v1/intake/release returns 400 when rate limit exceeded."""
    monkeypatch.setattr(
        "framekit.web.app.submit_intake_release",
        lambda source_id, path, preset=None, dedup_key=None: (_ for _ in ()).throw(
            ValueError("Rate limit exceeded (30 requests/min per source)")
        ),
    )
    monkeypatch.setattr("framekit.web.app._is_auth_active", lambda: False)
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/intake/release",
        json={"source": "qbittorrent", "path": str(tmp_path)},
    )
    assert response.status_code == 400
    assert "Rate limit" in response.json()["detail"]


# ── Intake unit tests (modules layer) ─────────────────────────────────────────


def test_intake_request_hash_deterministic() -> None:
    from framekit.web.modules import _intake_request_hash
    h1 = _intake_request_hash("src", "/tmp/release", "key1")
    h2 = _intake_request_hash("src", "/tmp/release", "key1")
    assert h1 == h2
    assert len(h1) == 40  # sha1 hex


def test_intake_request_hash_differs_on_key() -> None:
    from framekit.web.modules import _intake_request_hash
    h1 = _intake_request_hash("src", "/tmp/release", "key1")
    h2 = _intake_request_hash("src", "/tmp/release", "key2")
    assert h1 != h2


def test_intake_rate_limit_allows_up_to_limit() -> None:
    from framekit.web.modules import _check_intake_rate_limit, _INTAKE_RATE_WINDOWS, _INTAKE_RATE_LOCK
    source = "rate_test_source_unique_xyz"
    with _INTAKE_RATE_LOCK:
        _INTAKE_RATE_WINDOWS.pop(source, None)
    for _ in range(30):
        assert _check_intake_rate_limit(source) is True
    assert _check_intake_rate_limit(source) is False


def test_intake_path_allowed_no_roots(monkeypatch: MonkeyPatch) -> None:
    from pathlib import Path
    from framekit.web.modules import _intake_path_allowed
    monkeypatch.setattr("framekit.web.modules._intake_allowed_roots", lambda: [])
    assert _intake_path_allowed(Path("/any/path")) is True


def test_intake_path_allowed_with_root(monkeypatch: MonkeyPatch, tmp_path) -> None:
    from framekit.web.modules import _intake_path_allowed
    monkeypatch.setattr(
        "framekit.web.modules._intake_allowed_roots",
        lambda: [tmp_path.resolve()],
    )
    assert _intake_path_allowed((tmp_path / "release").resolve()) is True
    assert _intake_path_allowed(tmp_path.parent.resolve()) is False


def test_verify_intake_token_constant_time(monkeypatch: MonkeyPatch) -> None:
    from framekit.web.modules import verify_intake_token

    class _FakeVault:
        def retrieve(self, key, default=None):
            if key == "intake.src1.token":
                return "correct-token"
            return default

    class _FakeSettings:
        def get_vault(self):
            return _FakeVault()

    monkeypatch.setattr("framekit.web.modules.Settings", _FakeSettings)
    assert verify_intake_token("src1", "correct-token") is True
    assert verify_intake_token("src1", "wrong-token") is False
    assert verify_intake_token("unknown", "anything") is False


def test_submit_intake_release_unknown_source(monkeypatch: MonkeyPatch) -> None:
    from framekit.web.modules import submit_intake_release
    monkeypatch.setattr("framekit.web.modules._load_intake_sources", lambda: [])
    with pytest.raises(ValueError, match="Unknown intake source"):
        submit_intake_release("nonexistent", "/tmp/path")


def test_submit_intake_release_disabled_source(monkeypatch: MonkeyPatch) -> None:
    from framekit.web.modules import submit_intake_release, IntakeSource
    source = IntakeSource(
        id="1", name="Disabled", source_id="dis", enabled=False,
        default_preset=None, created_at="2026-01-01T00:00:00Z",
    )
    monkeypatch.setattr("framekit.web.modules._load_intake_sources", lambda: [source])
    with pytest.raises(ValueError, match="disabled"):
        submit_intake_release("dis", "/tmp/path")


# ── CLI --json output ─────────────────────────────────────────────────────────

def test_inspect_json_outputs_valid_json_on_missing_path() -> None:
    """inspect --json with nonexistent path prints {"error": "..."} — valid JSON, exit 1."""
    import json as _json
    from click.testing import CliRunner
    from framekit.commands.inspect import inspect_command

    runner = CliRunner()
    result = runner.invoke(inspect_command, ["--json", "/nonexistent/path/that/does/not/exist"])
    parsed = _json.loads(result.output.strip())
    assert "error" in parsed
    assert result.exit_code != 0


def test_validate_json_outputs_valid_json(tmp_path, monkeypatch: MonkeyPatch) -> None:
    """validate --json prints a valid JSON object regardless of validation outcome."""
    import json as _json
    from click.testing import CliRunner
    from framekit.commands.validate import validate_command

    class _Severity:
        value = "error"

    class _Issue:
        severity = _Severity()
        category = "container"
        message = "No MKV files found"
        suggestion = "Add an MKV file"

    class _Result:
        release_name = "TestRelease"
        is_valid = False
        checks_passed = 0
        checks_warned = 0
        checks_failed = 1
        issues = [_Issue()]

    class _ServiceStub:
        def __init__(self, **kwargs):  # noqa: ARG002
            pass

        def validate(self, path):  # noqa: ARG002
            return _Result()

    monkeypatch.setattr("framekit.commands.validate.ValidationService", _ServiceStub)

    runner = CliRunner()
    result = runner.invoke(validate_command, ["--json", str(tmp_path)])
    parsed = _json.loads(result.output.strip())
    assert parsed["release_name"] == "TestRelease"
    assert isinstance(parsed["issues"], list)
    assert parsed["checks_failed"] == 1
