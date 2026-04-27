from __future__ import annotations

import json
from importlib import resources

from framekit.core.i18n import DEFAULT_LOCALE, get_supported_locales


def _load_locale(locale: str) -> dict[str, str]:
    resource = resources.files("framekit.locales").joinpath(f"{locale}.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return {str(key): str(value) for key, value in payload.items()}


def test_locale_catalogs_are_key_aligned() -> None:
    reference = _load_locale(DEFAULT_LOCALE)
    reference_keys = set(reference)

    for locale in get_supported_locales():
        catalog = _load_locale(locale)
        keys = set(catalog)

        assert keys == reference_keys, (
            f"Locale catalog {locale!r} is not aligned with {DEFAULT_LOCALE!r}: "
            f"missing={sorted(reference_keys - keys)}, extra={sorted(keys - reference_keys)}"
        )


def test_locale_catalog_values_are_not_empty() -> None:
    for locale in get_supported_locales():
        catalog = _load_locale(locale)
        empty_keys = [key for key, value in catalog.items() if not value.strip()]
        assert empty_keys == []
