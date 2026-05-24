from __future__ import annotations

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

from framekit.web.app import create_app


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
        lambda name: [
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
