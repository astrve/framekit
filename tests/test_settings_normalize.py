"""Unit tests for :mod:`swirrl.core.settings.normalize`.

Targets pure helpers (``normalize_ui_locale``, ``normalize_nfo_locale``,
``resolve_nfo_locale``, ``metadata_language_for_nfo_locale``,
``is_valid_metadata_language``, ``_as_bool``, ``_as_int``,
``redact_settings``, ``_deep_merge``, ``_get_nested``, ``_set_nested``,
``_split_key_path``, ``_is_secret_key``). No I/O, no env, fast.
"""

from __future__ import annotations

from typing import Any

import pytest

from swirrl.core.settings.normalize import (
    _as_bool,
    _as_int,
    _deep_merge,
    _get_nested,
    _is_secret_key,
    _set_nested,
    _split_key_path,
    is_valid_metadata_language,
    metadata_language_for_nfo_locale,
    normalize_metadata_language,
    normalize_nfo_locale,
    normalize_settings,
    normalize_ui_locale,
    redact_settings,
    resolve_nfo_locale,
    validate_settings,
)

# ---------------------------------------------------------------------------
# UI locale
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en", "en"),
        ("fr", "fr"),
        ("es", "es"),
        ("EN", "en"),
        ("en_US", "en"),
        ("en-US", "en"),
        ("fr-CA", "fr"),
        ("", "en"),
        (None, "en"),
        ("ja", "en"),
        ("   ", "en"),
    ],
)
def test_normalize_ui_locale(raw: str | None, expected: str) -> None:
    assert normalize_ui_locale(raw) == expected


# ---------------------------------------------------------------------------
# NFO locale
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("auto", "auto"),
        ("en", "en"),
        ("fr-FR", "fr"),
        ("", "auto"),
        (None, "auto"),
        ("xx", "auto"),
    ],
)
def test_normalize_nfo_locale(raw: str | None, expected: str) -> None:
    assert normalize_nfo_locale(raw) == expected


def test_resolve_nfo_locale_returns_explicit_locale() -> None:
    assert resolve_nfo_locale("fr", ui_locale="en") == "fr"


def test_resolve_nfo_locale_falls_back_to_ui_when_auto() -> None:
    assert resolve_nfo_locale("auto", ui_locale="es") == "es"


def test_resolve_nfo_locale_uses_default_when_no_ui() -> None:
    assert resolve_nfo_locale("auto", ui_locale=None) == "en"


# ---------------------------------------------------------------------------
# Metadata language
# ---------------------------------------------------------------------------


def test_metadata_language_for_nfo_locale_uses_mapping() -> None:
    result = metadata_language_for_nfo_locale("fr")
    assert result.startswith("fr")


def test_metadata_language_for_auto_uses_default_ui_locale() -> None:
    result = metadata_language_for_nfo_locale("auto")
    assert result.startswith("en")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en-US", True),
        ("fr-FR", True),
        ("es", True),
        ("en_US", False),
        ("", False),
        (None, False),
        ("toolong", False),
    ],
)
def test_is_valid_metadata_language(raw: str | None, expected: bool) -> None:
    assert is_valid_metadata_language(raw) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("en-US", "en-US"),
        ("en_US", "en-US"),
        ("FR-fr", "FR-fr"),
        ("", "en-US"),
        ("garbage", "en-US"),
    ],
)
def test_normalize_metadata_language(raw: str, expected: str) -> None:
    assert normalize_metadata_language(raw) == expected


# ---------------------------------------------------------------------------
# _as_bool / _as_int
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        (True, False, True),
        (False, True, False),
        ("true", False, True),
        ("YES", False, True),
        ("on", False, True),
        ("1", False, True),
        ("y", False, True),
        ("false", True, False),
        ("no", True, False),
        ("off", True, False),
        ("0", True, False),
        ("n", True, False),
        ("garbage", True, True),
        (None, False, False),
        (42, True, True),
    ],
)
def test_as_bool(raw: Any, default: bool, expected: bool) -> None:
    assert _as_bool(raw, default) is expected


@pytest.mark.parametrize(
    ("raw", "default", "minimum", "expected"),
    [
        ("5", 0, None, 5),
        (5, 0, None, 5),
        ("invalid", 7, None, 7),
        (None, 7, None, 7),
        ("3", 0, 5, 0),
        ("10", 0, 5, 10),
        ("-1", 0, 0, 0),
    ],
)
def test_as_int(raw: Any, default: int, minimum: int | None, expected: int) -> None:
    assert _as_int(raw, default, minimum=minimum) == expected


# ---------------------------------------------------------------------------
# _is_secret_key / redact_settings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("tmdb_read_access_token", True),
        ("api_key", True),
        ("password", True),
        ("trakt_client_secret", True),
        ("announce", True),
        ("locale", False),
        ("max_size_mb", False),
        ("title", False),
    ],
)
def test_is_secret_key(key: str, expected: bool) -> None:
    assert _is_secret_key(key) is expected


