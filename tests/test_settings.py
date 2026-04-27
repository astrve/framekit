from framekit.core.settings import (
    DEFAULT_SETTINGS,
    metadata_language_for_nfo_locale,
    normalize_metadata_language,
    normalize_ui_locale,
    redact_settings,
)


def test_settings_store_creates_default_file(temp_settings_store):
    data = temp_settings_store.load()
    assert data["schema_version"] == DEFAULT_SETTINGS["schema_version"]
    assert temp_settings_store.path.exists()


def test_settings_store_set_and_get(temp_settings_store):
    temp_settings_store.set("general.default_folder", "E:/Media")
    assert temp_settings_store.get("general.default_folder") == "E:/Media"


def test_settings_store_reset(temp_settings_store):
    temp_settings_store.set("general.default_folder", "E:/Media")
    temp_settings_store.reset("general.default_folder")
    assert (
        temp_settings_store.get("general.default_folder")
        == DEFAULT_SETTINGS["general"]["default_folder"]
    )


def test_redact_settings_masks_known_secret_keys():
    payload = {
        "metadata": {
            "tmdb_api_key": "abc123",
            "tmdb_read_access_token": "token123",
            "language": "fr-FR",
        }
    }

    redacted = redact_settings(payload)

    assert redacted["metadata"]["tmdb_api_key"] == "********"
    assert redacted["metadata"]["tmdb_read_access_token"] == "********"
    assert redacted["metadata"]["language"] == "fr-FR"


def test_normalize_ui_locale_uses_supported_language_part():
    assert normalize_ui_locale("fr-FR") == "fr"
    assert normalize_ui_locale("es_419") == "es"
    assert normalize_ui_locale("de-DE") == DEFAULT_SETTINGS["general"]["locale"]


def test_normalize_metadata_language_accepts_region_codes():
    assert normalize_metadata_language("es_419") == "es-419"
    assert normalize_metadata_language("invalid value") == DEFAULT_SETTINGS["metadata"]["language"]


def test_normalize_nfo_locale_accepts_auto_and_supported_languages():
    from framekit.core.settings import normalize_nfo_locale, resolve_nfo_locale

    assert normalize_nfo_locale("auto") == "auto"
    assert normalize_nfo_locale("fr-FR") == "fr"
    assert normalize_nfo_locale("es_419") == "es"
    assert normalize_nfo_locale("de-DE") == "auto"
    assert resolve_nfo_locale("auto", ui_locale="es") == "es"


def test_settings_store_set_nfo_locale(temp_settings_store):
    temp_settings_store.set("modules.nfo.locale", "es")
    assert temp_settings_store.get("modules.nfo.locale") == "es"


def test_metadata_language_for_nfo_locale_uses_tmdb_region_codes():
    assert metadata_language_for_nfo_locale("en") == "en-US"
    assert metadata_language_for_nfo_locale("fr") == "fr-FR"
    assert metadata_language_for_nfo_locale("es") == "es-ES"
    assert metadata_language_for_nfo_locale("es-419") == "es-ES"
