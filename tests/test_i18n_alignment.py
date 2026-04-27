import json
from pathlib import Path

import framekit.locales


def test_i18n_key_alignment() -> None:
    """
    All locale JSON files should define the same set of keys so that translations are
    complete and consistent. If a key is missing in any language, this test will fail.
    """
    locale_dir = Path(framekit.locales.__file__).parent
    locales = ["en", "fr", "es"]
    expected_keys: set[str] | None = None
    for lang in locales:
        file_path = locale_dir / f"{lang}.json"
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        keys = set(data.keys())
        if expected_keys is None:
            expected_keys = keys
        else:
            assert keys == expected_keys, f"Locale '{lang}' does not match base keys"
