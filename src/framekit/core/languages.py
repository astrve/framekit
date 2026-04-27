from __future__ import annotations

from dataclasses import dataclass

try:
    import langcodes  # type: ignore[import]
except ImportError:
    # langcodes is an optional dependency used to guess languages and variants.
    # If not installed, set it to None so that fallback logic is used.
    langcodes = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class LanguageInfo:
    language: str | None
    variant: str | None


_LANGUAGE_ALIASES: dict[str, tuple[str, str | None]] = {
    "fr": ("french", None),
    "fra": ("french", None),
    "fre": ("french", None),
    "fr-fr": ("french", "france"),
    "fr-ca": ("french", "canada"),
    "fr-qc": ("french", "canada"),
    "french": ("french", None),
    "french (france)": ("french", "france"),
    "français": ("french", None),
    "francais": ("french", None),
    "en": ("english", None),
    "eng": ("english", None),
    "en-us": ("english", "us"),
    "en-gb": ("english", "uk"),
    "english": ("english", None),
    "anglais": ("english", None),
    "ja": ("japanese", None),
    "jpn": ("japanese", None),
    "ja-jp": ("japanese", None),
    "japanese": ("japanese", None),
    "japonais": ("japanese", None),
    "es": ("spanish", None),
    "spa": ("spanish", None),
    "es-es": ("spanish", None),
    "es-419": ("spanish", "latam"),
    "spanish": ("spanish", None),
    "espagnol": ("spanish", None),
    "español": ("spanish", None),
    "it": ("italian", None),
    "ita": ("italian", None),
    "italian": ("italian", None),
    "de": ("german", None),
    "deu": ("german", None),
    "ger": ("german", None),
    "german": ("german", None),
    "pt": ("portuguese", None),
    "por": ("portuguese", None),
    "pt-br": ("portuguese", "brazil"),
    "pt-pt": ("portuguese", "europe"),
    "portuguese": ("portuguese", None),
    "ru": ("russian", None),
    "rus": ("russian", None),
    "russian": ("russian", None),
    "russe": ("russian", None),
    "tr": ("turkish", None),
    "tur": ("turkish", None),
    "turkish": ("turkish", None),
    "turc": ("turkish", None),
    "pl": ("polish", None),
    "pol": ("polish", None),
    "polish": ("polish", None),
    "polonais": ("polish", None),
    "ar": ("arabic", None),
    "ara": ("arabic", None),
    "arabic": ("arabic", None),
    "arabe": ("arabic", None),
    "id": ("indonesian", None),
    "ind": ("indonesian", None),
    "indonesian": ("indonesian", None),
    "indonésien": ("indonesian", None),
    "indonesien": ("indonesian", None),
}


LANGUAGE_SHORT_MAP: dict[str, str] = {
    "french": "fr",
    "english": "en",
    "japanese": "ja",
    "spanish": "es",
    "italian": "it",
    "german": "de",
    "portuguese": "pt",
    "russian": "ru",
    "turkish": "tr",
    "polish": "pl",
    "arabic": "ar",
    "indonesian": "id",
}


VARIANT_SHORT_MAP: dict[str, str] = {
    "france": "FR",
    "canada": "CA",
    "us": "US",
    "uk": "GB",
    "latam": "419",
    "brazil": "BR",
    "europe": "PT",
}


LANGUAGE_DISPLAY_MAP: dict[str, str] = {
    "french": "French",
    "english": "English",
    "japanese": "Japanese",
    "spanish": "Spanish",
    "italian": "Italian",
    "german": "German",
    "portuguese": "Portuguese",
    "russian": "Russian",
    "turkish": "Turkish",
    "polish": "Polish",
    "arabic": "Arabic",
    "indonesian": "Indonesian",
}


VALID_LANGUAGE_VARIANTS: set[str] = {
    "france",
    "canada",
    "us",
    "uk",
    "latam",
    "brazil",
    "europe",
}


VARIANT_DISPLAY_MAP: dict[str, str] = {
    "france": "France",
    "canada": "Canada",
    "us": "US",
    "uk": "UK",
    "latam": "LATAM",
    "brazil": "Brazil",
    "europe": "Europe",
}


_REGION_TO_VARIANT: dict[str, str] = {
    "FR": "france",
    "CA": "canada",
    "US": "us",
    "GB": "uk",
    "419": "latam",
    "BR": "brazil",
    "PT": "europe",
}

