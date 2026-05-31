"""Base pytest configuration and fixtures for the test suite."""

from __future__ import annotations

import sys
from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def tmp_path_factory_session(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped temporary directory factory."""
    return tmp_path_factory.mktemp("session")


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """Provide an isolated environment with clean env vars and temp directories.

    Returns:
        Dictionary of environment variables set for the test.
    """
    env_vars_to_clear = [
        "SWIRRL_LOG_FILE",
        "SWIRRL_DEBUG",
        "SWIRRL_CONFIG",
        "SWIRRL_CACHE_DIR",
    ]
    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)

    cache_dir = tmp_path / "cache"
    config_dir = tmp_path / "config"
    cache_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    env = {
        "SWIRRL_CACHE_DIR": str(cache_dir),
        "SWIRRL_CONFIG": str(config_dir / "swirrl.yaml"),
    }

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    return env


@pytest.fixture
def mock_settings_data() -> dict[str, Any]:
    """Return a deep-copied snapshot of the current ``DEFAULT_SETTINGS``.

    This always matches the live schema (``SETTINGS_SCHEMA_VERSION``) — tests
    that need to verify load/save round-tripping or migration must operate on
    the same shape as production code. The fixture intentionally re-exports
    the real defaults rather than maintaining a parallel literal that drifts.
    """
    from swirrl.core.settings import DEFAULT_SETTINGS

    return deepcopy(DEFAULT_SETTINGS)


@pytest.fixture
def mock_http_response() -> Mock:
    """Create a mock HTTP response object.

    Returns:
        Mock object with common HTTP response attributes.
    """
    response = Mock()
    response.status_code = 200
    response.headers = {}
    response.body = b'{"success": true}'
    response.text = '{"success": true}'
    response.json.return_value = {"success": True}
    return response


@pytest.fixture
def mock_sleep(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock time.sleep to speed up tests.

    Returns:
        Mock sleep function that tracks calls without actually sleeping.
    """
    mock = Mock()
    monkeypatch.setattr("time.sleep", mock)
    return mock


@pytest.fixture(autouse=True)
def reset_locale_and_diagnostics() -> Generator[None, None, None]:
    """Reset global mutable state before and after each test.

    Tests rely on a clean slate: locale, diagnostics, and path security
    settings must not leak into the next test or the same xdist worker.
    """
    from swirrl.core.diagnostics import reset_diagnostics
    from swirrl.core.i18n import set_locale
    from swirrl.core.path_validation import configure_security

    set_locale("en")
    reset_diagnostics()
    configure_security(strict_mode=False, allowed_base_dirs=[], allow_symlinks=True)
    try:
        yield
    finally:
        set_locale("en")
        reset_diagnostics()
        configure_security(strict_mode=False, allowed_base_dirs=[], allow_symlinks=True)


@pytest.fixture
def mock_mediainfo() -> Mock:
    """Create a mock MediaInfo object for testing.

    Returns:
        Mock MediaInfo with common track structures.
    """
    mock = Mock()

    general_track = Mock()
    general_track.track_type = "General"
    general_track.format = "Matroska"
    general_track.duration = 3600000
    general_track.file_size = 1073741824

    video_track = Mock()
    video_track.track_type = "Video"
    video_track.format = "AVC"
    video_track.width = 1920
    video_track.height = 1080
    video_track.frame_rate = "23.976"
    video_track.bit_depth = 8

    audio_track = Mock()
    audio_track.track_type = "Audio"
    audio_track.format = "AAC"
    audio_track.language = "en"
    audio_track.channels = 2

    mock.tracks = [general_track, video_track, audio_track]
    return mock


@pytest.fixture
def sample_video_path(tmp_path: Path) -> Path:
    """Create a sample (empty) MKV file for tests that need a path on disk."""
    video_file = tmp_path / "sample_video.mkv"
    video_file.write_bytes(b"FAKE_VIDEO_DATA")
    return video_file


@pytest.fixture
def capture_logs(tmp_path: Path) -> Path:
    """Route diagnostic logs to a temporary file for the test."""
    from swirrl.core.diagnostics import configure_diagnostics

    log_file = tmp_path / "test.log"
    configure_diagnostics(debug=True, log_file=log_file)
    return log_file


@pytest.fixture
def temp_settings_store(tmp_path: Path):
    """A ``SettingsStore`` pointing at a temporary YAML file."""
    from swirrl.core.settings import SettingsStore

    return SettingsStore(tmp_path / "swirrl.yaml")


@pytest.fixture
def isolated_settings_store(temp_settings_store):
    """Alias kept for tests that still reference the original name."""
    return temp_settings_store


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (slower)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (slowest)")
    config.addinivalue_line("markers", "slow: Tests that take significant time")
    config.addinivalue_line("markers", "network: Tests requiring network access")
    config.addinivalue_line("markers", "filesystem: Tests requiring filesystem operations")
