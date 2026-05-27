from __future__ import annotations

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