_LANGUAGE_NAME_TO_INTERNAL: dict[str, str] = {
    "french": "french",
    "english": "english",
    "japanese": "japanese",
    "spanish": "spanish",
    "italian": "italian",
    "german": "german",
    "portuguese": "portuguese",
    "russian": "russian",
    "turkish": "turkish",
    "polish": "polish",
    "arabic": "arabic",
    "indonesian": "indonesian",
}


def _normalize_key(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", "-")


def _from_alias(value: str | None) -> LanguageInfo | None:
    key = _normalize_key(value)
    if not key:
        return None

    match = _LANGUAGE_ALIASES.get(key)
    if match is None:
        return None

    return LanguageInfo(language=match[0], variant=match[1])


def _from_langcodes(value: str | None) -> LanguageInfo | None:
    key = _normalize_key(value)
    if not key:
        return None

    if langcodes is None:
        # Without langcodes, we cannot infer languages beyond the alias map.
        return None
    try:
        language = langcodes.Language.get(key)
    except Exception:
        return None

    base = (language.language or "").lower()
    region = (language.region or "").upper()

    internal_language = _LANGUAGE_NAME_TO_INTERNAL.get(
        str(langcodes.Language.make(language=base).display_name("en")).strip().lower()
    )
    if internal_language is None:
        internal_language = _LANGUAGE_NAME_TO_INTERNAL.get(base)

    if internal_language is None and base in {
        "fr",
        "en",
        "ja",
        "es",
        "it",
        "de",
        "pt",
        "ru",
        "tr",
        "pl",
        "ar",
        "id",
    }:
        reverse = {v: k for k, v in LANGUAGE_SHORT_MAP.items()}
        internal_language = reverse.get(base)

    if internal_language is None:
        return None

    variant = _REGION_TO_VARIANT.get(region)
    return LanguageInfo(language=internal_language, variant=variant)


def normalize_language(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None

    alias_match = _from_alias(value)
    if alias_match is not None:
        return alias_match.language, alias_match.variant

    langcodes_match = _from_langcodes(value)
    if langcodes_match is not None:
        return langcodes_match.language, langcodes_match.variant

    key = _normalize_key(value)
    return key or None, None


def is_french(value: str | None) -> bool:
    lang, _variant = normalize_language(value)
    return lang == "french"


def language_short_label(language: str | None, variant: str | None = None) -> str:
    if not language:
        return "und"

    base = LANGUAGE_SHORT_MAP.get(language, language[:2].lower())
    if not variant:
        return base

    variant_code = VARIANT_SHORT_MAP.get(variant, variant[:2].upper())
    return f"{base}-{variant_code}"


def parse_language_filter(value: str) -> tuple[str, str | None]:
    raw = str(value).strip().lower()
    if not raw:
        raise ValueError("Language filter cannot be empty.")

    if ":" not in raw:
        return raw, None

    language, variant = raw.split(":", 1)
    language = language.strip()
    variant = variant.strip()

    if not language or not variant:
        raise ValueError(f"Invalid language filter: {value}")

    return language, variant


def is_valid_language_filter(value: str) -> bool:
    try:
        language, variant = parse_language_filter(value)
    except ValueError:
        return False

    if language not in LANGUAGE_SHORT_MAP:
        return False

    return variant is None or variant in VALID_LANGUAGE_VARIANTS


def match_language_filter(
    language: str | None,
    variant: str | None,
    filter_value: str,
) -> bool:
    if not language:
        return False

    expected_language, expected_variant = parse_language_filter(filter_value)

    if language != expected_language:
        return False

    if expected_variant is None:
        return True

    return variant == expected_variant


def language_filter_short_label(filter_value: str) -> str:
    language, variant = parse_language_filter(filter_value)
    return language_short_label(language, variant)


def language_filter_display_label(filter_value: str) -> str:
    language, variant = parse_language_filter(filter_value)

    base = LANGUAGE_DISPLAY_MAP.get(language, language.replace("_", " ").title())
    if variant is None:
        return base

    suffix = VARIANT_DISPLAY_MAP.get(variant, variant.replace("_", " ").title())
    return f"{base} ({suffix})"


def language_display_label(language: str | None, variant: str | None = None) -> str:
    if not language:
        return "Unknown"

    base = LANGUAGE_DISPLAY_MAP.get(language, language.replace("_", " ").title())
    if not variant:
        return base

    suffix = VARIANT_DISPLAY_MAP.get(variant, variant.replace("_", " ").title())
    return f"{base} ({suffix})"


def subtitle_variant_display_label(value: str | None) -> str:
    if not value:
        return "Unknown"

    mapping = {
        "forced": "Forced",
        "full": "Full",
        "sdh": "SDH",
    }
    return mapping.get(value, value.replace("_", " ").title())
