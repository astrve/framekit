from __future__ import annotations

from click.testing import CliRunner

from framekit.commands.main import cli
from framekit.modules.upload.models import TrackerConfig
from framekit.modules.upload.service import UploadService


def test_custom_json_api_engine_is_valid() -> None:
    config = TrackerConfig(
        name="my-tracker",
        type="custom_json_api_v1",
        url="https://tracker.example",
        api_key="token",
    )

    assert config.type == "custom_json_api_v1"


def test_upload_assistant_saves_tracker_yaml_without_token(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    settings_file.write_text("upload:\n  trackers: []\n", encoding="utf-8")
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))

    result = CliRunner().invoke(
        cli,
        [
            "upload",
            "assistant",
            "--name",
            "My Tracker",
            "--base-url",
            "https://tracker.example",
            "--token-env",
            "FRAMEKIT_TRACKER_MY_TRACKER_TOKEN",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    tracker_file = tmp_path / "trackers" / "my-tracker.yaml"
    content = tracker_file.read_text(encoding="utf-8")
    assert "FRAMEKIT_TRACKER_MY_TRACKER_TOKEN" in content
    assert "api_key" not in content
    assert "secret" not in content.lower()


def test_upload_service_loads_tracker_yaml_token_from_env(tmp_path, monkeypatch) -> None:
    settings_file = tmp_path / "framekit.yaml"
    trackers_dir = tmp_path / "trackers"
    trackers_dir.mkdir()
    settings_file.write_text("upload:\n  trackers: []\n", encoding="utf-8")
    (trackers_dir / "my-tracker.yaml").write_text(
        "\n".join(
            [
                "name: my-tracker",
                "engine: custom_json_api_v1",
                "base_url: https://tracker.example",
                "auth:",
                "  type: bearer",
                "  token_env: FRAMEKIT_TRACKER_MY_TRACKER_TOKEN",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FRAMEKIT_CONFIG", str(settings_file))
    monkeypatch.setenv("FRAMEKIT_TRACKER_MY_TRACKER_TOKEN", "runtime-token")

    config = UploadService()._load_tracker_config("my-tracker")

    assert config.type == "custom_json_api_v1"
    assert config.api_key == "runtime-token"