def test_redact_settings_masks_secret_values() -> None:
    settings = {
        "metadata": {
            "tmdb_read_access_token": "super-secret",
            "locale": "en",
        },
        "torrent": {"announce": "https://tracker/passkey"},
    }
    redacted = redact_settings(settings)
    assert redacted["metadata"]["tmdb_read_access_token"] == "********"
    assert redacted["metadata"]["locale"] == "en"
    assert redacted["torrent"]["announce"] == "********"


def test_redact_settings_preserves_empty_secrets() -> None:
    redacted = redact_settings({"api_key": ""})
    assert redacted["api_key"] == ""


def test_redact_settings_handles_lists() -> None:
    settings = {"announce_urls": ["https://a/passkey", "https://b/passkey"]}
    redacted = redact_settings(settings)
    # The list itself is secret-keyed → masked entirely.
    assert redacted["announce_urls"] == "********"


def test_redact_settings_custom_placeholder() -> None:
    redacted = redact_settings({"password": "hunter2"}, placeholder="<encrypted>")
    assert redacted["password"] == "<encrypted>"


def test_redact_settings_passes_through_primitives() -> None:
    assert redact_settings(42) == 42
    assert redact_settings("plain") == "plain"
    assert redact_settings(None) is None


# ---------------------------------------------------------------------------
# _deep_merge
# ---------------------------------------------------------------------------


def test_deep_merge_overrides_scalar() -> None:
    base = {"a": 1, "b": 2}
    out = _deep_merge(base, {"b": 99})
    assert out == {"a": 1, "b": 99}


def test_deep_merge_recurses_dicts() -> None:
    base = {"a": {"x": 1, "y": 2}}
    out = _deep_merge(base, {"a": {"y": 20, "z": 30}})
    assert out == {"a": {"x": 1, "y": 20, "z": 30}}


def test_deep_merge_does_not_mutate_base() -> None:
    base = {"a": {"x": 1}}
    _deep_merge(base, {"a": {"x": 2}})
    assert base == {"a": {"x": 1}}


def test_deep_merge_replaces_dict_with_scalar() -> None:
    base = {"a": {"x": 1}}
    out = _deep_merge(base, {"a": 42})
    assert out == {"a": 42}


# ---------------------------------------------------------------------------
# _split_key_path / _get_nested / _set_nested
# ---------------------------------------------------------------------------


def test_split_key_path_splits_dots() -> None:
    assert _split_key_path("a.b.c") == ["a", "b", "c"]


def test_split_key_path_handles_single() -> None:
    assert _split_key_path("a") == ["a"]


def test_get_nested_returns_value() -> None:
    data = {"a": {"b": {"c": 42}}}
    assert _get_nested(data, "a.b.c") == 42


def test_get_nested_raises_on_missing() -> None:
    from swirrl.core.exceptions import SettingsError

    data = {"a": {}}
    with pytest.raises(SettingsError):
        _get_nested(data, "a.b.c")


def test_get_nested_raises_on_non_dict_segment() -> None:
    from swirrl.core.exceptions import SettingsError

    with pytest.raises(SettingsError):
        _get_nested({"a": 42}, "a.b")


def test_set_nested_updates_existing_path() -> None:
    data: dict[str, Any] = {"a": {"b": {"c": 0}}}
    _set_nested(data, "a.b.c", 42)
    assert data == {"a": {"b": {"c": 42}}}


def test_set_nested_overrides_existing() -> None:
    data = {"a": {"b": 1}}
    _set_nested(data, "a.b", 99)
    assert data == {"a": {"b": 99}}


def test_set_nested_raises_on_unknown_key() -> None:
    from swirrl.core.exceptions import SettingsError

    data: dict[str, Any] = {}
    with pytest.raises(SettingsError):
        _set_nested(data, "a.b.c", 42)


def test_split_key_path_rejects_empty() -> None:
    from swirrl.core.exceptions import SettingsError

    with pytest.raises(SettingsError):
        _split_key_path("")
    with pytest.raises(SettingsError):
        _split_key_path("   ")


def test_normalize_settings_torrent_legacy_announce_is_promoted() -> None:
    data = {
        "modules": {
            "torrent": {
                "announce": "https://tracker.example/announce",
                "announce_urls": [],
                "selected_announce": "",
            }
        }
    }
    normalized = normalize_settings(data)
    torrent = normalized["modules"]["torrent"]
    assert torrent["announce_urls"] == ["https://tracker.example/announce"]
    assert torrent["selected_announce"] == "https://tracker.example/announce"
    assert torrent["announce"] == "https://tracker.example/announce"


def test_normalize_settings_prez_invalid_values_fall_back() -> None:
    data = {"modules": {"prez": {"format": "invalid", "mediainfo_mode": "bad"}}}
    normalized = normalize_settings(data)
    prez = normalized["modules"]["prez"]
    assert prez["format"] == "both"
    assert prez["mediainfo_mode"] == "none"


def test_validate_settings_rejects_invalid_shapes_and_values() -> None:
    from swirrl.core.exceptions import SettingsError

    with pytest.raises(SettingsError):
        validate_settings({"general": []})

    with pytest.raises(SettingsError):
        validate_settings(
            {
                "general": {"locale": "en"},
                "metadata": {"provider": "tmdb", "language": "en-US"},
                "modules": {"nfo": {"locale": "xx"}, "prez": {"locale": "en"}},
            }
        )
