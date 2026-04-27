from __future__ import annotations

from framekit.core.diagnostics import redact as diagnostics_redact
from framekit.core.settings import redact_settings

"""
Tests for secret redaction in settings and diagnostics.

These tests ensure that sensitive values such as TMDb API keys and torrent
announce URLs are redacted when exposed through the settings redaction
function or diagnostics log redaction.

The redaction logic uses substring matching of keys defined in
SECRET_KEY_PARTS to determine which configuration entries should be hidden.
This includes TMDb credentials as well as torrent announce configuration.
"""


def test_redact_settings_hides_torrent_announces_and_tokens() -> None:
    """`redact_settings` should mask announce-related settings and TMDb keys."""
    settings = {
        "modules": {
            "torrent": {
                "announce": "https://tracker.example/announce?passkey=abcd",
                "announce_urls": [
                    "https://tracker.example/announce?passkey=abcd",
                    "https://other.example/announce",
                ],
                "selected_announce": "https://tracker.example/announce?passkey=abcd",
            }
        },
        "metadata": {
            "tmdb_api_key": "tmdb-key",
            "tmdb_read_access_token": "tmdb-token",
        },
    }
    masked = redact_settings(settings)
    # Torrent announce configuration should be completely masked
    torrent = masked["modules"]["torrent"]
    assert torrent["announce"] == "********"
    # announce_urls is a secret key so the entire list is replaced with a placeholder
    assert torrent["announce_urls"] == "********"
    assert torrent["selected_announce"] == "********"
    # TMDb credentials should also be masked
    meta = masked["metadata"]
    assert meta["tmdb_api_key"] == "********"
    assert meta["tmdb_read_access_token"] == "********"


def test_diagnostics_redact_hides_torrent_announces_and_tokens() -> None:
    """`diagnostics.redact` should mask announce-related values in context logs."""
    context = {
        "announce": "https://tracker.example/announce?passkey=abcd",
        "announce_urls": [
            "https://tracker.example/announce?passkey=abcd",
            "https://other.example/announce",
        ],
        "selected_announce": "https://tracker.example/announce?passkey=abcd",
        "tmdb_api_key": "tmdb-key",
        "tmdb_read_access_token": "tmdb-token",
        "other": "non-secret value",
    }
    redacted = diagnostics_redact(context)
    # All announce-related entries should be hidden
    assert redacted["announce"] == "********"
    assert redacted["announce_urls"] == "********"
    assert redacted["selected_announce"] == "********"
    # TMDb credentials should be hidden
    assert redacted["tmdb_api_key"] == "********"
    assert redacted["tmdb_read_access_token"] == "********"
    # Non-secret values should remain unchanged
    assert redacted["other"] == "non-secret value"
