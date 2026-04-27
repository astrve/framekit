from framekit.modules.metadata.config import (
    has_wrapping_quotes,
    looks_like_tmdb_api_key,
    looks_like_tmdb_read_access_token,
    mask_secret,
    normalize_secret_input,
    resolve_metadata_config,
)


def test_resolve_metadata_config_defaults():
    config = resolve_metadata_config({}, env={})
    assert config.provider == "tmdb"
    assert config.language == "en-US"
    assert config.has_credentials is False
    assert config.credential_source == "missing"


def test_resolve_metadata_config_from_settings():
    config = resolve_metadata_config(
        {
            "metadata": {
                "tmdb_api_key": "abc123",
                "language": "fr-FR",
            }
        },
        env={},
    )
    assert config.tmdb_api_key == "abc123"
    assert config.language == "fr-FR"
    assert config.has_credentials is True
    assert config.credential_source == "settings"


def test_resolve_metadata_config_env_overrides_settings():
    config = resolve_metadata_config(
        {
            "metadata": {
                "tmdb_api_key": "settings-key",
                "language": "fr-FR",
            }
        },
        env={
            "FRAMEKIT_TMDB_API_KEY": "env-key",
            "FRAMEKIT_METADATA_LANGUAGE": "en-US",
        },
    )
    assert config.tmdb_api_key == "env-key"
    assert config.language == "en-US"
    assert config.has_credentials is True
    assert config.credential_source == "environment"


def test_resolve_metadata_config_language_override_wins_for_generation_context():
    config = resolve_metadata_config(
        {
            "metadata": {
                "tmdb_api_key": "settings-key",
                "language": "fr-FR",
            }
        },
        env={"FRAMEKIT_METADATA_LANGUAGE": "en-US"},
        language_override="es-ES",
    )
    assert config.language == "es-ES"


def test_mask_secret():
    assert mask_secret("") == "-"
    assert mask_secret("abcd") == "********"
    assert mask_secret("abcdefghijkl") == "********ijkl"


def test_has_wrapping_quotes():
    assert has_wrapping_quotes('"abc"') is True
    assert has_wrapping_quotes("'abc'") is True
    assert has_wrapping_quotes("abc") is False


def test_normalize_secret_input_strips_wrapping_quotes():
    assert normalize_secret_input('"abc"') == "abc"
    assert normalize_secret_input("'abc'") == "abc"
    assert normalize_secret_input("abc") == "abc"


def test_detect_tmdb_api_key_like_value():
    assert looks_like_tmdb_api_key("1234567890abcdef1234567890abcdef") is True
    assert looks_like_tmdb_api_key("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def") is False


def test_detect_tmdb_read_access_token_like_value():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + ("a" * 40) + ".signaturepart"
    assert looks_like_tmdb_read_access_token(token) is True
    assert looks_like_tmdb_read_access_token("1234567890abcdef1234567890abcdef") is False


def test_build_metadata_provider_uses_resolved_env():
    from framekit.modules.metadata.factory import build_metadata_provider

    provider = build_metadata_provider(
        {"metadata": {"tmdb_read_access_token": "settings.token", "language": "en-US"}},
        env={
            "FRAMEKIT_TMDB_READ_ACCESS_TOKEN": "env.token",
            "FRAMEKIT_METADATA_LANGUAGE": "fr-FR",
        },
    )

    assert provider.config.read_access_token == "env.token"
    assert provider.config.language == "fr-FR"
