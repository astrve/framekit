from framekit.core.i18n import get_supported_locales, set_locale, tr


def test_i18n_loads_bundled_spanish_catalog(monkeypatch):
    monkeypatch.setenv("FRAMEKIT_LOCALE", "es")
    set_locale("es")

    assert "es" in get_supported_locales()
    assert tr("common.yes") == "Sí"


def test_i18n_falls_back_to_english_for_missing_key(monkeypatch):
    monkeypatch.setenv("FRAMEKIT_LOCALE", "es")
    set_locale("es")

    assert tr("tools.not_found") == "no encontrado"
    assert tr("unknown.key", default="fallback") == "fallback"
